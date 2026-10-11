from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from datetime import datetime
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu, fill_bar_ins
bp = flask.Blueprint('notifications', __name__)

@bp.route('/notification', methods=['GET'])
@require_roles(1, 2)
def notification():
    if session['role_id'] == 1:
        info = fill_bar_stu(session['userid'])
        query = "SELECT n.id, (u.firstname || ' ' || u.lastname), n.title, n.send_date FROM notifications n JOIN users u ON u.id=n.sender_id JOIN courses c ON c.id=n.crs_id WHERE EXISTS (SELECT 1 FROM enrollments e WHERE e.course_id=n.crs_id AND e.student_id=? AND e.status='received')"
        items = search_rows('notification', query, (session['userid'],), order_by='n.id DESC')
        return render('non_admin_table.html', items=items, type='notification', firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])
    info = fill_bar_ins(session['userid'])
    query = 'SELECT n.id, n.title, n.send_date FROM notifications n JOIN users u ON u.id=n.sender_id JOIN courses c ON c.id=n.crs_id WHERE n.sender_id=?'
    items = search_rows('notification', query, (session['userid'],), order_by='n.id DESC')
    return render('ins_table.html', items=items, type='notification', firstname=session['name'], edit=True, courses=info[0], assignments=info[1])

@bp.route('/notification/view', methods=['GET', 'POST'])
@require_roles(1, 2)
def notification_view():
    cursor = get_db().cursor()
    notification_id = request.args.get('id')
    if notification_id is None:
        return flask.redirect('/notification')
    query = "SELECT (COALESCE(u.firstname, '') || ' ' || COALESCE(u.lastname, '')), n.title, n.content, n.send_date FROM notifications AS n INNER JOIN users AS u ON n.sender_id = u.id WHERE n.id=?"
    value = (notification_id,)
    cursor.execute(query, value)
    notification_info = cursor.fetchone()
    if notification_info is None:
        return flask.abort(404)
    return render('notification_window.html', info=notification_info)

@bp.route('/notification/create', methods=['GET', 'POST'])
@require_roles(2)
def notification_create():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        return render('create_notification.html', edit=False)
    else:
        title = flask.request.form.get('title')
        content = flask.request.form.get('content')
        send_date = datetime.now().strftime('%Y-%m-%d')
        crs_id = flask.request.form.get('crs_id')
        query = 'INSERT INTO notifications (title, content, send_date, crs_id, sender_id) VALUES (?, ?, ?, ?, ?)'
        value = (title, content, send_date, crs_id, session['userid'])
        try:
            cursor.execute(query, value)
            return flask.jsonify({'status': 'success', 'message': 'Notification creation successful.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/notification/delete', methods=['POST'])
@require_roles(2)
def notification_delete():
    cursor = get_db().cursor()
    ntf_id = flask.request.args.get('id')
    query = 'DELETE FROM notifications WHERE id = ?'
    value = (ntf_id,)
    cursor.execute(query, value)
    return flask.redirect('/notification')

@bp.route('/notification/edit', methods=['GET', 'POST'])
@require_roles(2)
def notification_edit():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        ntf_id = flask.request.args.get('id')
        query = 'SELECT content, title, crs_id FROM notifications WHERE id = ?'
        value = (ntf_id,)
        cursor.execute(query, value)
        items = cursor.fetchone()
        return render('create_notification.html', id=ntf_id, content=items[0], title=items[1], crs_id=items[2], edit=True)
    else:
        ntf_id = flask.request.form.get('id')
        title = flask.request.form.get('title')
        content = flask.request.form.get('content')
        send_date = datetime.now().strftime('%Y-%m-%d')
        crs_id = flask.request.form.get('crs_id')
        query = 'UPDATE notifications SET title = ?, content = ?, send_date = ?, crs_id = ? WHERE id = ?'
        value = (title, content, send_date, crs_id, ntf_id)
        try:
            cursor.execute(query, value)
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})
        return flask.jsonify({'status': 'success', 'message': 'Notification edit successful.'})
