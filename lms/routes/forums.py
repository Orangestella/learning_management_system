from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from datetime import datetime
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu
bp = flask.Blueprint('forums', __name__)

@bp.route('/forum', methods=['GET'])
@require_roles(0)
def forum():
    items = search_rows('forum', 'SELECT f.id, f.name FROM forums f WHERE 1', order_by='f.id')
    return render('console.html', items=items, firstname=session['name'], type='forum')

@bp.route('/forum/membership/<int:forum_id>', methods=['GET'])
@require_roles(0)
def forum_spec(forum_id):
    if not get_db().execute('SELECT id FROM forums WHERE id=?', (forum_id,)).fetchone():
        flask.abort(404)
    items = search_rows('membership', 'SELECT m.id, u.firstname, u.lastname, u.id FROM user_forum_memberships m JOIN users u ON u.id=m.user_id WHERE m.forum_id=?', (forum_id,), order_by='m.id')
    return render('console.html', items=items, firstname=session['name'], type='membership')

@bp.route('/forum/delete', methods=['POST'])
@require_roles(0)
def delete_forum():
    cursor = get_db().cursor()
    try:
        lec_id = flask.request.args['id']
        query = 'DELETE FROM forums WHERE id=?'
        value = (lec_id,)
        cursor.execute(query, value)
        query = 'DELETE FROM user_forum_memberships WHERE forum_id=?'
        cursor.execute(query, value)
        return flask.redirect('/forum')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/forum')

@bp.route('/forum/create', methods=['GET', 'POST'])
@require_roles(0)
def create_forum():
    cursor = get_db().cursor()
    if request.method == 'GET':
        return render('forum_window.html', title='Create new forum', edit=False)
    else:
        try:
            frm_name = flask.request.form['frm_name']
            query = 'INSERT INTO forums (name) VALUES (?)'
            value = (frm_name,)
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new forum successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/forum/edit', methods=['GET', 'POST'])
@require_roles(0)
def edit_forum():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        f_id = flask.request.args['id']
        query = 'SELECT id, name FROM forums WHERE id=?'
        value = (f_id,)
        cursor.execute(query, value)
        result1 = cursor.fetchone()
        if result1 is None:
            flask.abort(404)
        return render('forum_window.html', title='Edit forum', edit=True, id=f_id, frm_name=result1[1])
    else:
        f_id = flask.request.form['f_id']
        frm_name = flask.request.form['frm_name']
        query = 'UPDATE forums SET name=? WHERE id=?'
        value = (frm_name, f_id)
        try:
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Edit forum successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this forum.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/forum/stu', methods=['GET'])
@require_roles(1)
def forum_list():
    info = fill_bar_stu(session['userid'])
    items = search_rows('forum', 'SELECT f.id, f.name FROM forums f WHERE NOT EXISTS (SELECT 1 FROM user_forum_memberships m WHERE m.forum_id=f.id AND m.user_id=?)', (session['userid'],), order_by='f.id')
    return render('non_admin_table.html', items=items, type='join forum', firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3])

@bp.route('/forum/stu/join', methods=['POST'])
@require_roles(1)
def forum_join():
    cursor = get_db().cursor()
    frm_id = request.args['id']
    try:
        query = 'INSERT INTO user_forum_memberships (user_id, forum_id) VALUES (?, ?)'
        value = (session['userid'], frm_id)
        cursor.execute(query, value)
        return flask.redirect('/forum/stu')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/forum/stu')

@bp.route('/forum/view/<int:frm_id>', methods=['GET'])
@require_roles(1)
def forum_view(frm_id):
    info = fill_bar_stu(session['userid'])
    forum = get_db().execute('SELECT id, name FROM forums WHERE id=?', (frm_id,)).fetchone()
    posts = search_rows('posts', "SELECT (u.firstname || ' ' || u.lastname), f.name, p.content, p.date, p.id, u.id, (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) FROM forum_posts p JOIN forums f ON f.id=p.forum_id JOIN users u ON u.id=p.poster_id WHERE p.forum_id=?", (frm_id,), order_by='p.id DESC')
    return render('stu_forum.html', posts=posts, firstname=session['name'], courses=info[0], grades=info[1], assignments=info[2], forums=info[3], frm=forum, search=search_metadata('posts'))

@bp.route('/forum/stu/post', methods=['GET', 'POST'])
@require_roles(1)
def forum_post():
    cursor = get_db().cursor()
    if request.method == 'GET':
        frm_id = request.args['id']
        return render('post_window.html', title='Your Post', frm_id=frm_id)
    else:
        frm_id = request.form['frm_id']
        content = request.form['content']
        try:
            query = 'INSERT INTO forum_posts (poster_id, forum_id, content, date) VALUES (?, ?, ?, ?)'
            value = (int(session['userid']), int(frm_id), content, datetime.now().strftime('%Y-%m-%d'))
            cursor.execute(query, value)
            return flask.jsonify({'status': 'success', 'message': 'You have successfully posted'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return flask.jsonify({'status': 'error', 'message': 'Unable to complete the operation.'})

@bp.route('/forum/poster/detail', methods=['GET', 'POST'])
@require_roles(1)
def forum_poster_detail():
    cursor = get_db().cursor()
    if request.method == 'GET':
        info = fill_bar_stu(session['userid'])
        pst_id = request.args['id']
        query = "SELECT (COALESCE(u.firstname, '') || ' ' || COALESCE(u.lastname, '')), p.content, p.date, p.id, p.forum_id, u.id FROM forum_posts AS p INNER JOIN users AS u ON u.id = p.poster_id WHERE p.id=? "
        value = (int(pst_id),)
        cursor.execute(query, value)
        con = cursor.fetchone()
        query = "SELECT (COALESCE(u.firstname, '') || ' ' || COALESCE(u.lastname, '')), c.content, c.date, u.id FROM users AS u INNER JOIN comments AS c ON c.sender_id=u.id WHERE c.post_id=? ORDER BY c.id"
        cursor.execute(query, (pst_id,))
        comments = cursor.fetchall()
        return render('post_detail.html', firstname=session['name'], post=con, courses=info[0], grades=info[1], assignments=info[2], forums=info[3], cmts=comments)
    else:
        cmt = request.form['cmt']
        pst_id = request.form['pst_id']
        try:
            query = 'INSERT INTO comments (sender_id, content, date,post_id) VALUES (?, ?, ?, ?)'
            value = (int(session['userid']), cmt, datetime.now().strftime('%Y-%m-%d'), pst_id)
            cursor.execute(query, value)
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
        return flask.redirect(f'/forum/poster/detail?id={pst_id}')

@bp.route('/forum/stu/leave', methods=['POST'])
@require_roles(1)
def forum_leave():
    cursor = get_db().cursor()
    frm_id = request.args.get('id')
    query = 'DELETE FROM user_forum_memberships WHERE forum_id = ? AND user_id = ?'
    value = (frm_id, session['userid'])
    try:
        cursor.execute(query, value)
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})
    return flask.redirect('/')
