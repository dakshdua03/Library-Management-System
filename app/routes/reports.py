import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, make_response, flash, redirect, url_for, session
from app.extensions import db
from app.models import Patron, BookTitle, BookCopy, BorrowTransaction, Fine
from app.notification_model import NotificationLog
from app.notification_service import NotificationService
from app.auth_helpers import login_required, role_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/overdue')
@login_required
@role_required('Admin')
def overdue_report():
    """
    Overdue Books Report:
    - Lists Student Name, Roll Number, Book Title, Accession, Due Date, Days Overdue, and Fine
    - Administrative filters: Department & Role
    - CSV Export
    """
    department = request.args.get('department', '').strip()
    role = request.args.get('role', '').strip()
    export_csv = request.args.get('export') == 'csv'

    now = datetime.now()

    # Query active overdue loans
    query = (
        db.session.query(BorrowTransaction, Patron, BookCopy, BookTitle)
        .join(Patron, BorrowTransaction.patron_id == Patron.id)
        .join(BookCopy, BorrowTransaction.accession_no == BookCopy.accession_no)
        .join(BookTitle, BookCopy.isbn == BookTitle.isbn)
        .filter(BorrowTransaction.status == 'Active', BorrowTransaction.due_date < now)
    )

    if department:
        query = query.filter(Patron.department.ilike(f"%{department}%"))
    if role:
        query = query.filter(Patron.role == role)

    results = query.order_by(BorrowTransaction.due_date.asc()).all()

    # Build report rows
    overdue_rows = []
    for tx, patron, copy, title in results:
        days_overdue = max(1, (now.date() - tx.due_date.date()).days)
        fine_accrued = min(days_overdue * 2.0, 200.0)
        overdue_rows.append({
            'tx_id': tx.id,
            'patron_name': patron.name,
            'roll_number': patron.roll_number,
            'role': patron.role,
            'department': patron.department or 'N/A',
            'email': patron.email,
            'title': title.title,
            'accession_no': copy.accession_no,
            'due_date': tx.due_date.strftime('%d-%m-%Y'),
            'days_overdue': days_overdue,
            'fine_amount': fine_accrued
        })

    # CSV Export Handler
    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Loan ID', 'Patron Name', 'Roll / Employee ID', 'Role', 'Department', 'Email', 'Book Title', 'Accession No', 'Due Date', 'Days Overdue', 'Accrued Fine (Rs.)'])
        for r in overdue_rows:
            writer.writerow([r['tx_id'], r['patron_name'], r['roll_number'], r['role'], r['department'], r['email'], r['title'], r['accession_no'], r['due_date'], r['days_overdue'], f"{r['fine_amount']:.2f}"])

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=overdue_books_report_{datetime.now().strftime('%Y%m%d')}.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response

    # Get distinct departments for filter dropdown
    depts = [d[0] for d in db.session.query(Patron.department).distinct().filter(Patron.department.isnot(None)).all() if d[0]]

    return render_template(
        'reports/overdue.html',
        rows=overdue_rows,
        selected_dept=department,
        selected_role=role,
        departments=depts
    )

@reports_bp.route('/popular')
@login_required
@role_required('Admin')
def popular_report():
    """
    Top-20 Popular Books Report:
    - Counts transaction issues over past 30 / 90 days or all-time
    - CSV Export
    """
    timeframe = request.args.get('days', '90')
    export_csv = request.args.get('export') == 'csv'

    try:
        days_int = int(timeframe)
    except:
        days_int = 90

    cutoff_date = datetime.now() - timedelta(days=days_int)

    # Aggregation query
    stats_query = (
        db.session.query(
            BookTitle.isbn,
            BookTitle.title,
            BookTitle.authors,
            BookTitle.category,
            db.func.count(BorrowTransaction.id).label('issue_count')
        )
        .join(BookCopy, BookTitle.isbn == BookCopy.isbn)
        .join(BorrowTransaction, BookCopy.accession_no == BorrowTransaction.accession_no)
        .filter(BorrowTransaction.issue_date >= cutoff_date)
        .group_by(BookTitle.isbn, BookTitle.title, BookTitle.authors, BookTitle.category)
        .order_by(db.desc('issue_count'))
        .limit(20)
        .all()
    )

    popular_books = []
    for rank, (isbn, title, authors, category, count) in enumerate(stats_query, start=1):
        popular_books.append({
            'rank': rank,
            'isbn': isbn,
            'title': title,
            'authors': authors or 'Unknown',
            'category': category or 'General',
            'issue_count': count
        })

    if export_csv:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Rank', 'ISBN', 'Book Title', 'Authors', 'Category', f'Issue Count (Past {days_int} Days)'])
        for b in popular_books:
            writer.writerow([b['rank'], b['isbn'], b['title'], b['authors'], b['category'], b['issue_count']])

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=top20_popular_books_{days_int}days.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response

    return render_template('reports/popular.html', books=popular_books, timeframe=timeframe)

@reports_bp.route('/notifications')
@login_required
@role_required('Admin')
def notification_logs():
    """Audit log of automated reminder emails sent."""
    logs = NotificationLog.query.order_by(NotificationLog.sent_at.desc()).limit(50).all()
    return render_template('reports/notifications.html', logs=logs)

@reports_bp.route('/notifications/run-cron', methods=['POST'])
@login_required
@role_required('Admin')
def trigger_cron_manually():
    """Admin button to trigger daily reminder pipeline on demand."""
    reminders = NotificationService.run_daily_loan_reminders()
    holds = NotificationService.process_expired_reservation_holds()
    flash(f'Cron pipeline executed: {reminders} reminder email(s) dispatched, {holds} expired hold(s) processed.', 'success')
    return redirect(url_for('reports.notification_logs'))
