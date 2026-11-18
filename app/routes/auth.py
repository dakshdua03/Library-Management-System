from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models import Patron

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip().upper()
        if not roll_number:
            flash('Please enter your Roll Number or Employee ID.', 'warning')
            return render_template('auth/login.html')

        patron = Patron.query.filter(Patron.roll_number.ilike(roll_number)).first()
        if not patron:
            flash(f'No patron found with Roll / ID: "{roll_number}". Please check or ask Admin.', 'danger')
            return render_template('auth/login.html')

        # Check if patron account is active
        if not patron.is_active:
            flash('Your account has been deactivated. Please contact the library administrator.', 'danger')
            return render_template('auth/login.html')

        # Set Flask session
        session['user_id'] = patron.id
        session['user_roll'] = patron.roll_number
        session['user_name'] = patron.name
        session['user_role'] = patron.role

        flash(f'Signed in as {patron.name} ({patron.role})', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
