"""Authentication, CSRF and authorization, with no Flask extensions."""
import hashlib
import hmac
import secrets
import time
from functools import wraps

from flask import abort, current_app, g, redirect, request, session
from werkzeug.security import generate_password_hash

from .db import get_db


def hash_password(password):
    if not 10 <= len(password) <= 256:
        raise ValueError('Password must contain 10 to 256 characters.')
    return generate_password_hash(password, method='pbkdf2:sha256:600000', salt_length=16)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                if request.method == 'GET':
                    return redirect('/login')
                abort(401)
            if roles and g.user[4] not in roles:
                abort(403)
            authorize_resource(view.__name__, kwargs)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def course_access(course_id):
    if not course_id:
        abort(400, 'Course ID is required.')
    if g.user[4] == 0:
        found = get_db().execute('SELECT id FROM courses WHERE id=?', (course_id,)).fetchone()
    elif g.user[4] == 2:
        found = get_db().execute('SELECT id FROM ins_crs_assignments WHERE ins_id=? AND crs_id=?',
                                 (g.user[0], course_id)).fetchone()
    else:
        found = get_db().execute("SELECT id FROM enrollments WHERE student_id=? AND course_id=? AND status='received'",
                                 (g.user[0], course_id)).fetchone()
    if not found:
        abort(404)


def forum_access(forum_id):
    if not get_db().execute('SELECT id FROM user_forum_memberships WHERE user_id=? AND forum_id=?',
                           (g.user[0], forum_id)).fetchone():
        abort(404)


def authorize_resource(endpoint, values):
    data = request.form if request.method == 'POST' else request.args
    if request.method == 'POST':
        validate_form(endpoint, data)
    identifier = data.get('id') or request.args.get('id')
    db = get_db()
    if endpoint in ('get_course', 'students'):
        course_access(values['crs_id'])
    if endpoint in ('create_assignment', 'create_lecture', 'notification_create'):
        course_id = data.get('crs_id') or identifier
        if request.method == 'POST' or course_id:
            course_access(course_id)
    resource_queries = {
        'edit_assignment': ('SELECT course_id FROM assignments WHERE id=?', data.get('a_id') or identifier),
        'delete_assignment': ('SELECT course_id FROM assignments WHERE id=?', identifier),
        'edit_lecture': ('SELECT course_id FROM lectures WHERE id=?', data.get('l_id') or identifier),
        'delete_lecture': ('SELECT course_id FROM lectures WHERE id=?', identifier),
        'assignment_details': ('SELECT course_id FROM assignments WHERE id=?', values.get('asn_id')),
        'eval_submission': ('SELECT a.course_id FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.id=?', data.get('s_id') or identifier),
        'notification_edit': ('SELECT crs_id FROM notifications WHERE id=?', identifier),
        'notification_delete': ('SELECT crs_id FROM notifications WHERE id=?', identifier),
        'notification_view': ('SELECT crs_id FROM notifications WHERE id=?', identifier),
    }
    if endpoint in resource_queries:
        query, target = resource_queries[endpoint]
        row = db.execute(query, (target,)).fetchone()
        if row is None:
            abort(404)
        course_access(row[0])
        if request.method == 'POST' and data.get('crs_id'):
            course_access(data['crs_id'])
    if endpoint == 'delete_message':
        if not db.execute('SELECT id FROM messages WHERE id=? AND receiver_id=?', (identifier, g.user[0])).fetchone():
            abort(404)
    if endpoint in ('forum_view', 'forum_post'):
        forum_access(values.get('frm_id') or data.get('frm_id') or identifier)
    if endpoint == 'forum_poster_detail':
        row = db.execute('SELECT forum_id FROM forum_posts WHERE id=?', (data.get('pst_id') or identifier,)).fetchone()
        if row is None:
            abort(404)
        forum_access(row[0])
    if endpoint == 'eval_submission' and request.method == 'POST':
        try:
            score = int(data.get('score', ''))
        except ValueError:
            abort(400, 'Score must be an integer from 0 to 100.')
        if not 0 <= score <= 100:
            abort(400, 'Score must be an integer from 0 to 100.')


def validate_form(endpoint, data):
    required = {
        'create_account': ('c_firstname', 'c_lastname', 'c_roles', 'c_psw'),
        'edit_account': ('c_firstname', 'c_lastname', 'c_roles', 'e_id'),
        'create_course': ('course_name', 'session', 'ins_ids'),
        'edit_course': ('course_name', 'session', 'ins_ids', 'c_id'),
        'create_assignment': ('asn_name', 'crs_id', 'ddl'),
        'edit_assignment': ('asn_name', 'crs_id', 'ddl', 'a_id'),
        'create_lecture': ('lec_title', 'crs_id'),
        'edit_lecture': ('lec_title', 'crs_id', 'l_id'),
        'create_message': ('receiver_id', 'con'),
        'notification_create': ('title', 'content', 'crs_id'),
        'notification_edit': ('id', 'title', 'content', 'crs_id'),
        'forum_post': ('frm_id', 'content'),
        'forum_poster_detail': ('pst_id', 'cmt'),
        'create_forum': ('frm_name',), 'edit_forum': ('frm_name', 'f_id'),
        'eval_submission': ('s_id', 'score'),
    }
    for field in required.get(endpoint, ()):
        if not data.get(field, '').strip():
            abort(400, 'Required fields cannot be empty.')
    for field, value in data.items():
        if len(value) > 4096:
            abort(400, 'A field is too long.')
        if field in ('crs_id', 'a_id', 'l_id', 's_id', 'e_id', 'c_id', 'pst_id', 'frm_id', 'receiver_id'):
            if not value.isdecimal() or len(value) > 18:
                abort(400, 'Invalid ID.')
    if endpoint in ('create_account', 'edit_account'):
        if data.get('c_roles') not in ('0', '1', '2'):
            abort(400, 'Invalid role.')
        password = data.get('c_psw', '')
        if password and not 10 <= len(password) <= 256:
            abort(400, 'Password must contain 10 to 256 characters.')
    if endpoint == 'assignment_details':
        file = request.files.get('asn_file')
        if file is None or not file.filename:
            abort(400, 'An attachment is required.')
    if endpoint in ('create_assignment', 'edit_assignment'):
        from datetime import datetime
        try:
            datetime.fromisoformat(data['ddl'])
        except ValueError:
            abort(400, 'Invalid deadline.')


def register(app):
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        token = session.get('auth_token')
        if token:
            g.user = get_db().execute('SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?',
                                      (token_hash(token), int(time.time()))).fetchone()
        if g.user:
            session.update(userid=g.user[0], name=g.user[1], role_id=g.user[4])
        elif token or 'userid' in session:
            session.clear()
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            received = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
            expected = session.get('csrf_token')
            if not expected or not hmac.compare_digest(expected.encode('utf-8'), received.encode('utf-8')):
                abort(400, 'The form expired. Reload the page and try again.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        if current_app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.cookies.get('userid'):
            response.delete_cookie('userid')
        return response
