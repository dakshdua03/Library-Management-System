from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.extensions import db
from app.models import BookTitle, BookCopy, Reservation, Patron
from app.reservation_service import ReservationService
from app.auth_helpers import login_required

selfservice_bp = Blueprint('selfservice', __name__, url_prefix='/selfservice')

@selfservice_bp.route('/search')
@login_required
def search():
    """
    Responsive Public Book Discovery Search:
    - Filters: Title, Author, ISBN, Category
    - Option: "Available books only"
    - Displays: Cover, availability (e.g. 0/2 available), and rack/shelf locations.
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    available_only = request.args.get('available_only') == '1'

    query = BookTitle.query

    if q:
        query = query.filter(
            (BookTitle.title.ilike(f"%{q}%")) |
            (BookTitle.authors.ilike(f"%{q}%")) |
            (BookTitle.isbn.ilike(f"%{q}%")) |
            (BookTitle.category.ilike(f"%{q}%"))
        )

    if category:
        query = query.filter(BookTitle.category.ilike(category))

    titles = query.order_by(BookTitle.title.asc()).all()

    # Filter available only if requested
    if available_only:
        titles = [t for t in titles if t.available_copies > 0]

    # Get distinct categories for dropdown filter
    all_categories = (
        db.session.query(BookTitle.category)
        .distinct()
        .filter(BookTitle.category.isnot(None))
        .all()
    )
    categories = sorted([c[0] for c in all_categories if c[0]])

    return render_template(
        'selfservice/search.html',
        titles=titles,
        query=q,
        selected_category=category,
        available_only=available_only,
        categories=categories
    )

@selfservice_bp.route('/book/<string:isbn>')
@login_required
def book_details(isbn):
    """Book detail view with physical copy status & reserve button."""
    title = BookTitle.query.get_or_404(isbn)
    user_id = session.get('user_id')
    user_role = session.get('user_role')

    # Check if user already holds a pending reservation for this title
    my_reservation = Reservation.query.filter_by(
        patron_id=user_id,
        isbn=title.isbn,
        status='Pending'
    ).first()

    # Total waitlist queue length
    queue_count = Reservation.query.filter_by(isbn=title.isbn, status='Pending').count()

    return render_template(
        'selfservice/book_details.html',
        title=title,
        my_reservation=my_reservation,
        queue_count=queue_count
    )

@selfservice_bp.route('/reserve/<string:isbn>', methods=['POST'])
@login_required
def reserve_book(isbn):
    """Place FCFS Reservation when 0 copies are available."""
    user_id = session.get('user_id')
    success, message, res = ReservationService.create_reservation(user_id, isbn)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('selfservice.book_details', isbn=isbn))

@selfservice_bp.route('/cancel-reservation/<int:res_id>', methods=['POST'])
@login_required
def cancel_reservation(res_id):
    """Cancel waitlist reservation."""
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    is_staff = user_role in ['Admin', 'Librarian']

    success, message = ReservationService.cancel_reservation(
        res_id,
        requested_by_patron_id=user_id,
        is_admin_or_librarian=is_staff
    )

    if success:
        flash(message, 'info')
    else:
        flash(message, 'danger')

    next_page = request.referrer or url_for('selfservice.my_reservations')
    return redirect(next_page)

@selfservice_bp.route('/my-reservations')
@login_required
def my_reservations():
    """Patron dashboard showing all their active waitlist reservations and queue ranks."""
    user_id = session.get('user_id')
    reservations = (
        Reservation.query.filter_by(patron_id=user_id, status='Pending')
        .order_by(Reservation.request_date.desc())
        .all()
    )
    return render_template('selfservice/my_reservations.html', reservations=reservations)

@selfservice_bp.route('/admin-queue')
@login_required
def admin_queue():
    """Admin / Librarian view of all active reservation queues across the library."""
    if session.get('user_role') not in ['Admin', 'Librarian']:
        flash('Access restricted to library staff.', 'danger')
        return redirect(url_for('main.dashboard'))

    reservations = (
        Reservation.query.filter_by(status='Pending')
        .order_by(Reservation.isbn.asc(), Reservation.queue_position.asc())
        .all()
    )
    return render_template('selfservice/admin_queue.html', reservations=reservations)

@selfservice_bp.route('/api/search-suggest')
@login_required
def api_search_suggest():
    """Autocomplete suggestions for search bar."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    titles = (
        BookTitle.query.filter(
            (BookTitle.title.ilike(f"%{q}%")) |
            (BookTitle.authors.ilike(f"%{q}%")) |
            (BookTitle.isbn.ilike(f"%{q}%"))
        )
        .limit(6)
        .all()
    )

    results = []
    for t in titles:
        results.append({
            'isbn': t.isbn,
            'title': t.title,
            'authors': t.authors or 'Unknown',
            'available': t.available_copies,
            'total': t.total_copies,
            'cover_path': t.cover_path
        })
    return jsonify(results)
