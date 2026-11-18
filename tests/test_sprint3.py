import unittest
from datetime import datetime
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy, Reservation, BorrowTransaction
from app.reservation_service import ReservationService
from app.circulation_service import CirculationService

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class Sprint3SelfServiceAcceptanceTests(unittest.TestCase):
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
        self.student1 = Patron(name="Student Daksh", role="Student", roll_number="25MCMC21", email="daksh@test.com")
        self.student2 = Patron(name="Student Satyabrata", role="Student", roll_number="25MCMC36", email="satyabrata@test.com")
        self.student3 = Patron(name="Student Rahul", role="Student", roll_number="25MCMC50", email="rahul@test.com")
        db.session.add_all([self.admin, self.librarian, self.student1, self.student2, self.student3])

        # Seed Book Title & Copies
        self.title1 = BookTitle(isbn="9780133943030", title="Software Engineering", authors="Ian Sommerville", category="Computer Science")
        self.copy1 = BookCopy(accession_no="ACC-101", isbn="9780133943030", rack_no="Rack B2", shelf_no="Shelf 3", status="Available")

        self.title2 = BookTitle(isbn="9780132350884", title="Clean Code", authors="Robert C. Martin", category="Software Engineering")
        self.copy2 = BookCopy(accession_no="ACC-201", isbn="9780132350884", rack_no="Rack C1", shelf_no="Shelf 4", status="Available")

        db.session.add_all([self.title1, self.copy1, self.title2, self.copy2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_as(self, roll_number):
        return self.client.post('/auth/login', data={'roll_number': roll_number}, follow_redirects=True)

    # --- Test 1: Public Search filters by title, author, category, available_only ---
    def test_search_catalog_with_filters(self):
        self.login_as("25MCMC21")
        # Search by query
        resp = self.client.get('/selfservice/search?q=Sommerville')
        self.assertIn(b'Software Engineering', resp.data)
        self.assertNotIn(b'Clean Code', resp.data)

        # Search by category
        resp_cat = self.client.get('/selfservice/search?category=Computer+Science')
        self.assertIn(b'Software Engineering', resp_cat.data)

        # Shelf location displayed
        self.assertIn(b'Rack B2', resp_cat.data)
        self.assertIn(b'Shelf 3', resp_cat.data)

    # --- Test 2: Reservation blocked when available copies > 0 ---
    def test_reservation_blocked_when_copies_are_available(self):
        # 1 copy is available
        self.assertEqual(self.title1.available_copies, 1)

        success, msg, res = ReservationService.create_reservation(self.student1.id, self.title1.isbn)
        self.assertFalse(success)
        self.assertIn("currently available on the shelf", msg.lower())

    # --- Test 3: Reservation succeeds on FCFS basis when all copies are issued ---
    def test_reservation_succeeds_when_all_copies_issued_fcfs_queue(self):
        # Issue the only copy of title1 to student1
        CirculationService.validate_and_issue_book(self.student1.id, "ACC-101")
        self.assertEqual(self.title1.available_copies, 0)

        # Student 2 reserves -> Should get Queue #1
        ok1, msg1, res1 = ReservationService.create_reservation(self.student2.id, self.title1.isbn)
        self.assertTrue(ok1)
        self.assertEqual(res1.queue_position, 1)
        self.assertIn("queue position is #1", msg1.lower())

        # Student 3 reserves -> Should get Queue #2
        ok2, msg2, res2 = ReservationService.create_reservation(self.student3.id, self.title1.isbn)
        self.assertTrue(ok2)
        self.assertEqual(res2.queue_position, 2)
        self.assertIn("queue position is #2", msg2.lower())

    # --- Test 4: Duplicate active reservation blocked for the same student ---
    def test_duplicate_reservation_blocked(self):
        CirculationService.validate_and_issue_book(self.student1.id, "ACC-101")

        # Student 2 places reservation
        ReservationService.create_reservation(self.student2.id, self.title1.isbn)

        # Student 2 tries to reserve again
        ok, msg, res = ReservationService.create_reservation(self.student2.id, self.title1.isbn)
        self.assertFalse(ok)
        self.assertIn("already have an active reservation", msg.lower())

    # --- Test 5: Patron cannot reserve a book they currently have checked out ---
    def test_patron_cannot_reserve_their_own_issued_book(self):
        CirculationService.validate_and_issue_book(self.student1.id, "ACC-101")

        # Student 1 tries to reserve the same title they are holding
        ok, msg, res = ReservationService.create_reservation(self.student1.id, self.title1.isbn)
        self.assertFalse(ok)
        self.assertIn("already have an issued copy", msg.lower())

    # --- Test 6: Reservation cancellation shifts subsequent queue positions ---
    def test_reservation_cancellation_shifts_queue_positions(self):
        CirculationService.validate_and_issue_book(self.student1.id, "ACC-101")

        ok1, msg1, res1 = ReservationService.create_reservation(self.student2.id, self.title1.isbn)  # #1
        ok2, msg2, res2 = ReservationService.create_reservation(self.student3.id, self.title1.isbn)  # #2

        # Student 2 cancels reservation #1
        cancel_ok, cancel_msg = ReservationService.cancel_reservation(res1.id, requested_by_patron_id=self.student2.id)
        self.assertTrue(cancel_ok)

        # res1 status should be Cancelled
        self.assertEqual(res1.status, 'Cancelled')

        # Student 3's queue position should shift from #2 to #1!
        res3_updated = Reservation.query.get(res2.id)
        self.assertEqual(res3_updated.queue_position, 1)

if __name__ == '__main__':
    unittest.main()
