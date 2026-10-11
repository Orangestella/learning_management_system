"""Application factory. Uses Flask and the Python standard library only."""
import os
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from . import db, security


def create_app(config=None):
    root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(root / 'templates'), static_folder=str(root / 'static'),
                instance_path=str(root / 'instance'))
    app.config.from_mapping(
        DATABASE=str(root / 'instance' / 'lms.sqlite3'),
        UPLOAD_FOLDER=str(root / 'instance' / 'uploads'),
        SECRET_KEY=os.environ.get('LMS_SECRET_KEY'),
        SESSION_COOKIE_NAME='lms_session', SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('LMS_HTTPS') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024, ALLOWED_EXTENSIONS={'pdf', 'doc', 'docx'},
    )
    if config:
        app.config.update(config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        key_file = Path(app.instance_path) / 'secret.key'
        try:
            with key_file.open('x', encoding='ascii') as stream:
                stream.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = key_file.read_text(encoding='ascii').strip()
    db.register(app)
    from . import legacy_import
    legacy_import.register(app)
    security.register(app)
    from .routes import auth, dashboard, accounts, courses, materials, forums, messages, notifications
    from .uploads import bp as uploads
    for module in (auth, dashboard, accounts, courses, materials, forums, messages, notifications):
        app.register_blueprint(module.bp)
    app.register_blueprint(uploads)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(status='error', message=error.description), error.code

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(status='error', message='Invalid input.'), 400

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception('Database operation failed')
        return jsonify(status='error', message='Unable to save the change. Check the input and try again.'), 409

    with app.app_context():
        db.init_db()
    return app
