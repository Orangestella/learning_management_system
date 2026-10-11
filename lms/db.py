"""SQLite connections and one transaction per request."""
import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=15)
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA busy_timeout = 15000')
    return g.db


def init_db():
    get_db().executescript((Path(__file__).resolve().parent.parent / 'db.sql').read_text(encoding='utf-8'))
    get_db().commit()


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.rollback()
        db.close()


def finish_transaction(response):
    db = g.get('db')
    committed = False
    if db is not None:
        data = response.get_json(silent=True) if response.is_json else None
        if response.status_code < 400 and (not data or data.get('status') == 'success'):
            db.commit()
            committed = True
        else:
            db.rollback()
    for path in g.get('pending_uploads', []):
        if not committed:
            path.unlink(missing_ok=True)
    return response


def register(app):
    app.teardown_appcontext(close_db)
    app.after_request(finish_transaction)

    @app.cli.command('init-db')
    def init_command():
        """Create missing tables without deleting existing data."""
        init_db()
        click.echo('SQLite schema initialized.')

    @app.cli.command('create-admin')
    @click.option('--firstname', prompt=True)
    @click.option('--lastname', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def admin_command(firstname, lastname, password):
        """Create an administrator with a password entered privately."""
        from .security import hash_password
        if not firstname.strip() or not lastname.strip():
            raise click.ClickException('Names cannot be empty.')
        try:
            hashed = hash_password(password)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        cursor = get_db().execute('INSERT INTO users(firstname, lastname, password, role_id) VALUES (?, ?, ?, 0)',
                                  (firstname.strip(), lastname.strip(), hashed))
        get_db().commit()
        click.echo(f'Administrator created. Login ID: {cursor.lastrowid}')
