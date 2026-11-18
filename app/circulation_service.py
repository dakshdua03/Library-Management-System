from datetime import datetime, date, timedelta
from app.extensions import db
from app.models import Patron, BookTitle, BookCopy, BorrowTransaction, Reservation, Fine, BorrowingRules

class CirculationService:

    @staticmethod
    def validate_and_issue_book(patron_id, accession_no):
        """
        Implements 5-Point Issue Validations (Sequence Diagram 1 & Backlog):
        1. Patron active check
        2. Unpaid fine threshold check (fine_balance <= 100)
        3. Role max borrowing quota check
        4. Copy availability check ('Available')
        5. Duplicate loan guard (patron cannot borrow 2 copies of the exact same title simultaneously)
        """
        patron = Patron.query.get(patron_id)
        if not patron:
            return False, "Patron record not found.", None

        # Point 1: Active check
        if not patron.is_active:
            return False, "Issue blocked: Patron account is deactivated.", None

        # Point 2: Fine threshold
        if patron.fine_balance > 100.0:
            return False, f"Issue blocked: Patron fine balance (Rs. {patron.fine_balance:.2f}) exceeds the Rs. 100.00 threshold.", None

        # Point 3: Role borrowing limit
        rule = BorrowingRules.get_rule_for_role(patron.role)
        max_allowed = rule.max_books_allowed if rule else 3
        loan_days = rule.loan_duration_days if rule else 14

        # Count current active loans
        active_loans_count = BorrowTransaction.query.filter_by(patron_id=patron.id, status='Active').count()
        if active_loans_count >= max_allowed:
            return False, f"Issue blocked: Patron has reached the borrowing limit for {patron.role} ({max_allowed} books).", None

        # Point 4: Copy availability
        copy = BookCopy.query.get(accession_no)
        if not copy:
            return False, f"Issue blocked: Book copy '{accession_no}' does not exist.", None
        if copy.status != 'Available':
            return False, f"Issue blocked: Copy '{accession_no}' is currently '{copy.status}'.", None

        # Point 5: Duplicate title active loan guard
        title_isbn = copy.isbn
        has_same_title = (
            db.session.query(BorrowTransaction)
            .join(BookCopy, BorrowTransaction.accession_no == BookCopy.accession_no)
            .filter(
                BorrowTransaction.patron_id == patron.id,
                BorrowTransaction.status == 'Active',
                BookCopy.isbn == title_isbn
            )
            .first()
        )
        if has_same_title:
            return False, "Issue blocked: Patron already holds an active loan of this book title.", None

        # All 5 validations passed -> Atomic Commit
        today = datetime.now()
        due_date = today + timedelta(days=loan_days)

        transaction = BorrowTransaction(
            patron_id=patron.id,
            accession_no=copy.accession_no,
            issue_date=today,
            due_date=due_date,
            status='Active',
            renewal_count=0
        )
        copy.status = 'Issued'
        patron.current_borrowed_count = active_loans_count + 1

        db.session.add(transaction)
        db.session.commit()

        return True, "Book issued successfully!", transaction

    @staticmethod
    def process_return(borrow_id_or_accession):
        """
        Implements Return Book Workflow (Sequence Diagram 2 & Backlog):
        - Calculates overdue days (if return_date > due_date)
        - Computes fine at rule rate (Rs. 2/day, capped at Rs. 200)
        - Commits return, marks copy Available (or OnHold if waitlist exists)
        """
        tx = None
        cleaned_input = str(borrow_id_or_accession).strip()
        if cleaned_input.isdigit():
            tx = BorrowTransaction.query.filter_by(id=int(cleaned_input), status='Active').first()

        if not tx:
            tx = BorrowTransaction.query.filter_by(accession_no=cleaned_input.upper(), status='Active').first()

        if not tx:
            return False, f"No active loan found for '{borrow_id_or_accession}'.", None

        copy = BookCopy.query.get(tx.accession_no)
        patron = Patron.query.get(tx.patron_id)
        rule = BorrowingRules.get_rule_for_role(patron.role)
        fine_rate = rule.fine_per_day if rule else 2.0
        fine_cap = rule.max_fine_cap if rule else 200.0

        now = datetime.now()
        overdue_days = 0
        fine_amount = 0.0

        # Calculate overdue if past due_date
        if now > tx.due_date:
            delta = now - tx.due_date
            overdue_days = max(1, delta.days)
            raw_fine = overdue_days * fine_rate
            fine_amount = min(raw_fine, fine_cap)

        tx.return_date = now
        tx.status = 'Returned'

        # Record fine if overdue
        if fine_amount > 0:
            fine_record = Fine(
                borrow_id=tx.id,
                days_overdue=overdue_days,
                amount=fine_amount,
                paid_status='Unpaid'
            )
            db.session.add(fine_record)
            patron.fine_balance += fine_amount

        # Update patron active loan count
        patron.current_borrowed_count = max(0, patron.current_borrowed_count - 1)

        # Check if reservation queue exists for this title (Collaboration Diagram 2 Step 7)
        title_isbn = copy.isbn
        waitlist_next = (
            Reservation.query.filter_by(isbn=title_isbn, status='Pending')
            .order_by(Reservation.queue_position.asc(), Reservation.request_date.asc())
            .first()
        )

        hold_status = "Available"
        if waitlist_next:
            copy.status = 'OnHold'
            hold_status = f"Placed On 48-hr Hold for Waitlisted Patron ID {waitlist_next.patron_id}"
        else:
            copy.status = 'Available'

        db.session.commit()

        summary = {
            'borrow_id': tx.id,
            'patron_name': patron.name,
            'patron_roll': patron.roll_number,
            'patron_photo': patron.photo_path,
            'title': copy.title_rel.title,
            'accession_no': copy.accession_no,
            'issue_date': tx.issue_date,
            'due_date': tx.due_date,
            'return_date': tx.return_date,
            'overdue_days': overdue_days,
            'fine_amount': fine_amount,
            'hold_status': hold_status
        }

        return True, "Book returned successfully!", summary

    @staticmethod
    def process_renewal(borrow_id, patron_id=None):
        """
        Implements Renewal Workflow (Sequence Diagram 3 & Backlog):
        1. Check active reservation hold on the title -> Reject if reserved
        2. Check patron max renewals (Student 2, Faculty 3, Staff 2) -> Reject if reached
        3. Check overdue status -> Reject if overdue by more than 7 days
        4. Extend due date by loan_duration_days
        """
        tx = BorrowTransaction.query.get(borrow_id)
        if not tx or tx.status != 'Active':
            return False, "Active loan record not found."

        # If patron_id provided (self-service), ensure student owns the loan
        if patron_id and tx.patron_id != patron_id:
            return False, "Unauthorized: You can only renew your own borrowed books."

        copy = BookCopy.query.get(tx.accession_no)
        patron = Patron.query.get(tx.patron_id)
        rule = BorrowingRules.get_rule_for_role(patron.role)

        max_renewals = rule.max_renewals if rule else 2
        loan_days = rule.loan_duration_days if rule else 14

        # Guard 1: Check if another patron has reserved this title
        has_reservation = Reservation.query.filter(
            Reservation.isbn == copy.isbn,
            Reservation.status == 'Pending',
            Reservation.patron_id != patron.id
        ).first()

        if has_reservation:
            return False, "Renewal rejected: This book is reserved by another patron."

        # Guard 2: Max renewal count reached
        if tx.renewal_count >= max_renewals:
            return False, f"Renewal rejected: You have reached the maximum allowed renewals ({max_renewals})."

        # Guard 3: Overdue > 7 days
        now = datetime.now()
        if now > tx.due_date:
            overdue_days = (now - tx.due_date).days
            if overdue_days > 7:
                return False, f"Renewal rejected: Book is overdue by {overdue_days} days (cutoff is 7 days). Please return it to the counter."

        # Passed all guards -> Extend due date
        base_date = tx.due_date if tx.due_date > now else now
        tx.due_date = base_date + timedelta(days=loan_days)
        tx.renewal_count += 1

        db.session.commit()
        return True, f"Book renewed successfully! New Due Date: {tx.due_date.strftime('%d-%m-%Y')} (Renewed: {tx.renewal_count}/{max_renewals})."
