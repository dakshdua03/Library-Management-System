import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Patron, BorrowingRules, BookTitle, BookCopy, BorrowTransaction, Reservation, Fine

app = create_app()

def seed_rich_dataset():
    """Seeds a rich library dataset with multiple books, copies, patrons, active loans, and waitlists."""
    with app.app_context():
        db.create_all()

        # 1. Borrowing Rules (if not existing)
        if not BorrowingRules.query.first():
            rules_data = [
                BorrowingRules(role='Student', max_books_allowed=3, loan_duration_days=14, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Faculty', max_books_allowed=10, loan_duration_days=30, max_renewals=3, fine_per_day=2.0, max_fine_cap=200.0),
                BorrowingRules(role='Staff', max_books_allowed=5, loan_duration_days=21, max_renewals=2, fine_per_day=2.0, max_fine_cap=200.0),
            ]
            db.session.add_all(rules_data)
            db.session.commit()
            print("Borrowing Rules ensured.")

        # 2. Rich Patrons List
        patrons_to_add = [
            # Admins & Staff
            {"name": "Admin Officer", "role": "Admin", "department": "Library Administration", "roll_number": "ADMIN01", "email": "admin@lms.local", "phone": "9988776655", "is_active": True},
            {"name": "Chief Librarian", "role": "Librarian", "department": "Circulation Desk", "roll_number": "LIB01", "email": "librarian@lms.local", "phone": "9988776644", "is_active": True},
            {"name": "Asst. Librarian Ramesh", "role": "Librarian", "department": "Circulation Desk", "roll_number": "LIB02", "email": "ramesh.lib@lms.local", "phone": "9988776633", "is_active": True},
            
            # MCA Students (Daksh & Satyabrata + peers)
            {"name": "Daksh Dua", "role": "Student", "department": "SCIS - MCA", "roll_number": "25MCMC21", "email": "daksh@uohyd.ac.in", "phone": "9876543210", "is_active": True},
            {"name": "Satyabrata Rath", "role": "Student", "department": "SCIS - MCA", "roll_number": "25MCMC36", "email": "satyabrata@uohyd.ac.in", "phone": "9876543211", "is_active": True},
            {"name": "Aarav Sharma", "role": "Student", "department": "SCIS - MCA", "roll_number": "25MCMC05", "email": "aarav.sharma@uohyd.ac.in", "phone": "9876543213", "is_active": True},
            {"name": "Priya Nair", "role": "Student", "department": "SCIS - M.Tech CS", "roll_number": "25MCTC12", "email": "priya.nair@uohyd.ac.in", "phone": "9876543214", "is_active": True},
            {"name": "Rohan Verma", "role": "Student", "department": "School of Physics", "roll_number": "25PHPH08", "email": "rohan.v@uohyd.ac.in", "phone": "9876543215", "is_active": True},
            {"name": "Ananya Roy", "role": "Student", "department": "School of Chemistry", "roll_number": "25CHCH19", "email": "ananya.roy@uohyd.ac.in", "phone": "9876543216", "is_active": True},
            {"name": "Karthik Reddy", "role": "Student", "department": "School of Mathematics", "roll_number": "25MMMT22", "email": "karthik.r@uohyd.ac.in", "phone": "9876543217", "is_active": True},
            {"name": "Sneha Sen (Deactivated)", "role": "Student", "department": "SCIS - MCA", "roll_number": "25MCMC99", "email": "sneha.sen@uohyd.ac.in", "phone": "9876543218", "is_active": False},
            
            # Faculty
            {"name": "Dr. Salman Abdul Moiz", "role": "Faculty", "department": "SCIS", "roll_number": "FAC01", "email": "salman@uohyd.ac.in", "phone": "9876543220", "is_active": True},
            {"name": "Dr. Rajeev Wankar", "role": "Faculty", "department": "SCIS", "roll_number": "FAC02", "email": "wankar@uohyd.ac.in", "phone": "9876543221", "is_active": True},
            {"name": "Dr. Vineet C. P. Nair", "role": "Faculty", "department": "School of Physics", "roll_number": "FAC03", "email": "vineet@uohyd.ac.in", "phone": "9876543222", "is_active": True},
            
            # Staff
            {"name": "Suresh Kumar", "role": "Staff", "department": "SCIS Laboratory", "roll_number": "STF01", "email": "suresh.staff@uohyd.ac.in", "phone": "9876543230", "is_active": True},
            {"name": "Meena Kumari", "role": "Staff", "department": "Administration Office", "roll_number": "STF02", "email": "meena.staff@uohyd.ac.in", "phone": "9876543231", "is_active": True}
        ]

        for p_data in patrons_to_add:
            existing = Patron.query.filter_by(roll_number=p_data["roll_number"]).first()
            if not existing:
                patron = Patron(**p_data)
                db.session.add(patron)
        db.session.commit()
        print(f"Patrons seeded. Total: {Patron.query.count()}")

        # 3. Rich Catalog of Classical & Standard University Books
        books_to_add = [
            {
                "isbn": "9780133943030",
                "title": "Software Engineering (10th Edition)",
                "authors": "Ian Sommerville",
                "publisher": "Pearson Education",
                "year": 2015,
                "category": "Computer Science",
                "copies": [
                    {"accession_no": "ACC-101", "rack_no": "Rack B2", "shelf_no": "Shelf 3"},
                    {"accession_no": "ACC-102", "rack_no": "Rack B2", "shelf_no": "Shelf 3"},
                    {"accession_no": "ACC-103", "rack_no": "Rack B2", "shelf_no": "Shelf 3"},
                ]
            },
            {
                "isbn": "9780132350884",
                "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
                "authors": "Robert C. Martin",
                "publisher": "Prentice Hall",
                "year": 2008,
                "category": "Software Engineering",
                "copies": [
                    {"accession_no": "ACC-201", "rack_no": "Rack C1", "shelf_no": "Shelf 2"},
                    {"accession_no": "ACC-202", "rack_no": "Rack C1", "shelf_no": "Shelf 2"},
                ]
            },
            {
                "isbn": "9780262033848",
                "title": "Introduction to Algorithms (CLRS 3rd Edition)",
                "authors": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
                "publisher": "MIT Press",
                "year": 2009,
                "category": "Data Structures & Algorithms",
                "copies": [
                    {"accession_no": "ACC-301", "rack_no": "Rack A1", "shelf_no": "Shelf 1"},
                    {"accession_no": "ACC-302", "rack_no": "Rack A1", "shelf_no": "Shelf 1"},
                    {"accession_no": "ACC-303", "rack_no": "Rack A1", "shelf_no": "Shelf 2"},
                ]
            },
            {
                "isbn": "9780201633610",
                "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
                "authors": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
                "publisher": "Addison-Wesley Professional",
                "year": 1994,
                "category": "Software Architecture",
                "copies": [
                    {"accession_no": "ACC-401", "rack_no": "Rack C2", "shelf_no": "Shelf 4"},
                    {"accession_no": "ACC-402", "rack_no": "Rack C2", "shelf_no": "Shelf 4"},
                ]
            },
            {
                "isbn": "9780073523323",
                "title": "Database System Concepts (6th Edition)",
                "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
                "publisher": "McGraw-Hill",
                "year": 2010,
                "category": "Database Management",
                "copies": [
                    {"accession_no": "ACC-501", "rack_no": "Rack D1", "shelf_no": "Shelf 3"},
                    {"accession_no": "ACC-502", "rack_no": "Rack D1", "shelf_no": "Shelf 3"},
                ]
            },
            {
                "isbn": "9780131103627",
                "title": "The C Programming Language (2nd Edition ANSI C)",
                "authors": "Brian W. Kernighan, Dennis M. Ritchie",
                "publisher": "Prentice Hall",
                "year": 1988,
                "category": "Programming Languages",
                "copies": [
                    {"accession_no": "ACC-601", "rack_no": "Rack E1", "shelf_no": "Shelf 1"},
                    {"accession_no": "ACC-602", "rack_no": "Rack E1", "shelf_no": "Shelf 1"},
                ]
            },
            {
                "isbn": "9780132143011",
                "title": "Computer Networks (5th Edition)",
                "authors": "Andrew S. Tanenbaum, David J. Wetherall",
                "publisher": "Pearson",
                "year": 2010,
                "category": "Networking",
                "copies": [
                    {"accession_no": "ACC-701", "rack_no": "Rack F2", "shelf_no": "Shelf 2"},
                ]
            },
            {
                "isbn": "9780133591620",
                "title": "Operating Systems: Internals and Design Principles (8th Edition)",
                "authors": "William Stallings",
                "publisher": "Pearson",
                "year": 2014,
                "category": "Operating Systems",
                "copies": [
                    {"accession_no": "ACC-801", "rack_no": "Rack F1", "shelf_no": "Shelf 3"},
                    {"accession_no": "ACC-802", "rack_no": "Rack F1", "shelf_no": "Shelf 3"},
                ]
            },
            {
                "isbn": "9780134685991",
                "title": "Effective Java (3rd Edition)",
                "authors": "Joshua Bloch",
                "publisher": "Addison-Wesley Professional",
                "year": 2017,
                "category": "Software Engineering",
                "copies": [
                    {"accession_no": "ACC-901", "rack_no": "Rack C1", "shelf_no": "Shelf 3"},
                ]
            },
            {
                "isbn": "9780262035613",
                "title": "Deep Learning (Adaptive Computation and Machine Learning)",
                "authors": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
                "publisher": "MIT Press",
                "year": 2016,
                "category": "Artificial Intelligence",
                "copies": [
                    {"accession_no": "ACC-1001", "rack_no": "Rack G1", "shelf_no": "Shelf 2"},
                    {"accession_no": "ACC-1002", "rack_no": "Rack G1", "shelf_no": "Shelf 2"},
                ]
            }
        ]

        for b_data in books_to_add:
            title = BookTitle.query.get(b_data["isbn"])
            if not title:
                title = BookTitle(
                    isbn=b_data["isbn"],
                    title=b_data["title"],
                    authors=b_data["authors"],
                    publisher=b_data["publisher"],
                    year=b_data["year"],
                    category=b_data["category"],
                    cover_path=None
                )
                db.session.add(title)
                db.session.flush()

            for c_data in b_data["copies"]:
                copy = BookCopy.query.get(c_data["accession_no"])
                if not copy:
                    new_copy = BookCopy(
                        accession_no=c_data["accession_no"],
                        isbn=title.isbn,
                        rack_no=c_data["rack_no"],
                        shelf_no=c_data["shelf_no"],
                        status="Available"
                    )
                    db.session.add(new_copy)
        db.session.commit()
        print(f"Books & Copies seeded. Titles: {BookTitle.query.count()}, Copies: {BookCopy.query.count()}")

        # 4. Seed Realistic Transactions (Active Loans, Overdue Loans with Fines, Waitlists)
        # Check if loans exist
        if BorrowTransaction.query.count() == 0:
            now = datetime.now()
            p_daksh = Patron.query.filter_by(roll_number="25MCMC21").first()
            p_satya = Patron.query.filter_by(roll_number="25MCMC36").first()
            p_aarav = Patron.query.filter_by(roll_number="25MCMC05").first()
            p_priya = Patron.query.filter_by(roll_number="25MCTC12").first()
            p_rohan = Patron.query.filter_by(roll_number="25PHPH08").first()
            p_fac1 = Patron.query.filter_by(roll_number="FAC01").first()

            # Active loan 1: Daksh has Software Engineering (ACC-101), issued 5 days ago, due in 9 days
            c101 = BookCopy.query.get("ACC-101")
            c101.status = 'Issued'
            tx1 = BorrowTransaction(
                patron_id=p_daksh.id,
                accession_no="ACC-101",
                issue_date=now - timedelta(days=5),
                due_date=now + timedelta(days=9),
                status='Active',
                renewal_count=0
            )
            p_daksh.current_borrowed_count = 1

            # Active loan 2: Daksh has Clean Code (ACC-201), issued 2 days ago, due in 12 days
            c201 = BookCopy.query.get("ACC-201")
            c201.status = 'Issued'
            tx2 = BorrowTransaction(
                patron_id=p_daksh.id,
                accession_no="ACC-201",
                issue_date=now - timedelta(days=2),
                due_date=now + timedelta(days=12),
                status='Active',
                renewal_count=0
            )
            p_daksh.current_borrowed_count = 2

            # Active loan 3 (OVERDUE for demo report!): Rohan has Tanenbaum Networks (ACC-701) - 6 days overdue
            c701 = BookCopy.query.get("ACC-701")
            c701.status = 'Issued'
            tx3 = BorrowTransaction(
                patron_id=p_rohan.id,
                accession_no="ACC-701",
                issue_date=now - timedelta(days=20),
                due_date=now - timedelta(days=6),  # Overdue by 6 days!
                status='Active',
                renewal_count=0
            )
            p_rohan.current_borrowed_count = 1
            # Add fine record: 6 days * Rs. 2 = Rs. 12
            fine1 = Fine(borrow_id=3, days_overdue=6, amount=12.0, paid_status='Unpaid')
            p_rohan.fine_balance = 12.0
            db.session.add(fine1)

            # Active loan 4: Satyabrata has CLRS Algorithms (ACC-301)
            c301 = BookCopy.query.get("ACC-301")
            c301.status = 'Issued'
            tx4 = BorrowTransaction(
                patron_id=p_satya.id,
                accession_no="ACC-301",
                issue_date=now - timedelta(days=7),
                due_date=now + timedelta(days=7),
                status='Active',
                renewal_count=1
            )
            p_satya.current_borrowed_count = 1

            # Active loan 5: Priya has Deep Learning (ACC-1001)
            c1001 = BookCopy.query.get("ACC-1001")
            c1001.status = 'Issued'
            tx5 = BorrowTransaction(
                patron_id=p_priya.id,
                accession_no="ACC-1001",
                issue_date=now - timedelta(days=3),
                due_date=now + timedelta(days=11),
                status='Active',
                renewal_count=0
            )
            p_priya.current_borrowed_count = 1

            # Active loan 6 (OVERDUE for demo report): Aarav has Effective Java (ACC-901) - only 1 copy and issued!
            c901 = BookCopy.query.get("ACC-901")
            c901.status = 'Issued'
            tx6 = BorrowTransaction(
                patron_id=p_aarav.id,
                accession_no="ACC-901",
                issue_date=now - timedelta(days=18),
                due_date=now - timedelta(days=4),  # 4 days overdue
                status='Active',
                renewal_count=0
            )
            p_aarav.current_borrowed_count = 1
            fine2 = Fine(borrow_id=6, days_overdue=4, amount=8.0, paid_status='Unpaid')
            p_aarav.fine_balance = 8.0
            db.session.add(fine2)

            # Historical completed returns (for Popular Books report)
            past_txs = [
                BorrowTransaction(patron_id=p_fac1.id, accession_no="ACC-102", issue_date=now - timedelta(days=40), due_date=now - timedelta(days=10), return_date=now - timedelta(days=11), status='Returned'),
                BorrowTransaction(patron_id=p_satya.id, accession_no="ACC-103", issue_date=now - timedelta(days=35), due_date=now - timedelta(days=21), return_date=now - timedelta(days=20), status='Returned'),
                BorrowTransaction(patron_id=p_daksh.id, accession_no="ACC-302", issue_date=now - timedelta(days=25), due_date=now - timedelta(days=11), return_date=now - timedelta(days=12), status='Returned'),
                BorrowTransaction(patron_id=p_priya.id, accession_no="ACC-401", issue_date=now - timedelta(days=30), due_date=now - timedelta(days=16), return_date=now - timedelta(days=15), status='Returned'),
                BorrowTransaction(patron_id=p_aarav.id, accession_no="ACC-501", issue_date=now - timedelta(days=28), due_date=now - timedelta(days=14), return_date=now - timedelta(days=14), status='Returned'),
            ]

            db.session.add_all([tx1, tx2, tx3, tx4, tx5, tx6] + past_txs)

            # 5. Waitlist Reservations (For Effective Java ISBN 9780134685991 where 0/1 copies available)
            # Satyabrata is Queue #1, Daksh is Queue #2
            res1 = Reservation(
                patron_id=p_satya.id,
                isbn="9780134685991",
                request_date=now - timedelta(days=2),
                queue_position=1,
                status='Pending'
            )
            res2 = Reservation(
                patron_id=p_daksh.id,
                isbn="9780134685991",
                request_date=now - timedelta(days=1),
                queue_position=2,
                status='Pending'
            )
            db.session.add_all([res1, res2])
            db.session.commit()
            print("Realistic circulation transactions, overdue fines, and FCFS waitlists seeded successfully!")

if __name__ == '__main__':
    seed_rich_dataset()
