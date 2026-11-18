# Library Management System (LMS) - Minor 1 Implementation

Built with **Python**, **Flask**, **SQLite**, and **Bootstrap 5**. Designed strictly to match the Sommerville architecture diagrams and the specifications in `Product And Sprint Backlog (Refined).docx`.

---

## Project Structure

```
Implementation/
├── run.py                       # App entrypoint & automated database seeder
├── lms.db                       # SQLite relational database
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration (SQLite DB path, media paths, secrets)
│   ├── extensions.py            # SQLAlchemy instance
│   ├── models.py                # Database models (Patron, BorrowingRules, BookTitle, BookCopy, etc.)
│   ├── services.py              # ISBN API integration (OpenLibrary & Google Books) & cover downloader
│   ├── auth_helpers.py          # Session authentication & @role_required decorators
│   ├── routes/
│   │   ├── auth.py              # Login / Logout with session handling
│   │   ├── main.py              # Dashboard & offline media serving
│   │   ├── patrons.py           # Patron management & dynamic Borrowing Rules editor
│   │   └── catalog.py           # ISBN auto-fetch, manual entry fallback & copy tracker
│   └── templates/
│       ├── base.html            # Core layout with Bootstrap 5 & navigation
│       ├── dashboard.html       # Overview dashboard with stats & role-based quick actions
│       ├── auth/
│       │   └── login.html       # Role switcher & Roll Number / ID login
│       ├── patrons/
│       │   ├── list.html        # Searchable directory with active/deactive toggle
│       │   ├── add.html         # Add patron with uniqueness validation & photo upload
│       │   └── rules.html       # Dynamic Borrowing Rules editor
│       └── catalog/
│           ├── list.html        # Catalog inventory with availability (n/m) and cover thumbnails
│           ├── add_isbn.html    # Dynamic AJAX ISBN auto-fetch with cover preview
│           ├── manual_add.html  # Offline manual fallback entry
│           └── add_copy.html    # Add copies with Accession No, Rack & Shelf location
├── media/
│   ├── covers/                  # Locally downloaded book cover images (offline access)
│   └── photos/                  # Patron portrait photos
└── tests/
    └── test_sprint1.py          # Automated Acceptance Test Suite (8/8 passing)
```

---

## How to Run the Application

1. **Activate the virtual environment:**
   ```bash
   cd "/home/dakshdua/Downloads/Minor 1/Implementation"
   source venv/bin/activate
   ```

2. **Start the Flask development server:**
   ```bash
   python3 run.py
   ```
   The application will start at `http://localhost:5000`.

3. **Log in using Demo Accounts (or the Quick-Switcher buttons on the login page):**
   - **Admin:** `ADMIN01`
   - **Librarian:** `LIB01`
   - **Student (Daksh Dua):** `25MCMC21`
   - **Student (Satyabrata Rath):** `25MCMC36`
   - **Faculty:** `FAC01`

---

## Running Acceptance Tests

Run the automated Sprint 1 test suite verifying all acceptance criteria:
```bash
python3 -m unittest tests/test_sprint1.py
```
*(Tests cover: Admin patron registration, Roll & Email uniqueness validation, Student role blocking, Deactivation without deletion, Admin panel borrowing rules modification, Fine eligibility cutoff, Manual book registration fallback, and Duplicate accession number rejection).*
