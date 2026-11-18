from datetime import datetime
from app.extensions import db

class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    patron_id = db.Column(db.Integer, db.ForeignKey('patrons.id'), nullable=False)
    borrow_id = db.Column(db.Integer, db.ForeignKey('borrow_transactions.id'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=False)  # 'DUE_SOON_T_MINUS_1', 'DUE_TODAY', 'OVERDUE', 'HOLD_READY', 'HOLD_EXPIRED'
    recipient_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='Sent')  # 'Sent', 'Failed', 'Simulated'

    patron = db.relationship('Patron', backref='notifications')

    def __repr__(self):
        return f"<NotificationLog {self.notification_type} to {self.recipient_email} at {self.sent_at}>"
