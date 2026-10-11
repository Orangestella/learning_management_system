from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from datetime import datetime
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu, fill_bar_ins
from ..uploads import save_upload
bp = flask.Blueprint('materials', __name__)

@bp.route('/assignment', methods=['GET'])
@require_roles(0)
def assignment():
    items = search_rows('assignment', "SELECT a.id, a.name, (c.name || ' ' || c.session), a.deadline FROM assignments a JOIN courses c ON c.id=a.course_id WHERE 1", order_by='a.id')
    return render('console.html', items=items, firstname=session['name'], type='assignment')

@bp.route('/lecture', methods=['GET'])
@require_roles(0)
def lecture():
    items = search_rows('lecture', "SELECT l.id, l.name, (c.name || ' ' || c.session), l.resource_url FROM lectures l JOIN courses c ON c.id=l.course_id WHERE 1", order_by='l.id')
    return render('console.html', items=items, firstname=session['name'], type='lecture')

@bp.route('/assignment/create', methods=['GET', 'POST'])
@require_roles(0, 2)
def create_assignment():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        return render('assignment.html', title='Create new assignment', edit=False)
    else:
        try:
            asn_name = flask.request.form['asn_name']
            crs_id = flask.request.form['crs_id']
            ddl = flask.request.form['ddl']
            desc_asn = flask.request.form['desc_asn']
            query = 'INSERT INTO assignments (name, course_id, deadline, description) VALUES (?, ?, ?, ?)'
            value = (asn_name, crs_id, ddl, desc_asn)
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new assignment successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/assignment/delete', methods=['POST'])
@require_roles(0)
def delete_assignment():
    cursor = get_db().cursor()
    try:
        asn_id = flask.request.args['id']
        query = 'DELETE FROM assignments WHERE id=?'
        value = (asn_id,)
        cursor.execute(query, value)
        return flask.redirect('/assignment')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/assignment')

@bp.route('/assignment/edit', methods=['GET', 'POST'])
@require_roles(0)
def edit_assignment():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        query = 'SELECT * FROM assignments WHERE id=?'
        value = (flask.request.args['id'],)
        cursor.execute(query, value)
        result = cursor.fetchone()
        return render('assignment.html', title='Edit assignment', edit=True, a_id=result[0], asn_name=result[1], crs_id=result[2], ddl=result[3], desc_asn=result[4])
    else:
        a_id = flask.request.form['a_id']
        asn_name = flask.request.form['asn_name']
        crs_id = flask.request.form['crs_id']
        ddl = flask.request.form['ddl']
        desc_asn = flask.request.form['desc_asn']
        try:
            query = 'UPDATE assignments SET name=?, course_id=?, deadline=?, description=? WHERE id=?'
            value = (asn_name, crs_id, ddl, desc_asn, a_id)
            cursor.execute(query, value)
            return flask.jsonify({'status': 'success', 'message': 'Edit assignment successfully.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return flask.jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/lecture/delete', methods=['POST'])
@require_roles(0, 2)
def delete_lecture():
    cursor = get_db().cursor()
    try:
        lec_id = flask.request.args['id']
        query = 'DELETE FROM lectures WHERE id=?'
        value = (lec_id,)
        cursor.execute(query, value)
        if session['role_id'] == 0:
            return flask.redirect('/lecture')
        elif session['role_id'] == 2:
            return flask.redirect('/')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/lecture')

@bp.route('/lecture/create', methods=['GET', 'POST'])
@require_roles(0, 2)
def create_lecture():
    cursor = get_db().cursor()
    if request.method == 'GET':
        if session['role_id'] == 0:
            return render('lecture_window.html', title='Create new lecture', edit=False)
        else:
            crs_id = request.args['id']
            return render('lecture_window.html', title='Create new lecture', edit=False, crs_id=crs_id)
    else:
        try:
            lec_title = flask.request.form['lec_title']
            crs_id = flask.request.form['crs_id']
            rse = flask.request.files['rse']
            desc_lec = flask.request.form['desc_lec']
            rse_url = save_upload(rse)
            date = datetime.now()
            query = 'INSERT INTO lectures (course_id, name, resource_url, description, upload_date) VALUES (?, ?, ?, ?, ?)'
            value = (crs_id, lec_title, rse_url, desc_lec, date.strftime('%Y-%m-%d'))
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new assignment successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/lecture/edit', methods=['GET', 'POST'])
@require_roles(0, 2)
def edit_lecture():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        lec_id = flask.request.args['id']
        query = 'SELECT course_id, name, description FROM lectures WHERE id=?'
        value = (lec_id,)
        cursor.execute(query, value)
        result1 = cursor.fetchone()
        if result1 is None:
            return flask.redirect('/course')
        return render('lecture_window.html', title='Edit lecture', edit=True, l_id=lec_id, lec_title=result1[1], crs_id=result1[0], desc_lec=result1[2])
    else:
        l_id = flask.request.form['l_id']
        lec_title = flask.request.form['lec_title']
        crs_id = flask.request.form['crs_id']
        rse = flask.request.files.get('rse')
        if rse and rse.filename:
            rse_url = save_upload(rse)
        else:
            query_url = 'SELECT resource_url FROM lectures WHERE id=?'
            value_url = (l_id,)
            cursor.execute(query_url, value_url)
            result1 = cursor.fetchone()
            rse_url = result1[0]
        desc_lec = flask.request.form['desc_lec']
        query = 'UPDATE lectures SET name=?, course_id=?, resource_url=?, description=? WHERE id=?'
        value = (lec_title, crs_id, rse_url, desc_lec, l_id)
        try:
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Edit lecture successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this lecture.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/assignment/<int:asn_id>', methods=['GET', 'POST'])
@require_roles(1, 2)
def assignment_details(asn_id):
    cursor = get_db().cursor()
    if session['role_id'] == 1:
        if flask.request.method == 'GET':
            info = fill_bar_stu(session['userid'])
            ids = []
            for a_id in info[2]:
                ids.append(a_id[2])
            if int(asn_id) not in ids:
                return flask.abort(404)
            query = "SELECT a.*, (COALESCE(c.name, '') || ' ' || COALESCE(c.session, '')) FROM assignments AS a INNER JOIN courses AS c ON c.id = a.course_id WHERE a.id = ?"
            value = (int(asn_id),)
            cursor.execute(query, value)
            items = cursor.fetchone()
            return render('assignment_stu.html', items=items, firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])
        else:
            try:
                asn_file = flask.request.files['asn_file']
                asn_url = save_upload(asn_file)
                date = datetime.now().strftime('%Y-%m-%d')
                query = 'INSERT INTO submissions (assignment_id, student_id, submission_date, attach_file) VALUES (?, ?, ?, ?)'
                value = (int(asn_id), session['userid'], date, asn_url)
                cursor.execute(query, value)
                return flask.jsonify({'status': 'success', 'message': 'You have successfully submitted'})
            except Exception:
                flask.current_app.logger.exception('Operation failed')
                get_db().rollback()
                return flask.jsonify({'status': 'error', 'message': 'Unable to complete the operation.'})
    elif session['role_id'] == 2:
        if flask.request.method == 'GET':
            info = fill_bar_ins(session['userid'])
            ids = []
            for a_id in info[1]:
                ids.append(a_id[-1])
            if int(asn_id) not in ids:
                return flask.abort(404)
            items = search_rows('submission', "SELECT s.id, (u.firstname || ' ' || u.lastname), s.submission_date, s.attach_file FROM submissions s JOIN users u ON u.id=s.student_id WHERE s.assignment_id=?", (asn_id,), order_by='s.id DESC')
            return render('ins_table.html', items=items, firstname=session['name'], courses=info[0], assignments=info[1], edit=False, type='submission')

@bp.route('/grade/<int:sub_id>', methods=['GET'])
@require_roles(1)
def submission_details(sub_id):
    cursor = get_db().cursor()
    info = fill_bar_stu(session['userid'])
    query = "SELECT (COALESCE(a.name, '') || ' ' || COALESCE(c.name, '') || ' ' || COALESCE(c.session, '')), s.score, s.feedback FROM submissions AS s INNER JOIN assignments AS a ON a.id = s.assignment_id INNER JOIN courses AS c ON c.id = a.course_id WHERE s.id = ? AND s.student_id=? AND s.score IS NOT NULL"
    value = (int(sub_id), session['userid'])
    cursor.execute(query, value)
    items = cursor.fetchone()
    if items is None:
        flask.abort(404)
    return render('grade.html', items=items, firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])

@bp.route('/submission/eval', methods=['GET', 'POST'])
@require_roles(2)
def eval_submission():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        sub_id = flask.request.args.get('id')
        query = 'SELECT id, assignment_id, score, feedback FROM submissions WHERE id = ?'
        value = (sub_id,)
        try:
            cursor.execute(query, value)
            items = cursor.fetchone()
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            return flask.abort(404)
        if items[2] is None or items[3] is None or items[2] == '' or (items[3] == ''):
            return render('eval_window.html', s_id=items[0], a_id=items[1])
        else:
            return render('eval_window.html', s_id=items[0], a_id=items[1], score=items[2], fb=items[3])
    else:
        sub_id = flask.request.form.get('s_id')
        score = flask.request.form.get('score')
        feedback = flask.request.form.get('fb')
        query = 'UPDATE submissions SET score = ?, feedback = ? WHERE id = ?'
        value = (score, feedback, sub_id)
        try:
            cursor.execute(query, value)
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})
        return flask.jsonify({'status': 'success', 'message': 'Submission evaluated successful.'})
