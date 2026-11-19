import unittest
import io
import time
from datetime import datetime
from flask import Blueprint, render_template, jsonify
from app.auth_helpers import login_required

qa_bp = Blueprint('qa', __name__, url_prefix='/qa')

ACCEPTANCE_SPEC_MAP = [
    {
        "sprint": "Sprint 1: Basic Catalogue & Patron Foundation",
        "test_module": "tests.test_sprint1",
        "suite_name": "Sprint1AcceptanceTests",
        "criteria": [
            {"method": "test_admin_can_create_patron", "story": "Module 1: Patron Registration", "spec": "Check whether admin is able to create patron with name, role, department, roll number, email, phone."},
            {"method": "test_duplicate_roll_number_and_email_rejected", "story": "Module 1: Uniqueness Checks", "spec": "Check whether roll number and email uniqueness is validated and duplicate accounts are avoided."},
            {"method": "test_student_blocked_from_admin_patron_page", "story": "Module 1: Role Security", "spec": "Check whether a student user is blocked from opening the add-patron management pages."},
            {"method": "test_patron_deactivation_preserves_record", "story": "Module 1: Soft Deactivation", "spec": "Check whether deactivated patron cannot issue new books while past borrowing history is preserved."},
            {"method": "test_borrowing_rules_modifiable_from_admin_panel", "story": "Module 1: Borrowing Rules", "spec": "Check whether borrowing rules are changeable from admin panel without touching code."},
            {"method": "test_patron_ineligible_when_fine_exceeds_100", "story": "Module 1: Fine Cap Threshold", "spec": "Check whether issue is blocked when student fine balance is more than Rs. 100."},
            {"method": "test_manual_book_registration_fallback", "story": "Module 2: Offline Fallback", "spec": "Check whether librarian can save a book manually with local cover when APIs fail."},
            {"method": "test_duplicate_accession_number_rejected", "story": "Module 2: Copy Integrity", "spec": "Check whether duplicate accession numbers across copies are strictly rejected."}
        ]
    },
    {
        "sprint": "Sprint 2: Core Issue, Return, Renewal & Patron Status",
        "test_module": "tests.test_sprint2",
        "suite_name": "Sprint2CirculationAcceptanceTests",
        "criteria": [
            {"method": "test_successful_issue_decrements_availability_and_sets_due_date", "story": "Module 3: Fast Issue Desk", "spec": "Check whether due date is correct per role (student +14 days) and available count decreases by 1."},
            {"method": "test_issue_blocked_for_deactivated_patron", "story": "Module 3: Guard 1", "spec": "Check whether deactivated patron is blocked from borrowing books."},
            {"method": "test_issue_blocked_when_fine_exceeds_threshold", "story": "Module 3: Guard 2", "spec": "Check whether issue is blocked when fine balance exceeds Rs. 100 threshold."},
            {"method": "test_issue_blocked_when_max_books_quota_reached", "story": "Module 3: Guard 3", "spec": "Check whether issue is blocked when role borrowing limit is reached (e.g. Student max 3)."},
            {"method": "test_issue_blocked_for_duplicate_active_title_loan", "story": "Module 3: Guard 5", "spec": "Check whether patron is blocked from taking 2 simultaneous loans of the exact same title."},
            {"method": "test_return_on_time_has_zero_fine", "story": "Module 3: Return Counter", "spec": "Check whether on-time return incurs Rs. 0 fine and increments available stock count by +1."},
            {"method": "test_return_overdue_calculates_correct_fine_and_caps_at_200", "story": "Module 3: Auto-Fine Engine", "spec": "Check whether fine is calculated automatically at Rs. 2/day and strictly capped at Rs. 200."},
            {"method": "test_renewal_blocked_when_title_is_reserved", "story": "Module 3: Renewal Guard 1", "spec": "Check whether renewal is blocked when another student has reserved the title."},
            {"method": "test_valid_renewal_extends_due_date", "story": "Module 3: Renewal Extension", "spec": "Check whether valid renewal increments renewal count and extends due date by role duration."},
            {"method": "test_renewal_blocked_after_max_count", "story": "Module 3: Renewal Guard 2", "spec": "Check whether renewal is blocked when student hits max allowed renewal count (2 times)."},
            {"method": "test_renewal_blocked_if_overdue_more_than_7_days", "story": "Module 3: Renewal Guard 3", "spec": "Check whether renewal is blocked if book is overdue by more than 7 days."}
        ]
    },
    {
        "sprint": "Sprint 3: Student Self-Service Search & FCFS Reservations",
        "test_module": "tests.test_sprint3",
        "suite_name": "Sprint3SelfServiceAcceptanceTests",
        "criteria": [
            {"method": "test_search_catalog_with_filters", "story": "Module 4: Public Search", "spec": "Check whether student can search books by title, author, category with shelf location display (Rack B2, Shelf 3)."},
            {"method": "test_reservation_blocked_when_copies_are_available", "story": "Module 4: Reserve Guard 1", "spec": "Check whether reserve button is disabled/blocked when physical copies are still available on the shelf."},
            {"method": "test_reservation_succeeds_when_all_copies_issued_fcfs_queue", "story": "Module 4: FCFS Queue", "spec": "Check whether student is placed in reservation queue on first-come-first-serve basis with rank #N."},
            {"method": "test_duplicate_reservation_blocked", "story": "Module 4: Reserve Guard 2", "spec": "Check whether duplicate active reservation by the same student on the same title is blocked."},
            {"method": "test_patron_cannot_reserve_their_own_issued_book", "story": "Module 4: Reserve Guard 3", "spec": "Check whether patron is blocked from reserving a book they currently hold active on loan."},
            {"method": "test_reservation_cancellation_shifts_queue_positions", "story": "Module 4: Queue Re-balancing", "spec": "Check whether cancelling a hold shifts subsequent waiting queue positions down (#2 -> #1)."}
        ]
    },
    {
        "sprint": "Sprint 4: Bulk CSV Onboarding, Automated Reminders & Reports",
        "test_module": "tests.test_sprint4",
        "suite_name": "Sprint4AcceptanceTests",
        "criteria": [
            {"method": "test_bulk_csv_processing_with_success_and_failure_summary", "story": "Module 2: Bulk CSV Upload", "spec": "Check whether CSV import displays success count vs failed rows with reasons and rejects duplicate accessions."},
            {"method": "test_cron_pipeline_t_minus_1_reminder", "story": "Module 5: Cron Pipeline", "spec": "Check whether background pipeline sends email reminder 1 day before due date (T-1)."},
            {"method": "test_cron_pipeline_due_today_reminder", "story": "Module 5: Cron Pipeline", "spec": "Check whether background pipeline sends reminder on due date if book is not returned."},
            {"method": "test_cron_pipeline_daily_overdue_alert_capped_once_per_day", "story": "Module 5: Fine Notification", "spec": "Check whether overdue students receive alert with accrued fine, maximum one email per day per book."},
            {"method": "test_uncollected_hold_expires_after_48_hours", "story": "Module 5: 48-Hr Hold Expiry", "spec": "Check whether uncollected reservation hold expires after 48 hours and notifies next student in line."},
            {"method": "test_overdue_report_and_csv_export", "story": "Module 6: Overdue CSV Report", "spec": "Check whether overdue report displays student, roll, title, fine amount with CSV export and blocks students."},
            {"method": "test_popular_books_report_and_csv_export", "story": "Module 6: Popular Books", "spec": "Check whether popular books report aggregates top 20 titles for 30/90 days with CSV export."}
        ]
    }
]

@qa_bp.route('/')
@login_required
def dashboard():
    return render_template('qa/tests_dashboard.html', spec_map=ACCEPTANCE_SPEC_MAP)

@qa_bp.route('/run-all', methods=['POST'])
@login_required
def run_all_tests():
    """Executes the test suites dynamically to avoid circular imports."""
    import importlib
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    for sec in ACCEPTANCE_SPEC_MAP:
        mod = importlib.import_module(sec["test_module"])
        cls_obj = getattr(mod, sec["suite_name"])
        suite.addTests(loader.loadTestsFromTestCase(cls_obj))

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    failures_and_errors = {test.id().split('.')[-1]: err for test, err in result.failures + result.errors}

    detailed_results = []
    for section in ACCEPTANCE_SPEC_MAP:
        section_results = []
        for item in section["criteria"]:
            m_name = item["method"]
            passed = m_name not in failures_and_errors
            section_results.append({
                "method": m_name,
                "story": item["story"],
                "spec": item["spec"],
                "passed": passed,
                "error": failures_and_errors.get(m_name, None)
            })
        detailed_results.append({
            "sprint": section["sprint"],
            "criteria": section_results
        })

    return jsonify({
        "total_tests": result.testsRun,
        "passed": result.wasSuccessful(),
        "failures_count": len(result.failures),
        "errors_count": len(result.errors),
        "elapsed_seconds": round(elapsed, 2),
        "timestamp": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "sections": detailed_results
    })
