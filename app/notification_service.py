import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from flask import current_app
from app.extensions import db
from app.models import Patron, BorrowTransaction, BookCopy, Reservation
from app.notification_model import NotificationLog

class NotificationService:

    @staticmethod
    def send_email_alert(recipient_email, subject, html_body, patron_id, borrow_id=None, notif_type="GENERAL"):
        """
        Sends email via SMTP if configured, or logs to database table for audit/demo view.
        Always logs into NotificationLog for reliable verification.
        """
        status = "Sent"
        smtp_host = os.environ.get('MAIL_SERVER')
        smtp_port = int(os.environ.get('MAIL_PORT', 587))
        smtp_user = os.environ.get('MAIL_USERNAME')
        smtp_pass = os.environ.get('MAIL_PASSWORD')

        if smtp_host and smtp_user and smtp_pass:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = smtp_user
                msg["To"] = recipient_email
                msg.attach(MIMEText(html_body, "html"))

                with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, recipient_email, msg.as_string())
            except Exception as e:
                current_app.logger.warning(f"SMTP dispatch error to {recipient_email}: {e}")
                status = "Failed"
        else:
            status = "Simulated"  # Logged locally in test/offline environment

        log = NotificationLog(
            patron_id=patron_id,
            borrow_id=borrow_id,
            notification_type=notif_type,
            recipient_email=recipient_email,
            subject=subject,
            body=html_body,
            sent_at=datetime.utcnow(),
            status=status
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def run_daily_loan_reminders():
        """
        Sommerville Pipe-and-Filter Architecture (Architecture 5 Fig 6.13):
        Scans active loans table daily:
        - Books due in 1 day (T-1 Reminder)
        - Books due today (Due Date Reminder)
        - Books currently overdue (Daily Overdue Alert, maximum 1 email/day/book)
        Returns counts of emails dispatched.
        """
        now = datetime.now()
        today_date = now.date()
        one_day_ahead = today_date + timedelta(days=1)

        active_loans = BorrowTransaction.query.filter_by(status='Active').all()
        reminders_sent = 0

        for loan in active_loans:
            patron = Patron.query.get(loan.patron_id)
            copy = BookCopy.query.get(loan.accession_no)
            due_d = loan.due_date.date()

            # Rule 1: Due in 1 day (T-1)
            if due_d == one_day_ahead:
                # Check if already notified today for this loan
                already_notified = NotificationLog.query.filter(
                    NotificationLog.borrow_id == loan.id,
                    NotificationLog.notification_type == 'DUE_SOON_T_MINUS_1',
                    db.func.date(NotificationLog.sent_at) == today_date
                ).first()

                if not already_notified:
                    subject = f"Library Reminder: \"{copy.title_rel.title}\" is due tomorrow!"
                    body = f"""
                    <p>Dear {patron.name},</p>
                    <p>This is a friendly reminder that your borrowed book <strong>{copy.title_rel.title}</strong> (Accession: {copy.accession_no}) is due tomorrow on <strong>{loan.due_date.strftime('%d-%m-%Y')}</strong>.</p>
                    <p>Please return or renew it to avoid overdue fines of Rs. 2.00 / day.</p>
                    """
                    NotificationService.send_email_alert(patron.email, subject, body, patron.id, loan.id, 'DUE_SOON_T_MINUS_1')
                    reminders_sent += 1

            # Rule 2: Due Today
            elif due_d == today_date:
                already_notified = NotificationLog.query.filter(
                    NotificationLog.borrow_id == loan.id,
                    NotificationLog.notification_type == 'DUE_TODAY',
                    db.func.date(NotificationLog.sent_at) == today_date
                ).first()

                if not already_notified:
                    subject = f"Library Notice: \"{copy.title_rel.title}\" is due TODAY!"
                    body = f"""
                    <p>Dear {patron.name},</p>
                    <p>Your borrowed book <strong>{copy.title_rel.title}</strong> is due today, <strong>{loan.due_date.strftime('%d-%m-%Y')}</strong>.</p>
                    <p>Kindly return it to the circulation counter before library closing hours.</p>
                    """
                    NotificationService.send_email_alert(patron.email, subject, body, patron.id, loan.id, 'DUE_TODAY')
                    reminders_sent += 1

            # Rule 3: Currently Overdue (Daily Alert, max 1/day/book)
            elif due_d < today_date:
                already_notified = NotificationLog.query.filter(
                    NotificationLog.borrow_id == loan.id,
                    NotificationLog.notification_type == 'OVERDUE',
                    db.func.date(NotificationLog.sent_at) == today_date
                ).first()

                if not already_notified:
                    overdue_days = (today_date - due_d).days
                    est_fine = min(overdue_days * 2.0, 200.0)
                    subject = f"URGENT Overdue Notice: \"{copy.title_rel.title}\" ({overdue_days} days overdue)"
                    body = f"""
                    <p>Dear {patron.name},</p>
                    <p>Your borrowed book <strong>{copy.title_rel.title}</strong> was due on {loan.due_date.strftime('%d-%m-%Y')} and is now <strong>{overdue_days} days overdue</strong>.</p>
                    <p>Current accrued fine: <strong>Rs. {est_fine:.2f}</strong> (at Rs. 2/day, max cap Rs. 200.00).</p>
                    <p>Please return the book immediately to avoid account suspension.</p>
                    """
                    NotificationService.send_email_alert(patron.email, subject, body, patron.id, loan.id, 'OVERDUE')
                    reminders_sent += 1

        return reminders_sent

    @staticmethod
    def process_expired_reservation_holds():
        """
        48-hour expiration rule:
        If a waitlisted book was held for a student and they haven't collected it within 48 hours,
        cancel their hold and notify the next student in line!
        """
        now = datetime.now()
        expired_cutoff = now - timedelta(hours=48)
        expired_count = 0

        # Find copies marked 'OnHold' with top pending reservation older than 48 hours
        held_copies = BookCopy.query.filter_by(status='OnHold').all()
        for copy in held_copies:
            top_res = (
                Reservation.query.filter_by(isbn=copy.isbn, status='Pending')
                .order_by(Reservation.queue_position.asc())
                .first()
            )
            # If hold request was placed over 48 hours ago
            if top_res and top_res.request_date < expired_cutoff:
                # Cancel this patron's hold
                top_res.status = 'Expired'
                patron_expired = Patron.query.get(top_res.patron_id)
                NotificationService.send_email_alert(
                    patron_expired.email,
                    f"Reservation Expired: {copy.title_rel.title}",
                    f"<p>Dear {patron_expired.name}, your 48-hour pickup window for {copy.title_rel.title} has expired.</p>",
                    patron_expired.id,
                    None,
                    'HOLD_EXPIRED'
                )

                # Check if next patron exists in line
                next_res = (
                    Reservation.query.filter_by(isbn=copy.isbn, status='Pending')
                    .order_by(Reservation.queue_position.asc())
                    .first()
                )
                if next_res:
                    next_res.queue_position = 1
                    patron_next = Patron.query.get(next_res.patron_id)
                    NotificationService.send_email_alert(
                        patron_next.email,
                        f"Book Ready for Pickup: {copy.title_rel.title}",
                        f"<p>Dear {patron_next.name}, your reserved book {copy.title_rel.title} is now ready! Please collect within 48 hours.</p>",
                        patron_next.id,
                        None,
                        'HOLD_READY'
                    )
                else:
                    copy.status = 'Available'

                db.session.commit()
                expired_count += 1

        return expired_count
