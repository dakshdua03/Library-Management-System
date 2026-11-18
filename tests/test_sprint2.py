import unittest
from datetime import datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy, BorrowTransaction, Reservation
from app.circulation_service import CirculationService

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class Sprint2CirculationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed Borrowing Rules
        rules = [
            BorrowingRules(role='Student', max_books_allowed=3, loan_duration_days=14, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
            BorrowingRules(role='Faculty', max_books_allowed=10, loan_duration_days=30, max_renewals=3, fine_per_day=2.0, max_fine_cap=200.0),
        ]
        db.session.add_all(rules)

        # Seed Patrons
        self.admin = Patron(name="Admin", role="Admin", roll_number="ADMIN01", email="admin@test.com")
        self.librarian = Patron(name="Librarian", role="Librarian", roll_number="LIB01", email="lib@test.com")
        self.student = Patron(name="Student Daksh", role="Student", roll_number="25MCMC21", email="student@test.com")
        self.student2 = Patron(name="Student Satyabrata", role="Student", roll_number="25MCMC36", email="student2@test.com")
        db.session.add_all([self.admin, self.librarian, self.student, self.student2])

        # Seed Book Title & Copies
        self.title1 = BookTitle(isbn="9780133943030", title="Software Engineering", authors="Ian Sommerville")
        self.copy1 = BookCopy(accession_no="ACC-101", isbn="9780133943030", status="Available")
        self.copy2 = BookCopy(accession_no="ACC-102", isbn="9780133943030", status="Available")

        self.title2 = BookTitle(isbn="9780132350884", title="Clean Code", authors="Robert C. Martin")
        self.copy3 = BookCopy(accession_no="ACC-201", isbn="9780132350884", status="Available")

        db.session.add_all([self.title1, self.copy1, self.copy2, self.title2, self.copy3])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # --- Test 1: Successful Issue with Role Due Date (+14 days for student) ---
    def test_successful_issue_decrements_availability_and_sets_due_date(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        self.assertTrue(success)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'Active')
        
        # Verify copy marked Issued
        copy = BookCopy.query.get("ACC-101")
        self.assertEqual(copy.status, 'Issued')

        # Verify due date is exactly 14 days later
        expected_due = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        self.assertEqual(tx.due_date.strftime('%Y-%m-%d'), expected_due)

        # Title availability decreases
        title = BookTitle.query.get("9780133943030")
        self.assertEqual(title.available_copies, 1)  # Was 2, now 1

    # --- Test 2: Issue blocked when patron is deactivated ---
    def test_issue_blocked_for_deactivated_patron(self):
        self.student.is_active = False
        db.session.commit()

        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        self.assertFalse(success)
        self.assertIn("deactivated", msg.lower())

    # --- Test 3: Issue blocked when fine exceeds Rs. 100 ---
    def test_issue_blocked_when_fine_exceeds_threshold(self):
        self.student.fine_balance = 120.0
        db.session.commit()

        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        self.assertFalse(success)
        self.assertIn("exceeds the rs. 100", msg.lower())

    # --- Test 4: Issue blocked when role book limit reached (Student max 3) ---
    def test_issue_blocked_when_max_books_quota_reached(self):
        # Create separate book titles for each copy so duplicate-title guard isn't triggered
        t_a = BookTitle(isbn="9780000000001", title="Title A")
        t_b = BookTitle(isbn="9780000000002", title="Title B")
        t_c = BookTitle(isbn="9780000000003", title="Title C")
        copyA = BookCopy(accession_no="ACC-A", isbn="9780000000001", status="Available")
        copyB = BookCopy(accession_no="ACC-B", isbn="9780000000002", status="Available")
        copyC = BookCopy(accession_no="ACC-C", isbn="9780000000003", status="Available")
        db.session.add_all([t_a, t_b, t_c, copyA, copyB, copyC])
        db.session.commit()

        # Issue 3 distinct books (filling student quota of 3)
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        CirculationService.validate_and_issue_book(self.student.id, "ACC-A")
        CirculationService.validate_and_issue_book(self.student.id, "ACC-B")

        # 4th issue attempt must be blocked by borrowing limit
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-C")
        self.assertFalse(success)
        self.assertIn("borrowing limit", msg.lower())

    # --- Test 5: Issue blocked if patron already has an active loan of the same book title ---
    def test_issue_blocked_for_duplicate_active_title_loan(self):
        # Issue ACC-101 (Software Engineering)
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")

        # Attempt to issue ACC-102 (also Software Engineering)
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-102")
        self.assertFalse(success)
        self.assertIn("already holds an active loan", msg.lower())

    # --- Test 6: Return on time calculates zero fine and restores availability ---
    def test_return_on_time_has_zero_fine(self):
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        
        success, msg, summary = CirculationService.process_return("ACC-101")
        self.assertTrue(success)
        self.assertEqual(summary['fine_amount'], 0.0)
        self.assertEqual(summary['overdue_days'], 0)

        copy = BookCopy.query.get("ACC-101")
        self.assertEqual(copy.status, 'Available')

    # --- Test 7: Return overdue calculates fine at Rs. 2/day and caps at Rs. 200 ---
    def test_return_overdue_calculates_correct_fine_and_caps_at_200(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        
        # Simulate loan 10 days overdue
        tx.due_date = datetime.now() - timedelta(days=10)
        db.session.commit()

        success, msg, summary = CirculationService.process_return("ACC-101")
        self.assertTrue(success)
        self.assertEqual(summary['overdue_days'], 10)
        self.assertEqual(summary['fine_amount'], 20.0)  # 10 days * Rs. 2

        # Check patron fine balance increased
        student = Patron.query.get(self.student.id)
        self.assertEqual(student.fine_balance, 20.0)

        # Test fine capping at Rs. 200 (e.g. 150 days overdue -> 300, capped at 200)
        success2, msg2, tx2 = CirculationService.validate_and_issue_book(self.student.id, "ACC-201")
        tx2.due_date = datetime.now() - timedelta(days=150)
        db.session.commit()

        success3, msg3, summary2 = CirculationService.process_return("ACC-201")
        self.assertTrue(success3)
        self.assertEqual(summary2['fine_amount'], 200.0)  # Capped at 200

    # --- Test 8: Renewal guards (Reservation hold blocks renewal) ---
    def test_renewal_blocked_when_title_is_reserved(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")

        # Student 2 reserves this title
        reservation = Reservation(patron_id=self.student2.id, isbn="9780133943030", status="Pending")
        db.session.add(reservation)
        db.session.commit()

        # Student 1 attempts to renew
        renew_ok, renew_msg = CirculationService.process_renewal(tx.id, patron_id=self.student.id)
        self.assertFalse(renew_ok)
        self.assertIn("reserved by another patron", renew_msg.lower())

    # --- Test 9: Renewal extends due date and increments count ---
    def test_valid_renewal_extends_due_date(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        original_due = tx.due_date

        renew_ok, renew_msg = CirculationService.process_renewal(tx.id, patron_id=self.student.id)
        self.assertTrue(renew_ok)
        self.assertEqual(tx.renewal_count, 1)
        self.assertTrue(tx.due_date > original_due)

    # --- Test 10: Renewal blocked after max renewals exceeded (Student limit = 2) ---
    def test_renewal_blocked_after_max_count(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx.renewal_count = 2  # Max for student
        db.session.commit()

        renew_ok, renew_msg = CirculationService.process_renewal(tx.id, patron_id=self.student.id)
        self.assertFalse(renew_ok)
        self.assertIn("maximum allowed renewals", renew_msg.lower())

    # --- Test 11: Renewal blocked if overdue by more than 7 days ---
    def test_renewal_blocked_if_overdue_more_than_7_days(self):
        success, msg, tx = CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx.due_date = datetime.now() - timedelta(days=9)  # 9 days overdue (> 7)
        db.session.commit()

        renew_ok, renew_msg = CirculationService.process_renewal(tx.id, patron_id=self.student.id)
        self.assertFalse(renew_ok)
        self.assertIn("overdue by 9 days", renew_msg.lower())

if __name__ == '__main__':
    unittest.main()
