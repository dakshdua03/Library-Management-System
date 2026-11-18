import unittest
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy
from run import seed_initial_data

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class Sprint1AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed initial rules and demo accounts
        with self.app.test_request_context():
            rules_data = [
                BorrowingRules(role='Student', max_books_allowed=3, loan_duration_days=14, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Faculty', max_books_allowed=10, loan_duration_days=30, max_renewals=3, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Staff', max_books_allowed=5, loan_duration_days=21, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
            ]
            db.session.add_all(rules_data)

            admin = Patron(name="Admin", role="Admin", roll_number="ADMIN01", email="admin@test.com")
            student = Patron(name="Student", role="Student", roll_number="25MCMC21", email="student@test.com")
            librarian = Patron(name="Librarian", role="Librarian", roll_number="LIB01", email="lib@test.com")
            db.session.add_all([admin, student, librarian])
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_as(self, roll_number):
        return self.client.post('/auth/login', data={'roll_number': roll_number}, follow_redirects=True)

    # --- Module 1: Patron Acceptance Tests ---
    def test_admin_can_create_patron(self):
        self.login_as("ADMIN01")
        resp = self.client.post('/patrons/add', data={
            'name': 'New Student',
            'role': 'Student',
            'roll_number': '25MCMC99',
            'email': 'newstudent@uohyd.ac.in',
            'department': 'SCIS',
            'phone': '9876543299'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        p = Patron.query.filter_by(roll_number='25MCMC99').first()
        self.assertIsNotNone(p)
        self.assertEqual(p.name, 'New Student')

    def test_duplicate_roll_number_and_email_rejected(self):
        self.login_as("ADMIN01")
        # Duplicate roll number
        resp = self.client.post('/patrons/add', data={
            'name': 'Duplicate Roll',
            'role': 'Student',
            'roll_number': '25MCMC21',  # already exists
            'email': 'unique1@uohyd.ac.in',
            'department': 'SCIS'
        }, follow_redirects=True)
        self.assertIn(b'already registered', resp.data)

        # Duplicate email
        resp2 = self.client.post('/patrons/add', data={
            'name': 'Duplicate Email',
            'role': 'Student',
            'roll_number': '25MCMC88',
            'email': 'student@test.com',  # already exists
            'department': 'SCIS'
        }, follow_redirects=True)
        self.assertIn(b'already associated', resp2.data)

    def test_student_blocked_from_admin_patron_page(self):
        self.login_as("25MCMC21")  # Log in as Student
        resp = self.client.get('/patrons/add', follow_redirects=True)
        self.assertIn(b'Access denied', resp.data)

    def test_patron_deactivation_preserves_record(self):
        self.login_as("ADMIN01")
        student = Patron.query.filter_by(roll_number='25MCMC21').first()
        self.assertTrue(student.is_active)

        # Toggle to deactivate
        self.client.post(f'/patrons/toggle-status/{student.id}', follow_redirects=True)
        student_after = Patron.query.filter_by(roll_number='25MCMC21').first()
        self.assertFalse(student_after.is_active)
        # Verify eligibility check fails
        eligible, reason = student_after.check_eligibility()
        self.assertFalse(eligible)

    # --- Module 1 (Rules): Borrowing Rules Acceptance Tests ---
    def test_borrowing_rules_modifiable_from_admin_panel(self):
        self.login_as("ADMIN01")
        resp = self.client.post('/patrons/rules', data={
            'roles': 'Student',
            'max_books_Student': 5,  # modified from 3 to 5
            'duration_Student': 20,
            'renewals_Student': 3,
            'fine_Student': 3.5,
            'max_books_Faculty': 10,
            'duration_Faculty': 30,
            'renewals_Faculty': 3,
            'fine_Faculty': 2.0,
            'max_books_Staff': 5,
            'duration_Staff': 21,
            'renewals_Staff': 2,
            'fine_Staff': 2.0
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        student_rule = BorrowingRules.query.filter_by(role='Student').first()
        self.assertEqual(student_rule.max_books_allowed, 5)
        self.assertEqual(student_rule.fine_per_day, 3.5)

    def test_patron_ineligible_when_fine_exceeds_100(self):
        student = Patron.query.filter_by(roll_number='25MCMC21').first()
        student.fine_balance = 150.0  # Exceeds 100
        eligible, reason = student.check_eligibility()
        self.assertFalse(eligible)
        self.assertIn('exceeds permissible threshold', reason)

    # --- Module 2: Catalog & Copies Acceptance Tests ---
    def test_manual_book_registration_fallback(self):
        self.login_as("LIB01")
        resp = self.client.post('/catalog/manual-add', data={
            'isbn': '9780132350884',
            'title': 'Clean Code',
            'authors': 'Robert C. Martin',
            'publisher': 'Prentice Hall',
            'year': 2008,
            'category': 'Software Engineering',
            'accession_no': 'ACC-2001',
            'rack_no': 'Rack C1',
            'shelf_no': 'Shelf 4'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        title = BookTitle.query.get('9780132350884')
        self.assertIsNotNone(title)
        self.assertEqual(title.title, 'Clean Code')
        self.assertEqual(title.total_copies, 1)
        self.assertEqual(title.available_copies, 1)

    def test_duplicate_accession_number_rejected(self):
        self.login_as("LIB01")
        # Add first book with ACC-3001
        self.client.post('/catalog/manual-add', data={
            'isbn': '9781111111111',
            'title': 'Test Book 1',
            'accession_no': 'ACC-3001'
        }, follow_redirects=True)

        # Attempt to add another copy/book with same ACC-3001
        resp = self.client.post('/catalog/manual-add', data={
            'isbn': '9782222222222',
            'title': 'Test Book 2',
            'accession_no': 'ACC-3001'
        }, follow_redirects=True)
        self.assertIn(b'already exists', resp.data)

if __name__ == '__main__':
    unittest.main()
