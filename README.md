# Library Management System (LMS)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-SQLite%203-lightgrey.svg)](https://sqlite.org/)
[![Tests Passing](https://img.shields.io/badge/tests-32%2F32%20passing-brightgreen.svg)]()

A complete, production-grade Library Management System implemented in **Python**, **Flask**, **SQLite**, and **Bootstrap 5**. Designed strictly to match **Ian Sommerville's Software Engineering Architecture Patterns** and the exact sprint acceptance criteria defined in the *Product and Sprint Backlog*.

Developed by: **Daksh Dua** (`25MCMC21`), Master of Computer Applications (MCA), University of Hyderabad (SCIS).

---

> [!IMPORTANT]
> **Faculty Presentation & Viva Guide:**  
> A comprehensive guide for faculty evaluation, covering the architecture diagrams, feature matrix, and automated test walkthrough, is available in [FACULTY_PRESENTATION_GUIDE.md](FACULTY_PRESENTATION_GUIDE.md).

---

## Architecture & Sorted Diagrams Gallery

All 25 software engineering diagrams are organized into categorized subdirectories under `diagrams/`:

- `diagrams/01_Architectural_Patterns/`: MVC, Sommerville Layered (LIBSYS), Repository, Client-Server, Pipe-and-Filter, and Detailed Layered (MHCPMS).
- `diagrams/02_Communication_Diagrams/`: Issue, Return, Renew, Reserve, and Add Book via ISBN.
- `diagrams/03_Sequence_Diagrams/`: Detailed 5-point issue sequence, return with automated fines, multi-guard renewal, FCFS waitlist queue, and dual-API cataloging.
- `diagrams/04_Class_Diagrams/`: Refined domain object model (Patron, BorrowingRules, BookTitle, BookCopy, BorrowTransaction, Reservation, FineRecord).
- `diagrams/05_Analysis_And_Design/`: Transaction-centered DFD, Transform Analysis (In-Out mapping), and Software Structure Chart.

---

## Project Structure

```
Implementation/
├── FACULTY_PRESENTATION_GUIDE.md # Complete viva, diagram & test walkthrough guide
├── README.md                    # Project overview & quickstart
├── requirements.txt             # Locked Python dependencies
├── run.py                       # App entrypoint & automated database initialization
├── seed_data.py                 # Rich university dataset seeder
├── lms.db                       # SQLite relational database
├── diagrams/                    # Categorized architecture & design diagrams (25 PNGs)
│   ├── 01_Architectural_Patterns/
│   ├── 02_Communication_Diagrams/
│   ├── 03_Sequence_Diagrams/
│   ├── 04_Class_Diagrams/
│   └── 05_Analysis_And_Design/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration (SQLite DB path, media paths, secrets)
│   ├── extensions.py            # SQLAlchemy instance
│   ├── models.py                # Database models (Patron, BorrowingRules, BookTitle, BookCopy, etc.)
│   ├── circulation_service.py   # 5-point issue validations, auto fine & renewal engine
│   ├── reservation_service.py   # FCFS waitlist queue manager & hold re-balancing
│   ├── notification_service.py  # Sommerville Pipe-and-Filter automated reminder pipeline
│   ├── bulk_service.py          # CSV parser & bulk book onboarding
│   ├── services.py              # ISBN API integration (OpenLibrary & Google Books) & cover downloader
│   ├── auth_helpers.py          # Session authentication & @role_required decorators
│   ├── routes/
│   │   ├── auth.py              # Login / Logout with session handling
│   │   ├── main.py              # Dashboard & offline media serving
│   │   ├── patrons.py           # Patron management & dynamic Borrowing Rules editor
│   │   ├── catalog.py           # ISBN auto-fetch, manual entry fallback, copy tracker & bulk CSV
│   │   ├── circulation.py       # Circulation desk (Issue, Return, Active loans)
│   │   ├── selfservice.py       # Public catalog search, book details & waitlist queues
│   │   ├── reports.py           # Overdue & Top-20 popular CSV reports & notification audit
│   │   └── qa.py                # Interactive Acceptance Test verification runner (/qa)
│   └── templates/
│       ├── base.html            # Core layout with Bootstrap 5 & navigation
│       ├── dashboard.html       # Overview dashboard with stats & role-based quick actions
│       ├── auth/                # Login templates
│       ├── patrons/             # Patron management & rules templates
│       ├── catalog/             # Cataloging, ISBN auto-fetch & CSV templates
│       ├── circulation/         # Issue, Return & Active loans templates
│       ├── selfservice/         # Search, Book details & My reservations templates
│       ├── reports/             # Overdue, Popular & Notification log templates
│       └── qa/                  # Acceptance Tests verification runner template
├── media/
│   ├── covers/                  # Locally downloaded book cover images (offline access)
│   └── photos/                  # Patron portrait photos
└── tests/
    ├── test_sprint1.py          # Sprint 1 Acceptance Tests (8/8 passing)
    ├── test_sprint2.py          # Sprint 2 Acceptance Tests (11/11 passing)
    ├── test_sprint3.py          # Sprint 3 Acceptance Tests (6/6 passing)
    └── test_sprint4.py          # Sprint 4 Acceptance Tests (7/7 passing)
```

---

## How to Run the Application Locally

1. **Activate the virtual environment:**
   ```bash
   cd Implementation
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Flask server:**
   ```bash
   python3 run.py
   ```
   The application will start at: **`http://127.0.0.1:5000`**

4. **Log in using Demo Accounts (or the 1-Click Quick Login Switcher on the login page):**
   - **Admin:** `ADMIN01`
   - **Librarian:** `LIB01`
   - **Student (Daksh Dua):** `25MCMC21`
   - **Faculty:** `FAC01`

---

## Running the Acceptance Tests

### Option A: Command Line (All 32 Tests)
```bash
python3 -m unittest -v discover tests
```
*Result: 32 tests run in ~1 second with `OK` status.*

### Option B: Interactive In-Browser Runner
Navigate to **`http://127.0.0.1:5000/qa`** in your browser and click **"Run All 32 Acceptance Tests"** to observe live test execution and passing status badges.
