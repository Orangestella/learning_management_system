"""Private uploads served only to authorized course participants."""
import secrets
from pathlib import Path

from flask import Blueprint, abort, current_app, g, send_from_directory
from werkzeug.utils import secure_filename

from .db import get_db
from .security import course_access, require_roles

bp = Blueprint('uploads', __name__)


def save_upload(file):
    name = secure_filename(file.filename or '')
    extension = Path(name).suffix.lower().lstrip('.')
    if not name or extension not in current_app.config['ALLOWED_EXTENSIONS']:
        raise ValueError('Only PDF, DOC and DOCX files are allowed.')
    filename = secrets.token_hex(16) + '.' + extension
    path = Path(current_app.config['UPLOAD_FOLDER']) / filename
    g.setdefault('pending_uploads', []).append(path)
    file.save(path)
    return '/files/' + filename


@bp.route('/files/<filename>')
@require_roles()
def download(filename):
    url = '/files/' + filename
    row = get_db().execute('SELECT course_id FROM lectures WHERE resource_url=?', (url,)).fetchone()
    if row:
        course_access(row[0])
    else:
        row = get_db().execute('SELECT a.course_id, s.student_id FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.attach_file=?', (url,)).fetchone()
        if row is None or (g.user[4] == 1 and row[1] != g.user[0]):
            abort(404)
        course_access(row[0])
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
