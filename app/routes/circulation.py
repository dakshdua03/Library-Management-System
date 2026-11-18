from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.models import Patron, BookCopy, BookTitle, BorrowTransaction
from app.circulation_service import CirculationService
from app.auth_helpers import login_required, role_required

circulation_bp = Blueprint('circulation', __name__, url_prefix='/circulation')

@circulation_bp.route('/')
@login_required
@role_required('Admin', 'Librarian')
def active_loans():
    """Circulation desk overview of all active loans."""
    loans = BorrowTransaction.query.filter_by(status='Active').order_by(BorrowTransaction.issue_date.desc()).all()
    return render_template('circulation/active_loans.html', loans=loans)

@circulation_bp.route('/issue', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def issue_book():
    """
    Issue Book Desk:
    - Searchable autocomplete for Patrons & Books
    - 5-point validations
    - 1-click confirmation card
    """
    if request.method == 'POST':
        patron_id = request.form.get('patron_id', type=int)
        accession_no = request.form.get('accession_no', '').strip().upper()

        success, message, tx = CirculationService.validate_and_issue_book(patron_id, accession_no)
        if success:
            flash(message, 'success')
            return redirect(url_for('circulation.issue_confirmation', tx_id=tx.id))
        else:
            flash(message, 'danger')
            return redirect(url_for('circulation.issue_book'))

    return render_template('circulation/issue.html')

@circulation_bp.route('/issue/confirm/<int:tx_id>')
@login_required
@role_required('Admin', 'Librarian')
def issue_confirmation(tx_id):
    """1-click Issue Confirmation Summary Card showing patron photo, book title and due date."""
    tx = BorrowTransaction.query.get_or_404(tx_id)
    patron = Patron.query.get(tx.patron_id)
    copy = BookCopy.query.get(tx.accession_no)
    return render_template('circulation/issue_confirm.html', tx=tx, patron=patron, copy=copy)

@circulation_bp.route('/return', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def return_book():
    """Return Book Desk with automatic fine calculation and receipt card."""
    summary = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        if not identifier:
            flash('Please enter an Accession Number or Transaction ID.', 'warning')
            return render_template('circulation/return.html', summary=None)

        success, message, return_summary = CirculationService.process_return(identifier)
        if success:
            flash(message, 'success')
            summary = return_summary
        else:
            flash(message, 'danger')

    return render_template('circulation/return.html', summary=summary)

@circulation_bp.route('/renew/<int:tx_id>', methods=['POST'])
@login_required
def renew_book(tx_id):
    """Renew Book Action (accessible by Librarian or Student for their own book)."""
    patron_id = None
    # If student, restrict to own loans
    if session.get('user_role') == 'Student':
        patron_id = session.get('user_id')

    success, message = CirculationService.process_renewal(tx_id, patron_id=patron_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    # Return to previous page or dashboard
    next_page = request.referrer or url_for('main.dashboard')
    return redirect(next_page)

# --- Autocomplete APIs for Circulation Counter ---

@circulation_bp.route('/api/search-patrons')
@login_required
@role_required('Admin', 'Librarian')
def api_search_patrons():
    """Autocomplete search for patrons by roll number, name, or email."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    patrons = Patron.query.filter(
        (Patron.roll_number.ilike(f"%{q}%")) |
        (Patron.name.ilike(f"%{q}%")) |
        (Patron.email.ilike(f"%{q}%"))
    ).limit(8).all()

    results = []
    for p in patrons:
        results.append({
            'id': p.id,
            'name': p.name,
            'roll_number': p.roll_number,
            'role': p.role,
            'email': p.email,
            'fine_balance': p.fine_balance,
            'current_borrowed_count': p.current_borrowed_count,
            'is_active': p.is_active,
            'photo_path': p.photo_path
        })
    return jsonify(results)

@circulation_bp.route('/api/search-copies')
@login_required
@role_required('Admin', 'Librarian')
def api_search_copies():
    """Autocomplete search for available book copies by accession no, title, or ISBN."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    copies = (
        db.session.query(BookCopy, BookTitle)
        .join(BookTitle, BookCopy.isbn == BookTitle.isbn)
        .filter(
            BookCopy.status == 'Available',
            (
                (BookCopy.accession_no.ilike(f"%{q}%")) |
                (BookTitle.title.ilike(f"%{q}%")) |
                (BookTitle.isbn.ilike(f"%{q}%"))
            )
        )
        .limit(8)
        .all()
    )

    results = []
    for copy, title in copies:
        results.append({
            'accession_no': copy.accession_no,
            'isbn': title.isbn,
            'title': title.title,
            'authors': title.authors,
            'rack_no': copy.rack_no,
            'shelf_no': copy.shelf_no,
            'cover_path': title.cover_path
        })
    return jsonify(results)
