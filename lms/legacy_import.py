"""Import literal rows from the original MySQL dump without executing its SQL."""
import hashlib
import re
import shutil
import secrets
import sqlite3
import csv
from contextlib import closing
from datetime import datetime
from pathlib import Path

import click
from flask import current_app

from .db import get_db
from .security import hash_password

TABLE_ORDER = ('users', 'courses', 'forums', 'assignments', 'enrollments', 'ins_crs_assignments',
               'lectures', 'user_forum_memberships', 'forum_posts', 'comments', 'messages', 'submissions', 'notifications')
TOKEN = re.compile(r"\s*(?:'((?:\\.|''|[^'])*)'|(-?\d+)|(NULL)|([(),]))", re.S | re.I)


def literal_rows(text):
    """Only quoted strings, integers and NULL are accepted as dump values."""
    position, rows, row, expect_value = 0, [], None, False
    while position < len(text.rstrip()):
        match = TOKEN.match(text, position)
        if match is None:
            raise ValueError('Unsupported data in legacy INSERT.')
        position = match.end()
        string, number, null, punctuation = match.groups()
        if punctuation == '(' and row is None:
            row, expect_value = [], True
        elif punctuation == ')' and row is not None and not expect_value:
            rows.append(row)
            row = None
        elif punctuation == ',' and row is not None and not expect_value:
            expect_value = True
        elif punctuation == ',' and row is None and rows:
            continue
        elif punctuation is None and row is not None and expect_value:
            if string is not None:
                escapes = {'0': '\0', 'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'Z': '\x1a'}
                value = re.sub(r'\\(.)', lambda m: escapes.get(m[1], m[1]), string.replace("''", "'"))
            else:
                value = int(number) if number is not None else None
            row.append(value)
            expect_value = False
        else:
            raise ValueError('Malformed legacy row.')
    if row is not None:
        raise ValueError('Unclosed legacy row.')
    return rows


def read_dump(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    records = {}
    # A semicolon inside a string belongs to that string, not the statement terminator.
    pattern = r"INSERT INTO `([a-z_]+)`\s*\(([^)]+)\) VALUES\s*((?:'(?:\\.|''|[^'])*'|[^';])+);"
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != len(re.findall(r'^INSERT INTO ', text, re.M)):
        raise ValueError('Some legacy INSERT statements could not be parsed.')
    for match in matches:
        table, columns, values = match.groups()
        if table not in TABLE_ORDER:
            raise ValueError(f'Unsupported table: {table}')
        names = re.findall(r'`([a-z_]+)`', columns)
        if not names or 'id' not in names:
            raise ValueError('Legacy rows must have explicit IDs and columns.')
        for values in literal_rows(values):
            if len(values) != len(names):
                raise ValueError(f'Column count mismatch in {table}.')
            records.setdefault(table, []).append(dict(zip(names, values)))
    if not records:
        raise ValueError('No legacy INSERT rows were found.')
    return records


def import_dump(path):
    db = get_db()
    records = read_dump(path)
    report = dict(imported=0, existing=0, missing_files=[], counts={}, credentials=[])
    files = {}
    for table in ('lectures', 'submissions'):
        field = 'resource_url' if table == 'lectures' else 'attach_file'
        for row in records.get(table, []):
            old_path = row.get(field)
            if not old_path:
                continue
            filename = old_path.replace('\\', '/').rsplit('/', 1)[-1]
            if filename in ('', '.', '..') or ':' in filename:
                raise ValueError('Invalid legacy filename.')
            destination = f'legacy-{table}-{row["id"]}-' + hashlib.sha256(filename.encode()).hexdigest()[:24] + Path(filename).suffix.lower()
            row[field] = '/files/' + destination
            files[destination] = filename
    try:
        db.execute('SAVEPOINT legacy_import')
        for table in TABLE_ORDER:
            allowed = {column[1] for column in db.execute(f'PRAGMA table_info({table})')}
            for row in records.get(table, []):
                if not row.keys() <= allowed:
                    raise ValueError(f'Unknown columns in {table}.')
                names = list(row)
                columns = ', '.join(names)
                existing = db.execute(f'SELECT {columns} FROM {table} WHERE id=?', (row['id'],)).fetchone()
                if existing:
                    comparable = dict(zip(names, existing))
                    if table == 'users':
                        comparable.pop('password')
                    expected = {name: value for name, value in row.items() if table != 'users' or name != 'password'}
                    if comparable != expected:
                        raise ValueError(f'ID conflict in {table}, id={row["id"]}. Existing data was not overwritten.')
                    report['existing'] += 1
                    continue
                if table == 'users':
                    password = secrets.token_urlsafe(12)
                    row['password'] = hash_password(password)
                    report['credentials'].append({'id': row['id'], 'firstname': row['firstname'],
                                                  'lastname': row['lastname'], 'role_id': row['role_id'], 'password': password})
                placeholders = ', '.join('?' for _ in names)
                db.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(row[name] for name in names))
                report['imported'] += 1
                report['counts'][table] = report['counts'].get(table, 0) + 1
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Imported data contains broken foreign keys.')
        db.execute('RELEASE legacy_import')
        db.commit()
    except Exception:
        db.execute('ROLLBACK TO legacy_import')
        db.execute('RELEASE legacy_import')
        raise
    source_root = (Path(current_app.static_folder) / 'files').resolve()
    for destination, filename in files.items():
        source = (source_root / filename).resolve()
        if not source.is_relative_to(source_root):
            raise ValueError('Legacy attachment is outside the upload directory.')
        target = Path(current_app.config['UPLOAD_FOLDER']) / destination
        if source.is_file() and not target.exists():
            shutil.copyfile(source, target)
        elif not target.is_file() and filename not in report['missing_files']:
            report['missing_files'].append(filename)
    return report


def register(app):
    @app.cli.command('import-legacy')
    @click.option('--dump', type=click.Path(exists=True, dir_okay=False), default=str(Path(__file__).resolve().parent.parent / 'data' / 'legacy_mysql.sql'))
    def import_command(dump):
        """Import the original dump, preserving IDs and refusing conflicting data."""
        try:
            backup_directory = Path(current_app.config['DATABASE']).resolve().parent / 'backups'
            backup_directory.mkdir(exist_ok=True)
            backup_path = backup_directory / ('before-legacy-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.sqlite3')
            with closing(sqlite3.connect(backup_path)) as backup:
                get_db().backup(backup)
            report = import_dump(dump)
        except (ValueError, sqlite3.Error) as error:
            raise click.ClickException(str(error)) from error
        click.echo(f'Imported {report["imported"]} rows; {report["existing"]} already present.')
        for table, count in report['counts'].items():
            click.echo(f'{table}: {count}')
        if report['credentials']:
            credentials_path = Path(current_app.config['DATABASE']).resolve().parent / ('legacy-credentials-' + secrets.token_hex(3) + '.csv')
            with credentials_path.open('x', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['id', 'firstname', 'lastname', 'role_id', 'password'])
                writer.writeheader()
                writer.writerows(report['credentials'])
            click.echo(f'Generated passwords saved to {credentials_path}')
        if report['missing_files']:
            click.echo('Missing original attachments: ' + ', '.join(report['missing_files']))
