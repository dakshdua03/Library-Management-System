import os
from app import create_app
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy

app = create_app()

def seed_initial_data():
    """Initializes tables and seeds default patrons & borrowing rules if empty."""
    with app.app_context():
        db.create_all()

        # Seed Borrowing Rules per Product & Sprint Backlog specifications:
        # Students: 3 books / 14 days / 2 renewals
        # Faculty: 10 books / 30 days / 3 renewals
        # Staff: 5 books / 21 days / 2 renewals
        # Fine: Rs. 2/day, capped at Rs. 200
        if not BorrowingRules.query.first():
            rules_data = [
                BorrowingRules(role='Student', max_books_allowed=3, loan_duration_days=14, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Faculty', max_books_allowed=10, loan_duration_days=30, max_renewals=3, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Staff', max_books_allowed=5, loan_duration_days=21, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
            ]
            db.session.add_all(rules_data)
            db.session.commit()
            print("Default Borrowing Rules seeded.")

        # Seed Initial Demo Patrons (Admin, Librarian, Students, Faculty)
        if not Patron.query.first():
            patrons_data = [
                Patron(name="Admin Officer", role="Admin", department="Library Administration", roll_number="ADMIN01", email="admin@lms.local", phone="9988776655"),
                Patron(name="Chief Librarian", role="Librarian", department="Circulation Desk", roll_number="LIB01", email="librarian@lms.local", phone="9988776644"),
                Patron(name="Daksh Dua", role="Student", department="SCIS - MCA", roll_number="25MCMC21", email="daksh@uohyd.ac.in", phone="9876543210"),
                Patron(name="Satyabrata Rath", role="Student", department="SCIS - MCA", roll_number="25MCMC36", email="satyabrata@uohyd.ac.in", phone="9876543211"),
                Patron(name="Dr. Faculty Advisor", role="Faculty", department="SCIS", roll_number="FAC01", email="faculty@uohyd.ac.in", phone="9876543212")
            ]
            db.session.add_all(patrons_data)
            db.session.commit()
            print("Default Demo Patrons seeded.")

        # Seed an initial classic Software Engineering reference book
        if not BookTitle.query.first():
            se_title = BookTitle(
                isbn="9780133943030",
                title="Software Engineering (10th Edition)",
                authors="Ian Sommerville",
                publisher="Pearson",
                year=2015,
                category="Computer Science",
                cover_path=None
            )
            db.session.add(se_title)
            db.session.flush()

            # Physical copies
            copy1 = BookCopy(accession_no="ACC-101", isbn=se_title.isbn, rack_no="Rack B2", shelf_no="Shelf 3", status="Available")
            copy2 = BookCopy(accession_no="ACC-102", isbn=se_title.isbn, rack_no="Rack B2", shelf_no="Shelf 3", status="Available")
            db.session.add_all([copy1, copy2])
            db.session.commit()
            print("Default reference book title seeded.")

if __name__ == '__main__':
    seed_initial_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
