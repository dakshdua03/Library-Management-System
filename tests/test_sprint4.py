import unittest
import io
from datetime import datetime, timedelta
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy, BorrowTransaction, Reservation
from app.notification_model import NotificationLog
from app.bulk_service import process_bulk_csv
from app.notification_service import NotificationService
from app.circulation_service import CirculationService

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class Sprint4AcceptanceTests(unittest.TestCase):
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
        self.admin = Patron(name="Admin", role="Admin", roll_number="ADMIN01", email="admin@test.com", department="Administration")
        self.librarian = Patron(name="Librarian", role="Librarian", roll_number="LIB01", email="lib@test.com", department="Library")
        self.student = Patron(name="Student Daksh", role="Student", roll_number="25MCMC21", email="daksh@uohyd.ac.in", department="SCIS")
        self.student2 = Patron(name="Student Satyabrata", role="Student", roll_number="25MCMC36", email="satyabrata@uohyd.ac.in", department="SCIS")
        db.session.add_all([self.admin, self.librarian, self.student, self.student2])

        # Seed an initial book
        self.title1 = BookTitle(isbn="9780133943030", title="Software Engineering", authors="Ian Sommerville", category="Computer Science")
        self.copy1 = BookCopy(accession_no="ACC-101", isbn="9780133943030", rack_no="Rack B2", shelf_no="Shelf 3", status="Available")
        db.session.add_all([self.title1, self.copy1])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_as(self, roll_number):
        return self.client.post('/auth/login', data={'roll_number': roll_number}, follow_redirects=True)

    # --- Test 1: Bulk CSV processing adds books & rejects duplicates row-wise ---
    def test_bulk_csv_processing_with_success_and_failure_summary(self):
        csv_data = """ISBN,Accession Number,Rack,Shelf,Title,Author
9780132350884,ACC-CSV-1,Rack A1,Shelf 1,Clean Code,Robert C. Martin
9780133943030,ACC-101,Rack B2,Shelf 3,Duplicate Acc Book,Ian Sommerville
9780201633610,ACC-CSV-2,Rack A2,Shelf 2,Design Patterns,Erich Gamma
"""
        file_stream = io.BytesIO(csv_data.encode("utf-8"))
        summary = process_bulk_csv(file_stream)

        # Total 3 rows: 2 valid, 1 duplicate accession number ACC-101
        self.assertEqual(summary['total_rows'], 3)
        self.assertEqual(summary['success_count'], 2)
        self.assertEqual(summary['failed_count'], 1)

        # Check failure reason
        self.assertIn("already exists", summary['errors'][0]['reason'])

        # Verify added copies in DB
        copy1 = BookCopy.query.get("ACC-CSV-1")
        self.assertIsNotNone(copy1)
        self.assertEqual(copy1.title_rel.title, "Clean Code")

    # --- Test 2: Cron pipeline sends T-1 reminder email 1 day before due date ---
    def test_cron_pipeline_t_minus_1_reminder(self):
        # Issue loan due tomorrow
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx = BorrowTransaction.query.filter_by(status='Active').first()
        tx.due_date = datetime.now() + timedelta(days=1)
        db.session.commit()

        sent_count = NotificationService.run_daily_loan_reminders()
        self.assertEqual(sent_count, 1)

        log = NotificationLog.query.filter_by(notification_type='DUE_SOON_T_MINUS_1').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.recipient_email, "daksh@uohyd.ac.in")
        self.assertIn("due tomorrow", log.subject.lower())

    # --- Test 3: Cron pipeline sends Due Date reminder on due date ---
    def test_cron_pipeline_due_today_reminder(self):
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx = BorrowTransaction.query.filter_by(status='Active').first()
        tx.due_date = datetime.now()  # Due today
        db.session.commit()

        sent_count = NotificationService.run_daily_loan_reminders()
        self.assertEqual(sent_count, 1)

        log = NotificationLog.query.filter_by(notification_type='DUE_TODAY').first()
        self.assertIsNotNone(log)
        self.assertIn("due today", log.subject.lower())

    # --- Test 4: Overdue loan gets exactly one email per day with calculated fine ---
    def test_cron_pipeline_daily_overdue_alert_capped_once_per_day(self):
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx = BorrowTransaction.query.filter_by(status='Active').first()
        tx.due_date = datetime.now() - timedelta(days=5)  # 5 days overdue
        db.session.commit()

        # Run 1st time
        sent1 = NotificationService.run_daily_loan_reminders()
        self.assertEqual(sent1, 1)

        log = NotificationLog.query.filter_by(notification_type='OVERDUE').first()
        self.assertIsNotNone(log)
        self.assertIn("5 days overdue", log.subject.lower())
        self.assertIn("Rs. 10.00", log.body)

        # Run 2nd time on the same day -> Must NOT send duplicate email
        sent2 = NotificationService.run_daily_loan_reminders()
        self.assertEqual(sent2, 0)

    # --- Test 5: 48-hour uncollected reservation hold expires and notifies next in line ---
    def test_uncollected_hold_expires_after_48_hours(self):
        copy = BookCopy.query.get("ACC-101")
        copy.status = 'OnHold'

        # Res 1 for Student 1 (placed > 48h ago)
        res1 = Reservation(
            patron_id=self.student.id,
            isbn=copy.isbn,
            request_date=datetime.now() - timedelta(hours=50),
            queue_position=1,
            status='Pending'
        )
        # Res 2 for Student 2
        res2 = Reservation(
            patron_id=self.student2.id,
            isbn=copy.isbn,
            request_date=datetime.now(),
            queue_position=2,
            status='Pending'
        )
        db.session.add_all([res1, res2])
        db.session.commit()

        expired_count = NotificationService.process_expired_reservation_holds()
        self.assertEqual(expired_count, 1)

        # Res 1 is Expired
        res1_after = Reservation.query.get(res1.id)
        self.assertEqual(res1_after.status, 'Expired')

        # Res 2 is now #1 and notified
        res2_after = Reservation.query.get(res2.id)
        self.assertEqual(res2_after.queue_position, 1)

        notif = NotificationLog.query.filter_by(notification_type='HOLD_READY').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient_email, "satyabrata@uohyd.ac.in")

    # --- Test 6: Overdue CSV report generation & student role blocking ---
    def test_overdue_report_and_csv_export(self):
        # Create an overdue loan
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        tx = BorrowTransaction.query.filter_by(status='Active').first()
        tx.due_date = datetime.now() - timedelta(days=4)
        db.session.commit()

        # Admin can view report and export CSV
        self.login_as("ADMIN01")
        resp = self.client.get('/reports/overdue')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Student Daksh', resp.data)
        self.assertIn(b'25MCMC21', resp.data)

        # CSV Export
        csv_resp = self.client.get('/reports/overdue?export=csv')
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.content_type, 'text/csv; charset=utf-8')
        self.assertIn(b'25MCMC21', csv_resp.data)

        # Student is blocked from accessing reports
        self.login_as("25MCMC21")
        stud_resp = self.client.get('/reports/overdue', follow_redirects=True)
        self.assertIn(b'Access denied', stud_resp.data)

    # --- Test 7: Popular books report aggregates issue counts & CSV export ---
    def test_popular_books_report_and_csv_export(self):
        # Issue and return to create transaction records
        CirculationService.validate_and_issue_book(self.student.id, "ACC-101")
        CirculationService.process_return("ACC-101")

        self.login_as("ADMIN01")
        resp = self.client.get('/reports/popular?days=30')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Software Engineering', resp.data)

        # CSV Export
        csv_resp = self.client.get('/reports/popular?days=30&export=csv')
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn(b'Software Engineering', csv_resp.data)

        # Student is blocked
        self.login_as("25MCMC21")
        stud_resp = self.client.get('/reports/popular', follow_redirects=True)
        self.assertIn(b'Access denied', stud_resp.data)

if __name__ == '__main__':
    unittest.main()
