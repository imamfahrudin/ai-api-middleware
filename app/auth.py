from functools import wraps
from flask import request, session, redirect, url_for, render_template, Blueprint

from app.config import MIDDLEWARE_PASSWORD

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not MIDDLEWARE_PASSWORD:
            return f(*args, **kwargs)
        if not session.get('logged_in'):
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/middleware/login', methods=['GET', 'POST'])
def login():
    if not MIDDLEWARE_PASSWORD:
        return redirect('/middleware/')
    if session.get('logged_in'):
        return redirect('/middleware/')
    error = None
    if request.method == 'POST':
        if request.form.get('password') == MIDDLEWARE_PASSWORD:
            session['logged_in'] = True
            next_url = request.args.get('next') or '/middleware/'
            return redirect(next_url)
        else:
            error = 'Invalid Credentials. Please try again.'
    return f'Login page: {error}' if error else 'Login page'

@auth_bp.route('/middleware/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
