from ..search import search_rows, search_metadata
import flask
from flask import session, request, jsonify
from ..db import get_db
from ..security import require_roles, hash_password
from ..views import render
bp = flask.Blueprint('accounts', __name__)

@bp.route('/account', methods=['GET'])
@require_roles(0)
def account():
    roles = {0: 'Admin', 1: 'Student', 2: 'Instructor'}
    rows = search_rows('account', 'SELECT id, firstname, lastname, role_id FROM users WHERE 1', order_by='id')
    items = [(identifier, first, last, roles[role]) for identifier, first, last, role in rows]
    return render('console.html', items=items, firstname=session['name'], type='account')

@bp.route('/account/create', methods=['GET', 'POST'])
@require_roles(0)
def create_account():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        return render('account_window.html', title='Create new account', edit=False)
    else:
        try:
            f_name = flask.request.form['c_firstname']
            l_name = flask.request.form['c_lastname']
            psw = hash_password(flask.request.form['c_psw'])
            role_id = int(flask.request.form['c_roles'])
            query = 'INSERT INTO users (firstname, lastname, password, role_id) VALUES (?, ?, ?, ?)'
            value = (f_name, l_name, psw, role_id)
            cursor.execute(query, value)
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new account successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})

@bp.route('/account/delete', methods=['POST'])
@require_roles(0)
def delete_account():
    cursor = get_db().cursor()
    try:
        account_id = flask.request.args['id']
        if int(account_id) == session['userid']:
            return flask.redirect('/account')
        query = 'DELETE FROM users WHERE id=?'
        value = (account_id,)
        cursor.execute(query, value)
        return flask.redirect('/account')
    except Exception:
        flask.current_app.logger.exception('Operation failed')
        get_db().rollback()
        return flask.redirect('/account')

@bp.route('/account/edit', methods=['GET', 'POST'])
@require_roles(0)
def edit_account():
    cursor = get_db().cursor()
    if flask.request.method == 'GET':
        account_id = flask.request.args['id']
        query = 'SELECT firstname, lastname, role_id FROM users WHERE id=?'
        value = (account_id,)
        cursor.execute(query, value)
        result = cursor.fetchone()
        if result is None:
            return flask.redirect('/account')
        return render('account_window.html', title='Edit account', edit=True, id=account_id, f_name=result[0], l_name=result[1], role_id=result[2])
    else:
        f_name = flask.request.form['c_firstname']
        l_name = flask.request.form['c_lastname']
        psw = flask.request.form['c_psw']
        psw_confirm = flask.request.form['e_psw']
        if psw_confirm != psw:
            return jsonify({'status': 'error', 'message': f'Two inputs are inconsistent, please try again.'})
        else:
            psw = hash_password(psw) if psw else ''
        role_id = int(flask.request.form['c_roles'])
        account_id = flask.request.form['e_id']
        if not psw:
            query = 'UPDATE users SET firstname=?, lastname=?, role_id=? WHERE id=?'
            value = (f_name, l_name, role_id, account_id)
        else:
            query = 'UPDATE users SET firstname=?, lastname=?, password=?, role_id=? WHERE id=?'
            value = (f_name, l_name, psw, role_id, account_id)
        try:
            cursor.execute(query, value)
            updated = cursor.rowcount
            cursor.execute('DELETE FROM auth_sessions WHERE user_id=?', (account_id,))
            if updated > 0:
                return jsonify({'status': 'success', 'message': 'Success.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this user.'})
        except Exception:
            flask.current_app.logger.exception('Operation failed')
            get_db().rollback()
            return jsonify({'status': 'error', 'message': 'Unable to complete the operation. Check the input and try again.'})
