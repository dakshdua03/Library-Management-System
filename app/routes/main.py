from flask import Blueprint, render_template, session, send_from_directory, current_app, redirect, url_for
from app.models import Patron, BookTitle, BookCopy, BorrowingRules
from app.auth_helpers import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    patron = Patron.query.get(session['user_id'])
    if not patron:
        session.clear()
        return redirect(url_for('auth.login'))

    rules = BorrowingRules.query.all()
    stats = {
        'total_titles': BookTitle.query.count(),
        'total_copies': BookCopy.query.count(),
        'total_patrons': Patron.query.count()
    }

    return render_template('dashboard.html', patron=patron, rules=rules, stats=stats)

@main_bp.route('/media/<path:filename>')
def uploaded_media(filename):
    """Serves local cover images and patron photos for offline access."""
    return send_from_directory(current_app.config['MEDIA_FOLDER'], filename)
