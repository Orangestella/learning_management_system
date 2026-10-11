"""One search grammar and field allowlist for every list view."""
import re
from dataclasses import dataclass

from flask import g, request
from .db import get_db


@dataclass(frozen=True)
class Field:
    label: str
    expression: str
    kind: str = 'text'


FULLNAME = "(u.firstname || ' ' || u.lastname)"
FIELDS = {
    'account': {'id': Field('ID', 'id', 'number'), 'name': Field('Name', "(firstname || ' ' || lastname)"),
                'firstname': Field('First name', 'firstname'), 'lastname': Field('Last name', 'lastname'), 'role': Field('Role', 'role_id', 'role')},
    'course': {'id': Field('Course ID', 'c.id', 'number'), 'name': Field('Course name', 'c.name'),
               'instructor': Field('Lead instructor', FULLNAME), 'instructor_id': Field('Instructor ID', 'u.id', 'number'),
               'session': Field('Session', 'c.session'), 'description': Field('Description', 'c.description')},
    'assignment': {'id': Field('Assignment ID', 'a.id', 'number'), 'name': Field('Assignment name', 'a.name'),
                   'course': Field('Course name', 'c.name'), 'course_id': Field('Course ID', 'c.id', 'number'),
                   'deadline': Field('Deadline', 'a.deadline', 'date'), 'description': Field('Description', 'a.description')},
    'lecture': {'id': Field('Resource ID', 'l.id', 'number'), 'name': Field('Resource name', 'l.name'),
                'course': Field('Course name', 'c.name'), 'course_id': Field('Course ID', 'c.id', 'number'),
                'description': Field('Description', 'l.description'), 'date': Field('Upload date', 'l.upload_date', 'date')},
    'forum': {'id': Field('Forum ID', 'f.id', 'number'), 'name': Field('Forum name', 'f.name')},
    'membership': {'id': Field('Membership ID', 'm.id', 'number'), 'name': Field('Name', FULLNAME),
                   'firstname': Field('First name', 'u.firstname'), 'lastname': Field('Last name', 'u.lastname'),
                   'student_id': Field('Student ID', 'u.id', 'number')},
    'enrollment requests': {'id': Field('Request ID', 'e.id', 'number'), 'student': Field('Student name', FULLNAME),
                            'student_id': Field('Student ID', 'u.id', 'number'), 'course': Field('Course name', 'c.name'),
                            'course_id': Field('Course ID', 'c.id', 'number'), 'session': Field('Session', 'c.session')},
    'student': {'id': Field('Student ID', 'u.id', 'number'), 'name': Field('Name', FULLNAME),
                'firstname': Field('First name', 'u.firstname'), 'lastname': Field('Last name', 'u.lastname')},
    'submission': {'id': Field('Submission ID', 's.id', 'number'), 'student': Field('Student name', FULLNAME),
                   'student_id': Field('Student ID', 'u.id', 'number'), 'date': Field('Submitted', 's.submission_date', 'date'),
                   'score': Field('Score', 's.score', 'number')},
    'messages': {'id': Field('Message ID', 'm.id', 'number'), 'sender': Field('Sender', FULLNAME),
                 'sender_id': Field('Sender ID', 'u.id', 'number'), 'content': Field('Content', 'm.content'),
                 'date': Field('Sent', 'm.send_time', 'date')},
    'notification': {'id': Field('Notification ID', 'n.id', 'number'), 'title': Field('Title', 'n.title'),
                     'content': Field('Content', 'n.content'), 'sender': Field('Sender', FULLNAME),
                     'sender_id': Field('Sender ID', 'u.id', 'number'), 'course': Field('Course name', 'c.name'),
                     'course_id': Field('Course ID', 'c.id', 'number'), 'date': Field('Sent', 'n.send_date', 'date')},
    'posts': {'id': Field('Topic ID', 'p.id', 'number'), 'sender': Field('Author', FULLNAME),
              'sender_id': Field('Author ID', 'u.id', 'number'), 'content': Field('Content', 'p.content'),
              'date': Field('Posted', 'p.date', 'date')},
}
ALIASES = {'crs': 'course', 'ins': 'instructor', 'asn': 'name', 'lec': 'name', 'sen': 'sender', 'con': 'content'}
ROLE_VALUES = {'admin': 0, 'student': 1, 'instructor': 2, '管理员': 0, '学生': 1, '教师': 2, '0': 0, '1': 1, '2': 2}


def profile_for(kind):
    return {'enroll': 'course', 'join forum': 'forum'}.get(kind, kind)


def field_name(profile, name):
    name = ALIASES.get(name.lower(), name.lower())
    if profile == 'course' and name == 'course':
        name = 'name'
    return name


def search_metadata(kind):
    profile = profile_for(kind)
    fields = FIELDS[profile]
    example_field = next(name for name, field in fields.items() if field.kind == 'text')
    return dict(fields=fields, selected=field_name(profile, request.args.get('search_field', 'all')),
                example=f'{example_field}:"English" id:>=1',
                date_field=next((name for name, field in fields.items() if field.kind == 'date'), None),
                keyword=request.args.get('items_keyword', ''), error=getattr(g, 'search_error', None))


def condition(field, value, explicit=True):
    match = re.match(r'^(>=|<=|>|<|=)(.*)$', value)
    operator, text = match.groups() if match else ('', value)
    if not text:
        raise ValueError('A search condition needs a value.')
    if field.kind in ('number', 'role'):
        converted = ROLE_VALUES.get(text.lower()) if field.kind == 'role' else int(text) if re.fullmatch(r'[0-9]{1,18}', text) else None
        if converted is None:
            if explicit:
                raise ValueError('IDs and scores must be non-negative integers. Roles: admin, student, instructor.')
            return None
        return f'{field.expression} {operator or "="} ?', [converted]
    if field.kind == 'date':
        from datetime import datetime
        try:
            datetime.fromisoformat(text)
        except ValueError:
            if explicit:
                raise ValueError('Use YYYY-MM-DD or YYYY-MM-DDTHH:MM for dates.')
            return None
        # Prefix equality matches an entire day; range comparisons normalize old and new timestamps.
        if not operator or operator == '=':
            return f'REPLACE({field.expression}, "T", " ") LIKE ? ESCAPE \'\\\'', [text.replace('T', ' ') + '%']
        expression = f'julianday(REPLACE({field.expression}, ",", ""))'
        return f'{expression} {operator} julianday(?)', [text]
    if operator and operator != '=':
        raise ValueError('Text fields support contains matching or = for an exact match.')
    if operator == '=':
        return f'{field.expression} = ? COLLATE NOCASE', [text]
    escaped = text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'{field.expression} LIKE ? ESCAPE \'\\\'', ['%' + escaped + '%']


def compile_search(profile, keyword, scope='all'):
    """Implicit AND, explicit OR, quoted phrases and negative terms; never raw SQL."""
    profile = profile_for(profile)
    fields = FIELDS[profile]
    scope = field_name(profile, scope)
    if scope != 'all' and scope not in fields:
        raise ValueError('Unknown search scope.')
    if len(keyword) > 1024:
        raise ValueError('Search is limited to 1024 characters.')
    # Preserve old prefixes while giving new syntax consistent field meanings.
    legacy = re.match(r'^(crs|ins|asn|lec|sen|con)\s+(.+)$', keyword.strip(), re.I)
    if legacy:
        name = field_name(profile, legacy[1])
        if legacy[2].isdecimal():
            name = {'name': 'id', 'course': 'course_id', 'instructor': 'instructor_id', 'sender': 'sender_id'}.get(name, name)
        keyword = name + ':"' + legacy[2].replace('"', '') + '"'
    if keyword.count('"') % 2:
        raise ValueError('Unclosed quote. Wrap phrases in double quotes.')
    tokens = re.findall(r'(?:"[^"]*"|[^\s"]+)+', keyword)
    if len(tokens) > 32:
        raise ValueError('Use at most 32 search terms.')
    groups, current, parameters = [], [], []
    expecting_term = True
    for token in tokens:
        if token.upper() in ('AND', 'OR'):
            if expecting_term:
                raise ValueError('AND and OR need search conditions on both sides.')
            if token.upper() == 'OR':
                groups.append(' AND '.join(current))
                current = []
            expecting_term = True
            continue
        token = token.replace('"', '')
        negative = token.startswith('-')
        term = token[1:] if negative else token
        if not term:
            raise ValueError('An exclusion needs a keyword.')
        if ':' in term:
            name, value = term.split(':', 1)
            name = field_name(profile, name)
            if name not in fields:
                raise ValueError(f'Unknown field {name}. Click ? to see available fields.')
            options = [condition(fields[name], value)]
        else:
            selected = fields.values() if scope == 'all' else [fields[scope]]
            options = [result for field in selected if (result := condition(field, term, explicit=scope != 'all'))]
        if not options:
            options = [('0', [])]
        expression = '(' + ' OR '.join(result[0] for result in options) + ')'
        current.append(('NOT COALESCE(' + expression + ', 0)' if negative else expression))
        for _, args in options:
            parameters.extend(args)
        expecting_term = False
    if tokens and expecting_term:
        raise ValueError('AND and OR need search conditions on both sides.')
    if current:
        groups.append(' AND '.join(current))
    return '(' + ' OR '.join('(' + group + ')' for group in groups) + ')' if groups else '1', parameters


def search_rows(profile, query, args=(), order_by=None):
    try:
        condition_sql, parameters = compile_search(profile, request.args.get('items_keyword', ''), request.args.get('search_field', 'all'))
    except ValueError as error:
        g.search_error = str(error)
        return []
    # query always supplies WHERE and its authorization predicate before these parentheses.
    sql = query + ' AND ' + condition_sql
    if order_by:
        sql += ' ORDER BY ' + order_by
    return get_db().execute(sql, tuple(args) + tuple(parameters)).fetchall()
