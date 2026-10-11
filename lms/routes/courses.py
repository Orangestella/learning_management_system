from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from datetime import datetime
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu, fill_bar_ins
from ..course_service import save_course
bp = flask.Blueprint('courses', __name__)

@bp.route('/course', methods=['GET'])
@require_roles(0)
def course():
    items = search_rows('course', "SELECT c.id, c.name, (u.firstname || ' ' || u.lastname), u.id, c.session FROM courses c JOIN users u ON u.id=c.leader_id WHERE 1", order_by='c.id')
    return render('console.html', items=items, firstname=session['name'], type='course')

@bp.route('/course/create', methods=['GET', 'POST'])
@require_roles(0)
def create_course():
    if request.method == 'GET':
        return render('course_window.html', title='Create new course', edit=False)
    save_course(request.form)
    return jsonify(status='success', message='Course created successfully.')

@bp.route('/course/delete', methods=['POST'])
@require_roles(0)
def delete_course():
    get_db().execute('DELETE FROM courses WHERE id=?', (request.args['id'],))
    return flask.redirect('/course')

@bp.route('/course/edit', methods=['GET', 'POST'])
@require_roles(0)
def edit_course():
    if request.method == 'POST':
        save_course(request.form, request.form['c_id'])
        return jsonify(status='success', message='Course updated successfully.')
    course_id = request.args['id']
    db = get_db()
    course = db.execute('SELECT name, description, session FROM courses WHERE id=?', (course_id,)).fetchone()
    if course is None:
        flask.abort(404)
    instructors = db.execute('SELECT ins_id FROM ins_crs_assignments WHERE crs_id=? ORDER BY id', (course_id,)).fetchall()
    return render('course_window.html', title='Edit course', edit=True, id=course_id, crs_name=course[0], desc=course[1], crs_session=course[2], ids=' '.join((str(row[0]) for row in instructors)))

@bp.route('/course/<int:crs_id>', methods=['GET'])
@require_roles(1, 2)
def get_course(crs_id):
    items = search_rows('lecture', 'SELECT l.id, l.name, l.resource_url, l.description, l.upload_date FROM lectures l JOIN courses c ON c.id=l.course_id WHERE l.course_id=?', (crs_id,), order_by='l.id')
    if session['role_id'] == 1:
        info = fill_bar_stu(session['userid'])
        return render('non_admin_table.html', items=items, type='lecture', firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])
    info = fill_bar_ins(session['userid'])
    return render('ins_table.html', edit=True, items=items, type='lecture', firstname=session['name'], courses=info[0], assignments=info[1], crs_id=crs_id)

@bp.route('/course/enroll/request', methods=['GET'])
@require_roles(0)
def enroll_view():
    items = search_rows('enrollment requests', "SELECT e.id, (u.firstname || ' ' || u.lastname), u.id, c.name, c.session FROM enrollments e JOIN users u ON u.id=e.student_id JOIN courses c ON c.id=e.course_id WHERE e.status=?", ('under review',), order_by='e.id')
    return render('console.html', items=items, firstname=session['name'], type='enrollment requests')

@bp.route('/enroll', methods=['GET'])
@require_roles(1)
def student_enroll():
    info = fill_bar_stu(session['userid'])
    items = search_rows('course', "SELECT c.id, c.name, c.session, (u.firstname || ' ' || u.lastname) FROM courses c JOIN users u ON u.id=c.leader_id WHERE NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.course_id=c.id AND e.student_id=?)", (session['userid'],), order_by='c.id')
    return render('non_admin_table.html', items=items, type='enroll', firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])

@bp.route('/enroll/request/send', methods=['POST'])
@require_roles(1)
def enroll_send_request():
    cursor = get_db().cursor()
    crs_id = request.args['id']
    try:
        query = 'INSERT INTO enrollments (student_id, course_id, enrollment_date, status) VALUES (?, ?, ?, ?)'
        value = (session['userid'], crs_id, datetime.today().strftime('%Y-%m-%d'), 'under review')
        cursor.execute(query, value)
        return flask.redirect('/enroll')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/enroll')

@bp.route('/course/enroll/receive', methods=['POST'])
@require_roles(0)
def course_enroll_receive():
    cursor = get_db().cursor()
    erl_id = request.args['id']
    try:
        query = 'UPDATE enrollments SET status=? WHERE id=?'
        value = ('received', erl_id)
        cursor.execute(query, value)
        return flask.redirect('/course/enroll/request')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/course/enroll/request')

@bp.route('/course/enroll/deny', methods=['POST'])
@require_roles(0)
def course_enroll_deny():
    cursor = get_db().cursor()
    erl_id = request.args['id']
    try:
        query = 'DELETE FROM enrollments WHERE id=?'
        value = (erl_id,)
        cursor.execute(query, value)
        return flask.redirect('/course/enroll/request')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/course/enroll/request')

@bp.route('/student/<int:crs_id>', methods=['GET'])
@require_roles(2)
def students(crs_id):
    info = fill_bar_ins(session['userid'])
    items = search_rows('student', "SELECT u.id, u.firstname, u.lastname FROM users u JOIN enrollments e ON e.student_id=u.id WHERE e.course_id=? AND e.status='received'", (crs_id,), order_by='u.id')
    return render('ins_table.html', items=items, firstname=session['name'], type='student', courses=info[0], assignments=info[1])
