import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Patron, BorrowingRules
from app.auth_helpers import login_required, role_required

patrons_bp = Blueprint('patrons', __name__, url_prefix='/patrons')

@patrons_bp.route('/')
@login_required
@role_required('Admin')
def list_patrons():
    patrons = Patron.query.order_by(Patron.created_at.desc()).all()
    return render_template('patrons/list.html', patrons=patrons)

@patrons_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def add_patron():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'Student').strip()
        roll_number = request.form.get('roll_number', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()

        # Validation Checks
        if not name or not roll_number or not email:
            flash('Name, Roll Number, and Email are mandatory fields.', 'danger')
            return render_template('patrons/add.html')

        # Check Roll Number uniqueness
        if Patron.query.filter_by(roll_number=roll_number).first():
            flash(f'Validation Error: Roll Number "{roll_number}" is already registered.', 'danger')
            return render_template('patrons/add.html')

        # Check Email uniqueness
        if Patron.query.filter_by(email=email).first():
            flash(f'Validation Error: Email "{email}" is already associated with an existing account.', 'danger')
            return render_template('patrons/add.html')

        # Handle optional Photo upload
        photo_path = None
        photo_file = request.files.get('photo')
        if photo_file and photo_file.filename:
            filename = secure_filename(f"{roll_number}_{photo_file.filename}")
            photos_dir = current_app.config['PHOTOS_FOLDER']
            os.makedirs(photos_dir, exist_ok=True)
            full_path = os.path.join(photos_dir, filename)
            photo_file.save(full_path)
            photo_path = f"photos/{filename}"

        # Create Patron
        new_patron = Patron(
            name=name,
            role=role,
            roll_number=roll_number,
            email=email,
            department=department,
            phone=phone,
            photo_path=photo_path,
            is_active=True
        )

        db.session.add(new_patron)
        db.session.commit()

        flash(f'Patron "{name}" ({roll_number}) registered successfully!', 'success')
        return redirect(url_for('patrons.list_patrons'))

    return render_template('patrons/add.html')

@patrons_bp.route('/toggle-status/<int:patron_id>', methods=['POST'])
@login_required
@role_required('Admin')
def toggle_status(patron_id):
    """Deactivate or reactivate patron without deleting historical borrowing records."""
    patron = Patron.query.get_or_404(patron_id)
    patron.is_active = not patron.is_active
    db.session.commit()

    state = "activated" if patron.is_active else "deactivated"
    flash(f'Patron {patron.name} ({patron.roll_number}) has been {state}.', 'info')
    return redirect(url_for('patrons.list_patrons'))

@patrons_bp.route('/rules', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def borrowing_rules():
    """Admin configuration of role borrowing policies without editing code."""
    rules = BorrowingRules.query.all()

    if request.method == 'POST':
        for r in rules:
            max_books = request.form.get(f'max_books_{r.role}', type=int)
            duration = request.form.get(f'duration_{r.role}', type=int)
            renewals = request.form.get(f'renewals_{r.role}', type=int)
            fine = request.form.get(f'fine_{r.role}', type=float)

            if max_books is not None and duration is not None and renewals is not None and fine is not None:
                r.max_books_allowed = max_books
                r.loan_duration_days = duration
                r.max_renewals = renewals
                r.fine_per_day = fine

        db.session.commit()
        flash('Borrowing rules successfully updated across the system!', 'success')
        return redirect(url_for('patrons.borrowing_rules'))

    return render_template('patrons/rules.html', rules=rules)
