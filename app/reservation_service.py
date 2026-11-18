from datetime import datetime
from app.extensions import db
from app.models import Patron, BookTitle, BookCopy, Reservation, BorrowTransaction

class ReservationService:

    @staticmethod
    def create_reservation(patron_id, isbn):
        """
        Implements Reserve Book Workflow (Sequence Diagram 4 & Backlog):
        1. Verify patron exists and is active.
        2. Verify book title exists.
        3. Verify UNAVAILABILITY: All physical copies must be issued/unavailable (0 available).
           If any copy is on the shelf, reservation is blocked.
        4. Verify NO DUPLICATE: Patron cannot hold 2 active reservations on the same title.
        5. Verify patron does not currently have this book issued.
        6. Compute next FCFS queue position (e.g. Queue #N).
        7. Record reservation with timestamp=Now().
        """
        patron = Patron.query.get(patron_id)
        if not patron:
            return False, "Patron not found.", None

        if not patron.is_active:
            return False, "Reservation blocked: Your account is deactivated.", None

        title = BookTitle.query.get(isbn)
        if not title:
            return False, "Book title not found.", None

        # Guard 1: Copies must be unavailable (available_copies == 0)
        available_count = title.available_copies
        if available_count > 0:
            return False, f"Reservation not allowed: {available_count} physical copy is currently available on the shelf for direct issue.", None

        # Guard 2: Duplicate reservation check
        existing_res = Reservation.query.filter_by(
            patron_id=patron.id,
            isbn=title.isbn,
            status='Pending'
        ).first()
        if existing_res:
            return False, f"You already have an active reservation for this book (Queue Position #{existing_res.queue_position}).", None

        # Guard 3: Check if patron already has an active loan of this title
        has_active_loan = (
            db.session.query(BorrowTransaction)
            .join(BookCopy, BorrowTransaction.accession_no == BookCopy.accession_no)
            .filter(
                BorrowTransaction.patron_id == patron.id,
                BorrowTransaction.status == 'Active',
                BookCopy.isbn == title.isbn
            )
            .first()
        )
        if has_active_loan:
            return False, "You already have an issued copy of this book.", None

        # Compute FCFS Queue Position
        highest_pos = (
            db.session.query(db.func.max(Reservation.queue_position))
            .filter_by(isbn=title.isbn, status='Pending')
            .scalar()
        ) or 0
        new_position = highest_pos + 1

        reservation = Reservation(
            patron_id=patron.id,
            isbn=title.isbn,
            request_date=datetime.now(),
            queue_position=new_position,
            status='Pending'
        )

        db.session.add(reservation)
        db.session.commit()

        return True, f"Book reserved successfully! Your FCFS queue position is #{new_position}.", reservation

    @staticmethod
    def cancel_reservation(reservation_id, requested_by_patron_id=None, is_admin_or_librarian=False):
        """
        Cancels an active reservation and shifts subsequent queue positions down.
        Can be cancelled by the student themselves or by an Admin/Librarian.
        """
        res = Reservation.query.get(reservation_id)
        if not res or res.status != 'Pending':
            return False, "Active reservation record not found."

        # Authorization guard
        if not is_admin_or_librarian and (requested_by_patron_id and res.patron_id != requested_by_patron_id):
            return False, "Unauthorized: You can only cancel your own reservations."

        cancelled_pos = res.queue_position
        isbn = res.isbn

        res.status = 'Cancelled'

        # Shift all subsequent reservations for this ISBN down by 1
        subsequent_reservations = (
            Reservation.query.filter(
                Reservation.isbn == isbn,
                Reservation.status == 'Pending',
                Reservation.queue_position > cancelled_pos
            )
            .all()
        )
        for r in subsequent_reservations:
            r.queue_position -= 1

        db.session.commit()
        return True, "Reservation cancelled successfully. Waitlist queue updated."
