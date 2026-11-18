from datetime import datetime
from app.extensions import db

class Patron(db.Model):
    __tablename__ = 'patrons'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'Student', 'Faculty', 'Staff', 'Admin'
    department = db.Column(db.String(100), nullable=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)
    fine_balance = db.Column(db.Float, default=0.0)
    current_borrowed_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships for future sprints
    borrow_transactions = db.relationship('BorrowTransaction', backref='patron', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='patron', lazy='dynamic')

    def check_eligibility(self):
        """Validates if patron can borrow (active and fine <= 100)."""
        if not self.is_active:
            return False, "Patron account is deactivated."
        if self.fine_balance > 100.0:
            return False, f"Fine balance (Rs. {self.fine_balance:.2f}) exceeds permissible threshold of Rs. 100."
        return True, "Eligible"

    def __repr__(self):
        return f"<Patron {self.roll_number} - {self.name} ({self.role})>"


class BorrowingRules(db.Model):
    __tablename__ = 'borrowing_rules'

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), unique=True, nullable=False)
    max_books_allowed = db.Column(db.Integer, nullable=False)
    loan_duration_days = db.Column(db.Integer, nullable=False)
    max_renewals = db.Column(db.Integer, nullable=False)
    fine_per_day = db.Column(db.Float, default=2.0)
    max_fine_cap = db.Column(db.Float, default=200.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_rule_for_role(cls, role_name):
        return cls.query.filter_by(role=role_name).first()

    def __repr__(self):
        return f"<BorrowingRules {self.role}: {self.max_books_allowed} books, {self.loan_duration_days} days>"


class BookTitle(db.Model):
    __tablename__ = 'book_titles'

    isbn = db.Column(db.String(20), primary_key=True)  # Cleaned ISBN-10 or ISBN-13
    title = db.Column(db.String(255), nullable=False, index=True)
    authors = db.Column(db.String(255), nullable=True)
    publisher = db.Column(db.String(150), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    cover_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Physical copies relationship
    copies = db.relationship('BookCopy', backref='title_rel', cascade='all, delete-orphan', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='title_rel', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def total_copies(self):
        return self.copies.count()

    @property
    def available_copies(self):
        return self.copies.filter_by(status='Available').count()

    def __repr__(self):
        return f"<BookTitle {self.isbn} - {self.title}>"


class BookCopy(db.Model):
    __tablename__ = 'book_copies'

    accession_no = db.Column(db.String(50), primary_key=True)
    isbn = db.Column(db.String(20), db.ForeignKey('book_titles.isbn'), nullable=False, index=True)
    rack_no = db.Column(db.String(30), nullable=True)
    shelf_no = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), default='Available', nullable=False)  # 'Available', 'Issued', 'OnHold', 'Lost'
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrow_transactions = db.relationship('BorrowTransaction', backref='copy_rel', lazy='dynamic')

    def is_available(self):
        return self.status == 'Available'

    def __repr__(self):
        return f"<BookCopy {self.accession_no} ({self.status}) for ISBN {self.isbn}>"


# Skeleton tables to support relationships mapped in diagrams (Sprint 2/3 will fully populate them)
class BorrowTransaction(db.Model):
    __tablename__ = 'borrow_transactions'

    id = db.Column(db.Integer, primary_key=True)
    patron_id = db.Column(db.Integer, db.ForeignKey('patrons.id'), nullable=False)
    accession_no = db.Column(db.String(50), db.ForeignKey('book_copies.accession_no'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime, nullable=True)
    renewal_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='Active', nullable=False)  # 'Active', 'Returned', 'Overdue'


class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    patron_id = db.Column(db.Integer, db.ForeignKey('patrons.id'), nullable=False)
    isbn = db.Column(db.String(20), db.ForeignKey('book_titles.isbn'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    queue_position = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # 'Pending', 'Fulfilled', 'Cancelled', 'Expired'


class Fine(db.Model):
    __tablename__ = 'fines'

    id = db.Column(db.Integer, primary_key=True)
    borrow_id = db.Column(db.Integer, db.ForeignKey('borrow_transactions.id'), nullable=False)
    days_overdue = db.Column(db.Integer, default=0)
    amount = db.Column(db.Float, default=0.0)
    paid_status = db.Column(db.String(20), default='Unpaid')  # 'Unpaid', 'Paid'
