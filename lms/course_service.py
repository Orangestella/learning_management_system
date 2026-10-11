"""Keep course records and instructor assignments in the same transaction."""
from flask import abort
from .db import get_db


def instructor_ids(text):
    parts = text.split()
    if not parts or any(not part.isdecimal() or len(part) > 18 for part in parts):
        abort(400, 'Instructor IDs must be numbers separated by spaces.')
    identifiers = list(dict.fromkeys(int(part) for part in parts))
    for identifier in identifiers:
        if not get_db().execute('SELECT id FROM users WHERE id=? AND role_id=2', (identifier,)).fetchone():
            abort(400, 'Every instructor ID must belong to an instructor.')
    return identifiers


def save_course(data, course_id=None):
    db = get_db()
    instructors = instructor_ids(data['ins_ids'])
    fields = (data['course_name'].strip(), data['session'].strip(), instructors[0], data.get('description', ''))
    if course_id is None:
        cursor = db.execute('INSERT INTO courses(name, session, leader_id, description) VALUES (?, ?, ?, ?)', fields)
        course_id = cursor.lastrowid
    else:
        cursor = db.execute('UPDATE courses SET name=?, session=?, leader_id=?, description=? WHERE id=?', fields + (course_id,))
        if cursor.rowcount == 0:
            abort(404)
        db.execute('DELETE FROM ins_crs_assignments WHERE crs_id=?', (course_id,))
    db.executemany('INSERT INTO ins_crs_assignments(ins_id, crs_id) VALUES (?, ?)',
                   [(identifier, course_id) for identifier in instructors])
    return course_id
