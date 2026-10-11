import flask
from flask import session, request, jsonify
from ..db import get_db
from ..security import require_roles
from ..views import render
import secrets
import time
from ..security import token_hash
from werkzeug.security import check_password_hash
bp = flask.Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render('login.html')
    data = request.form
    account_id = data.get('id', '')
    password = data.get('psw', '')
    if not account_id.isdecimal() or len(account_id) > 18 or len(password) > 256:
        return (jsonify(status='error', message='Incorrect login information.'), 400)
    account_id = str(int(account_id))
    db = get_db()
    now = int(time.time())
    attempt = db.execute('SELECT failures, updated_at FROM login_attempts WHERE account_id=?', (account_id,)).fetchone()
    if attempt and attempt[0] >= 10 and (now - attempt[1] < 900):
        return (jsonify(status='error', message='Too many attempts. Try again in 15 minutes.'), 429)
    user = db.execute('SELECT * FROM users WHERE id=?', (account_id,)).fetchone()
    if not user or not check_password_hash(user[3], password):
        failures = attempt[0] + 1 if attempt and now - attempt[1] < 900 else 1
        db.execute('INSERT INTO login_attempts VALUES (?, ?, ?) ON CONFLICT(account_id) DO UPDATE SET failures=excluded.failures, updated_at=excluded.updated_at', (account_id, failures, now))
        db.commit()
        return (jsonify(status='error', message='Incorrect login information.'), 401)
    old_token = session.get('auth_token')
    if old_token:
        db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (token_hash(old_token),))
    db.execute('DELETE FROM login_attempts WHERE account_id=?', (account_id,))
    db.execute('DELETE FROM auth_sessions WHERE expires_at<=?', (now,))
    session.clear()
    session.permanent = True
    token = secrets.token_urlsafe(32)
    session['auth_token'] = token
    session['csrf_token'] = secrets.token_urlsafe(32)
    db.execute('INSERT INTO auth_sessions VALUES (?, ?, ?)', (token_hash(token), user[0], now + 8 * 3600))
    return jsonify(status='success', message='Welcome!')

@bp.route('/logout', methods=['POST'])
@require_roles()
def logout():
    cursor = get_db().cursor()
    cursor.execute('DELETE FROM auth_sessions WHERE token_hash=?', (token_hash(session['auth_token']),))
    session.clear()
    return flask.redirect('/login')
