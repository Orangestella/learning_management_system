from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from datetime import datetime
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu, fill_bar_ins
bp = flask.Blueprint('messages', __name__)

@bp.route('/messages/recipients', methods=['GET'])
@require_roles()
def find_recipients():
    keyword = request.args.get('q', '').strip()
    if len(keyword) > 100:
        return jsonify(status='error', message='Use at most 100 characters.'), 400
    if not keyword:
        return jsonify(users=[], has_more=False)
    db = get_db()
    if keyword.isdecimal():
        if len(keyword) > 18:
            return jsonify(users=[], has_more=False)
        users = db.execute('SELECT id, firstname, lastname FROM users WHERE id=?', (int(keyword),)).fetchall()
    else:
        words = keyword.split()
        clauses = ["(firstname || ' ' || lastname) LIKE ? ESCAPE '\\'" for _ in words]
        values = ['%' + word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for word in words]
        query = f"SELECT id, firstname, lastname FROM users WHERE {' AND '.join(clauses)} ORDER BY firstname, lastname, id LIMIT 21"
        users = db.execute(query, values).fetchall()
    return jsonify(users=[dict(id=user[0], name=f'{user[1]} {user[2]}') for user in users[:20]], has_more=len(users) > 20)

@bp.route('/messages', methods=['GET'])
@require_roles(1, 2)
def get_messages():
    items = search_rows('messages', "SELECT m.id, (u.firstname || ' ' || u.lastname), m.content, m.send_time, u.id FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.receiver_id=?", (session['userid'],), order_by='julianday(REPLACE(m.send_time, ",", "")) DESC, m.id DESC')
    if session['role_id'] == 1:
        info = fill_bar_stu(session['userid'])
        return render('non_admin_table.html', items=items, type='messages', firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])
    info = fill_bar_ins(session['userid'])
    return render('ins_table.html', items=items, type='messages', firstname=session['name'], courses=info[0], assignments=info[1], edit=True)

@bp.route('/messages/create', methods=['GET', 'POST'])
@require_roles()
def create_message():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        return render('msg_window.html', title='Write message')
    else:
        try:
            receiver_id = flask.request.form['receiver_id']
            if not get_db().execute('SELECT id FROM users WHERE id=?', (receiver_id,)).fetchone():
                return jsonify(status='error', message='Recipient not found. Check the personal ID.'), 400
            content = flask.request.form['con']
            send_time = datetime.now().strftime('%Y-%m-%d, %H:%M:%S')
            query = 'INSERT INTO messages (sender_id, receiver_id, content, send_time) VALUES (?, ?, ?, ?)'
            value = (session['userid'], receiver_id, content, send_time)
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Message successfully created.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to send message.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/messages/delete', methods=['POST'])
@require_roles()
def delete_message():
    cursor = get_db().cursor()
    try:
        msg_id = flask.request.args['id']
        query = 'DELETE FROM messages WHERE id=?'
        value = (msg_id,)
        cursor.execute(query, value)
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
    return flask.redirect('/messages')
