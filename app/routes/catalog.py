from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import BookTitle, BookCopy
from app.services import clean_isbn, fetch_book_metadata, download_cover_locally
from app.bulk_service import process_bulk_csv
from app.auth_helpers import login_required, role_required

catalog_bp = Blueprint('catalog', __name__, url_prefix='/catalog')

@catalog_bp.route('/')
@login_required
def list_books():
    titles = BookTitle.query.order_by(BookTitle.created_at.desc()).all()
    return render_template('catalog/list.html', titles=titles)

@catalog_bp.route('/api/fetch-isbn')
@login_required
def api_fetch_isbn():
    """AJAX endpoint for ISBN lookup from OpenLibrary / Google Books."""
    isbn = request.args.get('isbn', '').strip()
    result = fetch_book_metadata(isbn)
    return jsonify(result)

@catalog_bp.route('/add-by-isbn', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def add_by_isbn():
    if request.method == 'POST':
        raw_isbn = request.form.get('isbn', '').strip()
        isbn = clean_isbn(raw_isbn)
        title_text = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        publisher = request.form.get('publisher', '').strip()
        year = request.form.get('year', type=int)
        category = request.form.get('category', 'General').strip()
        cover_url = request.form.get('cover_url', '').strip()

        accession_no = request.form.get('accession_no', '').strip().upper()
        rack_no = request.form.get('rack_no', '').strip()
        shelf_no = request.form.get('shelf_no', '').strip()

        if not isbn or not title_text or not accession_no:
            flash('ISBN, Title, and Accession Number are mandatory fields.', 'danger')
            return render_template('catalog/add_isbn.html')

        if BookCopy.query.filter_by(accession_no=accession_no).first():
            flash(f'Validation Error: Accession Number "{accession_no}" already exists! Copies must have unique accession numbers.', 'danger')
            return render_template('catalog/add_isbn.html')

        book_title = BookTitle.query.get(isbn)
        if not book_title:
            cover_path = None
            if cover_url:
                cover_path = download_cover_locally(cover_url, isbn)

            book_title = BookTitle(
                isbn=isbn,
                title=title_text,
                authors=authors,
                publisher=publisher,
                year=year,
                category=category,
                cover_path=cover_path
            )
            db.session.add(book_title)

        initial_copy = BookCopy(
            accession_no=accession_no,
            isbn=isbn,
            rack_no=rack_no,
            shelf_no=shelf_no,
            status='Available'
        )
        db.session.add(initial_copy)
        db.session.commit()

        flash(f'Book "{title_text}" and copy {accession_no} successfully added to catalog!', 'success')
        return redirect(url_for('catalog.list_books'))

    return render_template('catalog/add_isbn.html')

@catalog_bp.route('/manual-add', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def manual_add_title():
    if request.method == 'POST':
        raw_isbn = request.form.get('isbn', '').strip()
        isbn = clean_isbn(raw_isbn)
        title_text = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        publisher = request.form.get('publisher', '').strip()
        year = request.form.get('year', type=int)
        category = request.form.get('category', 'General').strip()

        accession_no = request.form.get('accession_no', '').strip().upper()
        rack_no = request.form.get('rack_no', '').strip()
        shelf_no = request.form.get('shelf_no', '').strip()

        if not isbn or not title_text or not accession_no:
            flash('ISBN, Title, and Accession Number are required.', 'danger')
            return render_template('catalog/manual_add.html')

        if BookCopy.query.filter_by(accession_no=accession_no).first():
            flash(f'Accession Number "{accession_no}" already exists.', 'danger')
            return render_template('catalog/manual_add.html')

        cover_path = None
        cover_file = request.files.get('cover_file')
        if cover_file and cover_file.filename:
            filename = secure_filename(f"{isbn}_{cover_file.filename}")
            covers_dir = current_app.config['COVERS_FOLDER']
            os.makedirs(covers_dir, exist_ok=True)
            cover_file.save(os.path.join(covers_dir, filename))
            cover_path = f"covers/{filename}"

        book_title = BookTitle.query.get(isbn)
        if not book_title:
            book_title = BookTitle(
                isbn=isbn,
                title=title_text,
                authors=authors,
                publisher=publisher,
                year=year,
                category=category,
                cover_path=cover_path
            )
            db.session.add(book_title)

        initial_copy = BookCopy(
            accession_no=accession_no,
            isbn=isbn,
            rack_no=rack_no,
            shelf_no=shelf_no,
            status='Available'
        )
        db.session.add(initial_copy)
        db.session.commit()

        flash(f'Manual registration for "{title_text}" completed successfully!', 'success')
        return redirect(url_for('catalog.list_books'))

    return render_template('catalog/manual_add.html')

@catalog_bp.route('/add-copy/<string:isbn>', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def add_copy(isbn):
    title = BookTitle.query.get_or_404(isbn)

    if request.method == 'POST':
        accession_no = request.form.get('accession_no', '').strip().upper()
        rack_no = request.form.get('rack_no', '').strip()
        shelf_no = request.form.get('shelf_no', '').strip()

        if not accession_no:
            flash('Accession Number is required.', 'danger')
            return render_template('catalog/add_copy.html', title=title)

        if BookCopy.query.filter_by(accession_no=accession_no).first():
            flash(f'Accession Number "{accession_no}" is already registered.', 'danger')
            return render_template('catalog/add_copy.html', title=title)

        new_copy = BookCopy(
            accession_no=accession_no,
            isbn=isbn,
            rack_no=rack_no,
            shelf_no=shelf_no,
            status='Available'
        )
        db.session.add(new_copy)
        db.session.commit()

        flash(f'Physical Copy "{accession_no}" added to "{title.title}"!', 'success')
        return redirect(url_for('catalog.list_books'))

    return render_template('catalog/add_copy.html', title=title)

# --- Sprint 4: Bulk CSV Onboarding ---

@catalog_bp.route('/bulk-csv', methods=['GET', 'POST'])
@login_required
@role_required('Admin', 'Librarian')
def bulk_csv():
    """Bulk CSV book onboarding endpoint with summary report."""
    summary = None
    if request.method == 'POST':
        csv_file = request.files.get('csv_file')
        if not csv_file or not csv_file.filename.endswith('.csv'):
            flash('Please upload a valid .csv file.', 'danger')
            return render_template('catalog/bulk_csv.html', summary=None)

        summary = process_bulk_csv(csv_file.stream)
        if summary['success_count'] > 0:
            flash(f"Bulk Onboarding Complete: {summary['success_count']} book copies added successfully!", 'success')
        if summary['failed_count'] > 0:
            flash(f"{summary['failed_count']} rows failed validation.", 'warning')

    return render_template('catalog/bulk_csv.html', summary=summary)
