import os
from datetime import datetime

import flask
from flask import Flask, session, request, make_response, jsonify
from werkzeug.utils import secure_filename

import utils
import mysql.connector
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
cnx = mysql.connector.connect(user=config["DATABASE"]["User"],
                              password=config["DATABASE"]["Password"], host=config["DATABASE"]["Host"],
                              database=config["DATABASE"]["Database"])
cursor = cnx.cursor()

app = Flask(__name__)
app.secret_key = config["SESSION"]["Secret_key"]
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB
app.config['ALLOWED_EXTENSIONS'] = {'doc', 'pdf', 'docx'}


def judge_str(filed):
    return isinstance(filed, str)


app.jinja_env.globals.update(judge_str=judge_str)


def fill_bar(userid):
    print("?")
    query = ("SELECT c.name, c.session, CONCAT_WS(' ',u.firstname, u.lastname), c.description, c.id "
             "FROM learn_manage.courses AS c INNER JOIN learn_manage.enrollments AS e ON e.course_id=c.id "
             "INNER JOIN learn_manage.users AS u ON u.id=c.leader_id WHERE e.student_id=%s AND e.status=%s")
    value = (userid, "received")
    print("?")
    cursor.execute(query, value)
    results_crs = cursor.fetchall()
    query = ("SELECT c.name, a.name FROM learn_manage.submissions AS s INNER JOIN learn_manage.assignments AS "
             "a ON s.assignment_id=a.id INNER JOIN learn_manage.courses AS c ON a.course_id = c.id WHERE s.student_id=%s")
    value = (userid,)
    cursor.execute(query, value)
    results_grd = cursor.fetchall()
    query = ("SELECT a.name, a.deadline FROM learn_manage.assignments AS a INNER JOIN learn_manage.enrollments "
             "AS e ON e.course_id=a.course_id WHERE e.student_id=%s AND e.status=%s")
    value = (userid, "received")
    cursor.execute(query, value)
    results_asn = cursor.fetchall()
    query = ("SELECT f.name, f.id FROM learn_manage.forums AS f INNER JOIN learn_manage.user_forum_memberships AS m "
             "ON f.id = m.forum_id WHERE m.user_id=%s")
    value = (userid,)
    cursor.execute(query, value)
    results_frm = cursor.fetchall()
    return results_crs, results_grd, results_asn, results_frm


@app.route('/')
def index():  # put application's code here
    if not flask.request.cookies.get("userid") and 'userid' not in session:
        print(flask.request.cookies.get("userid"))
        return flask.redirect("/login")
    else:
        if "userid" not in session and "role_id" not in session:
            session["userid"] = int(flask.request.cookies.get("userid"))
            print(int(flask.request.cookies.get("userid")))
        query1 = "SELECT role_id, firstname FROM users WHERE id=%s"
        value = (session["userid"],)
        cursor.execute(query1, value)
        result1 = cursor.fetchone()
        fname = result1[1]
        session["role_id"] = result1[0]
        session["name"] = fname
        print(result1)
        if result1[0] == 0:  # Admin
            query1 = "SELECT COUNT(*) FROM users"
            cursor.execute(query1)
            result1 = cursor.fetchone()
            query2 = "SELECT COUNT(*) FROM courses"
            cursor.execute(query2)
            result2 = cursor.fetchone()
            total_users = result1[0]
            speech_rate = 0.4
            assign_rate = 0.7
            total_courses = result2[0]
            return flask.render_template("index_admin.html", firstname=fname, total_courses=total_courses,
                                         speech_rate=speech_rate, total_users=total_users, assign_rate=assign_rate)
        elif result1[0] == 1:  # Student
            results = fill_bar(session['userid'])
            return flask.render_template("index_stu.html", firstname=fname, courses=results[0], grades=results[1],
                                         assignments=results[2], forums=results[3])
        elif result1[0] == 2:  # Instructor
            return "You are instructor."
        else:
            return "Error"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'GET':
        return flask.render_template("login.html")
    else:
        fname = flask.request.form["firstname"]
        lname = flask.request.form["lastname"]
        id = int(flask.request.form["id"])
        psw = utils.md5(flask.request.form["psw"]).upper()
        query = "SELECT * FROM users WHERE id=%s AND firstname=%s AND lastname=%s AND password=%s"
        values = (id, fname, lname, psw)
        cursor.execute(query, values)
        result = cursor.fetchone()
        if result is None:
            return flask.jsonify({'status': 'error', 'message': 'Incorrect information, please try again after check.'})
        else:
            session['userid'] = id
            session['name'] = fname
            session['role_id'] = result[4]
            print(session["role_id"])
            resp = flask.make_response(flask.jsonify({'status': 'success', 'message': 'Welcome!'}))
            print(values)
            resp.set_cookie('userid', str(id), max_age=36000)
            print("cookie set")
            return resp


@app.route('/results', methods=["GET"])
def search_results():
    keyword = request.args["keyword"]
    return flask.render_template("search_results.html", keyword=keyword)


@app.route('/logout')
def logout():
    resp = make_response(flask.redirect(flask.url_for('login')))
    resp.delete_cookie('userid')
    session.clear()
    return resp


@app.route('/account', methods=['GET'])
def account():
    role_dict = {0: 'Admin', 1: 'Student', 2: 'Instructor'}
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = "SELECT id, firstname, lastname, role_id FROM learn_manage.users"
        value = ()
    elif search_key.isnumeric():
        search_key = int(search_key)
        query = "SELECT id, firstname, lastname, role_id FROM learn_manage.users WHERE id=%s"
        value = (search_key,)
    elif search_key.lower() in ("admin", "student", "instructor"):
        query = "SELECT id, firstname, lastname, role_id FROM learn_manage.users WHERE role_id=%s"
        if search_key.lower() == "admin":
            role_id = 0
        elif search_key.lower() == "student":
            role_id = 1
        else:
            role_id = 2
        value = (role_id,)
    else:
        query = ("SELECT id, firstname, lastname, role_id FROM learn_manage.users WHERE firstname LIKE %s or lastname "
                 "LIKE %s")
        value = (f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    print(results)
    results = [(id, firstname, lastname, role_dict[role_id]) for id, firstname, lastname, role_id in results]
    print(results)
    return flask.render_template("console.html", items=results, firstname=session['name'], type="account")


@app.route('/account/create', methods=['GET', 'POST'])
def create_account():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'Unauthenticated.'})
    if flask.request.method == 'GET':
        return flask.render_template("account_window.html", title="Create new account", edit=False)
    else:
        try:
            f_name = flask.request.form["c_firstname"]
            l_name = flask.request.form["c_lastname"]
            psw = utils.md5(flask.request.form["c_psw"]).upper()
            role_id = int(flask.request.form["c_roles"])
            query = "INSERT INTO learn_manage.users (firstname, lastname, password, role_id) VALUES (%s, %s, %s, %s)"
            value = (f_name, l_name, psw, role_id)
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new account successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/account/delete', methods=['GET'])
def delete_account():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    try:
        account_id = flask.request.args['id']
        if account_id == session["userid"]:
            return flask.redirect("/account")
        query = "DELETE FROM learn_manage.users WHERE id=%s"
        value = (account_id,)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/account")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/account")


@app.route('/account/edit', methods=['GET', 'POST'])
def edit_account():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        account_id = flask.request.args['id']
        query = "SELECT firstname, lastname FROM learn_manage.users WHERE id=%s"
        value = (account_id,)
        cursor.execute(query, value)
        result = cursor.fetchone()
        if result is None:
            return flask.redirect("/account")
        return flask.render_template("account_window.html", title="Edit account", edit=True, id=account_id,
                                     f_name=result[0], l_name=result[1])
    else:
        f_name = flask.request.form["c_firstname"]
        l_name = flask.request.form["c_lastname"]
        psw = flask.request.form["c_psw"]
        psw_confirm = flask.request.form["e_psw"]
        if psw_confirm != psw:
            return jsonify({'status': 'error', 'message': f'Two inputs are inconsistent, please try again.'})
        else:
            psw = utils.md5(psw).upper()
        role_id = int(flask.request.form["c_roles"])
        account_id = flask.request.form["e_id"]
        if psw == '' or None:
            query = "UPDATE learn_manage.users SET firstname=%s, lastname=%s, role_id=%s WHERE id=%s"
            value = (f_name, l_name, psw, role_id, account_id)
        else:
            query = "UPDATE learn_manage.users SET firstname=%s, lastname=%s, password=%s, role_id=%s WHERE id=%s"
            value = (f_name, l_name, psw, role_id, account_id)
        try:
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Success.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this user.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/course', methods=['GET'])
def course():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS Instructor, users.id, session FROM learn_manage.courses INNER "
            "JOIN learn_manage.users ON users.id = courses.leader_id")
        value = ()
    elif search_key.isnumeric():
        search_key = int(search_key)
        query = (
            "SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS Instructor, users.id, session FROM learn_manage.courses INNER "
            "JOIN learn_manage.users ON users.id = courses.leader_id WHERE courses.id=%s OR "
            "courses.leader_id=%s")
        value = (search_key, search_key)
    elif search_key[:4] in ("crs\40", "ins\40"):
        search_cmd = search_key[:3]
        search_target = search_key[4:]
        if search_target.isnumeric():
            search_target = int(search_target)
            if search_cmd == "crs":
                query = ("SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS "
                         "Instructor, users.id, session FROM learn_manage.courses INNER JOIN learn_manage.users ON "
                         "users.id = courses.leader_id WHERE courses.id=%s")
            else:
                query = ("SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS "
                         "Instructor, users.id, session FROM learn_manage.courses INNER JOIN learn_manage.users ON "
                         "users.id = courses.leader_id WHERE courses.leader_id=%s")
            value = (search_target,)
        else:
            if search_cmd == "crs":
                query = ("SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS "
                         "Instructor, users.id, session FROM learn_manage.courses INNER JOIN learn_manage.users ON "
                         "users.id = courses.leader_id WHERE courses.name lIKE %s")
            else:
                query = ("SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS "
                         "Instructor, users.id, session FROM learn_manage.courses INNER JOIN learn_manage.users ON "
                         "users.id = courses.leader_id WHERE CONCAT_WS(' ', users.firstname, users.lastname) LIKE "
                         "%s")
            value = (f'%{search_target}%',)
    else:
        query = ("SELECT courses.id, courses.name, CONCAT_WS(' ', users.firstname, users.lastname) AS Instructor, "
                 "users.id, session FROM learn_manage.courses INNER JOIN learn_manage.users ON users.id = "
                 "courses.leader_id WHERE courses.name lIKE %s OR CONCAT_WS(' ', users.firstname, users.lastname) "
                 "LIKE %s")
        value = (f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("console.html", items=results, firstname=session['name'], type="course")


@app.route('/course/create', methods=['GET', 'POST'])
def create_course():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'Unauthenticated.'})
    if flask.request.method == 'GET':
        return flask.render_template("course_window.html", title="Create new course", edit=False)
    else:
        try:
            crs_name = flask.request.form['course_name']
            crs_session = flask.request.form['session']
            ins_ids = flask.request.form['ins_ids']
            description = flask.request.form['description']

            ins_ids_list = ins_ids.split(' ')
            print(ins_ids_list)
            for ins_id in ins_ids_list:
                if not ins_id.isnumeric():
                    return jsonify({'status': 'error', 'message': 'Invalid Format.'})
                else:
                    query = "SELECT id FROM learn_manage.users WHERE id=%s AND role_id=%s"
                    value = (int(ins_id), 2)
                    cursor.execute(query, value)
                    result2 = cursor.fetchone()
                    if result2 is None:
                        return flask.jsonify({'status': 'error', 'message': 'Invalid Instructor ID.'})

            query = "INSERT INTO learn_manage.courses (name, description, leader_id, session) VALUES (%s, %s, %s, %s)"
            value = (crs_name, description, ins_ids_list[0], crs_session)
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                last_crs_id = cursor.lastrowid
                try:
                    for ins_id in ins_ids_list:
                        ins_id = int(ins_id)
                        query = "INSERT INTO learn_manage.ins_crs_assignments (ins_id, crs_id) VALUES (%s, %s)"
                        value = (ins_id, last_crs_id)
                        cursor.execute(query, value)
                        cnx.commit()
                    return jsonify({'status': 'success', 'message': 'Create new account successfully.'})
                except Exception as e:
                    cnx.rollback()
                    return jsonify(
                        {'status': 'error', 'message': f'{e} occurred at the second step, please try again.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred at the first step, please try again.'})


@app.route('/course/delete', methods=['GET'])
def delete_course():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    try:
        crs_id = flask.request.args['id']
        query = "DELETE FROM learn_manage.courses WHERE id=%s"
        value = (crs_id,)
        cursor.execute(query, value)
        cnx.commit()
        query = "DELETE FROM learn_manage.ins_crs_assignments WHERE crs_id=%s"
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/course")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/course")


@app.route('/course/edit', methods=['GET', 'POST'])
def edit_course():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        crs_id = flask.request.args['id']
        query = "SELECT name, description, session FROM learn_manage.courses WHERE id=%s"
        value = (crs_id,)
        cursor.execute(query, value)
        result1 = cursor.fetchone()
        query2 = "SELECT ins_id FROM learn_manage.ins_crs_assignments WHERE crs_id=%s"
        value2 = (crs_id,)
        cursor.execute(query2, value2)
        result2 = cursor.fetchall()
        ids = ''.join([str(t[0]) + " " for t in result2])
        ids = ids[:-1]
        if result1 is None:
            return flask.redirect("/course")
        return flask.render_template("course_window.html", title="Edit course", edit=True, id=crs_id,
                                     crs_name=result1[0], ids=ids, desc=result1[1], crs_session=result1[2])
    else:
        crs_name = flask.request.form["course_name"]
        crs_session = flask.request.form["session"]
        ins_ids = flask.request.form["ins_ids"]
        description = flask.request.form["description"]
        crs_id = flask.request.form["c_id"]
        print("Going on.")

        ins_ids_list = ins_ids.split(' ')
        for ins_id in ins_ids_list:
            if not ins_id.isnumeric():
                print("Nearly fail.")
                return jsonify({'status': 'error', 'message': 'Invalid Instructor ID.'})
        query = "UPDATE learn_manage.courses SET name=%s, session=%s, leader_id=%s, description=%s WHERE id=%s"
        value = (crs_name, crs_session, int(ins_ids_list[0]), description, crs_id)
        try:
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                print("Maybe success")
                try:
                    query = "DELETE FROM learn_manage.ins_crs_assignments WHERE crs_id=%s"
                    value = (crs_id,)
                    cursor.execute(query, value)
                    cnx.commit()
                    for ins_id in ins_ids_list:
                        ins_id = int(ins_id)
                        query = "INSERT INTO learn_manage.ins_crs_assignments (ins_id, crs_id) VALUES (%s, %s)"
                        value = (ins_id, crs_id)
                        cursor.execute(query, value)
                        cnx.commit()
                    print("Nearly success.")
                    return jsonify({'status': 'success', 'message': 'Success.'})
                except Exception as e:
                    cnx.rollback()
                    return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this course.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/course/enroll', methods=['GET', 'POST'])
def enroll_course():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})

    if flask.request.method == 'GET':
        crs_id = flask.request.args['id']
        query = "SELECT student_id, course_id, id FROM learn_manage.enrollments WHERE course_id=%s"
        value = (crs_id,)
        cursor.execute(query, value)
        result = cursor.fetchall()
        std_ids = ''
        print(result)
        if result is not None:
            for erl in result:
                std_ids = std_ids + str(erl[0]) + ' '
            std_ids = std_ids[:-1]
        return flask.render_template("enrollment.html", title="Enroll course", ids=std_ids, crs_id=crs_id)
    else:
        crs_id = flask.request.form['crs_id']
        std_ids = flask.request.form['std_ids']
        query = "SELECT student_id, course_id, id FROM learn_manage.enrollments WHERE course_id=%s"
        value = (crs_id,)
        cursor.execute(query, value)
        result = cursor.fetchall()
        std_ids_list = std_ids.split(' ')
        for std_id in std_ids_list:
            if not std_id.isnumeric():
                return flask.jsonify({'status': 'error', 'message': 'Invalid format.'})
            else:
                query = "SELECT id FROM learn_manage.users WHERE id=%s AND role_id=%s"
                value = (int(std_id), 1)
                cursor.execute(query, value)
                result2 = cursor.fetchone()
                if result2 is None:
                    return flask.jsonify({'status': 'error', 'message': 'Invalid Student ID.'})
        try:
            print("Are you ok?")
            if result:
                print("wtf", result)
                ori_ids = [t[0] for t in result]
                for ori_erl in result:
                    if ori_erl[0] not in std_ids_list:
                        query = "DELETE FROM learn_manage.enrollments WHERE id=%s"
                        value = (int(ori_erl[2]),)
                        cursor.execute(query, value)
                        cnx.commit()
                    for std_id in std_ids_list:
                        if std_id not in ori_ids:
                            date = datetime.now()
                            query = (
                                "INSERT INTO learn_manage.enrollments (student_id, course_id, enrollment_date, status) "
                                "VALUES (%s, %s, %s, %s)")
                            value = (int(std_id), crs_id, date.strftime("%Y-%m-%d"), "received")
                            cursor.execute(query, value)
                            cnx.commit()
                return flask.jsonify({'status': 'success', 'message': 'Success.'})
            else:
                try:
                    for std_id in std_ids_list:
                        print("?????")
                        date = datetime.now()
                        query = (
                            "INSERT INTO learn_manage.enrollments (student_id, course_id, enrollment_date, status) VALUES "
                            "(%s, %s, %s, %s)")
                        value = (int(std_id), crs_id, date.strftime("%Y-%m-%d"), "received")
                        cursor.execute(query, value)
                        cnx.commit()
                    return flask.jsonify({'status': 'success', 'message': 'Success.'})
                except Exception as e:
                    cnx.rollback()
                    return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route("/assignment", methods=['GET'])
def assignment():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT a.id, a.name, CONCAT_WS(' ', c.name, c.session), a.deadline FROM learn_manage.assignments AS a INNER JOIN "
            "learn_manage.courses AS c ON c.id=a.course_id")
        value = ()
    elif search_key.isnumeric():
        query = (
            "SELECT a.id, a.name, CONCAT_WS(' ', c.name, c.session), a.deadline FROM learn_manage.assignments AS a INNER JOIN "
            "learn_manage.courses AS c ON c.id=a.course_id WHERE a.id=%s")
        value = (int(search_key),)
    elif search_key[:4] in ("crs\40", "asn\40"):
        search_cmd = search_key[:3]
        search_target = search_key[4:]
        if search_cmd == "crs":
            query = (
                "SELECT a.id, a.name, CONCAT_WS(' ', c.name, c.session), a.deadline FROM learn_manage.assignments AS a INNER JOIN "
                "learn_manage.courses AS c ON c.id=a.course_id WHERE c.name LIKE %s")
        else:
            query = (
                "SELECT a.id, a.name, CONCAT_WS(' ', c.name, c.session), a.deadline FROM learn_manage.assignments AS a INNER JOIN "
                "learn_manage.courses AS c ON c.id=a.course_id WHERE a.name LIKE %s")
        value = (f'%{search_target}%',)
    else:
        query = (
            "SELECT a.id, a.name, CONCAT_WS(' ', c.name, c.session), a.deadline FROM learn_manage.assignments AS a INNER JOIN "
            "learn_manage.courses AS c ON c.id=a.course_id WHERE a.name LIKE %s OR c.name LIKE %s")
        value = (f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("console.html", items=results, firstname=session['name'], type="assignment")


@app.route("/lecture", methods=['GET'])
def lecture():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT l.id, l.name, CONCAT_WS(' ', c.name, c.session), l.resource_url FROM learn_manage.lectures AS l "
            "INNER JOIN learn_manage.courses AS c ON c.id=l.course_id")
        value = ()
    elif search_key.isnumeric():
        query = (
            "SELECT l.id, l.name, CONCAT_WS(' ', c.name, c.session), l.resource_url FROM learn_manage.lectures AS l "
            "INNER JOIN learn_manage.courses AS c ON c.id=l.course_id WHERE l.id=%s")
        value = (int(search_key),)
    elif search_key[:4] in ("crs\40", "lec\40"):
        search_cmd = search_key[:3]
        search_target = search_key[4:]
        if search_cmd == "crs":
            query = (
                "SELECT l.id, l.name, CONCAT_WS(' ', c.name, c.session), l.resource_url FROM learn_manage.lectures AS l "
                "INNER JOIN learn_manage.courses AS c ON c.id=l.course_id WHERE c.name LIKE %s")
            value = (f'%{search_target}%',)
        else:
            query = (
                "SELECT l.id, l.name, CONCAT_WS(' ', c.name, c.session), l.resource_url FROM learn_manage.lectures AS l "
                "INNER JOIN learn_manage.courses AS c ON c.id=l.course_id WHERE l.name LIKE %s")
            value = (f'%{search_target}%',)
    else:
        query = (
            "SELECT l.id, l.name, CONCAT_WS(' ', c.name, c.session), l.resource_url FROM learn_manage.lectures AS l "
            "INNER JOIN learn_manage.courses AS c ON c.id=l.course_id WHERE l.name LIKE %s OR c.name LIKE %s")
        value = (f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("console.html", items=results, firstname=session['name'], type="lecture")


@app.route("/forum", methods=['GET'])
def forum():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = "SELECT * FROM learn_manage.forums"
        value = ()
    elif search_key.isnumeric():
        query = "SELECT * FROM learn_manage.forums WHERE id=%s"
        value = (int(search_key),)
    else:
        query = "SELECT * FROM learn_manage.forums WHERE name LIKE %s"
        value = (f'%{search_key}%',)
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("console.html", items=results, firstname=session['name'], type="forum")


@app.route("/forum/membership/<forum_id>", methods=['GET'])
def forum_spec(forum_id):
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    query = "SELECT name FROM learn_manage.forums WHERE id=%s"
    value = (int(forum_id),)
    cursor.execute(query, value)
    result = cursor.fetchone()
    print(result)
    if result is None or result == []:
        return flask.abort(404)
    if search_key is None or search_key == '':
        query = ("SELECT m.id, u.firstname, u.lastname, u.id FROM learn_manage.user_forum_memberships AS m "
                 "INNER JOIN learn_manage.users AS u ON u.id=m.user_id WHERE m.forum_id=%s")
        value = (int(forum_id),)
    elif search_key.isnumeric():
        query = ("SELECT m.id, u.firstname, u.lastname, u.id FROM learn_manage.user_forum_memberships AS m "
                 "INNER JOIN learn_manage.users AS u ON u.id=m.user_id WHERE m.forum_id=%s AND u.id=%s")
        value = (int(forum_id), int(search_key), int(search_key))
    else:
        query = ("SELECT m.id, u.firstname, u.lastname, u.id FROM learn_manage.user_forum_memberships AS m "
                 "INNER JOIN learn_manage.users AS u ON u.id=m.user_id "
                 "WHERE m.forum_id=%s AND (u.firstname LIKE %s OR u.lastname LIKE %s)")
        value = (int(forum_id), search_key, search_key)
    cursor.execute(query, value)
    results = cursor.fetchall()
    print(results)
    return flask.render_template("console.html", items=results, firstname=session['name'], type="membership")


@app.route("/assignment/create", methods=['GET', 'POST'])
def create_assignment():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        return flask.render_template("assignment.html", title="Create new assignment", edit=False)
    else:
        try:
            asn_name = flask.request.form['asn_name']
            crs_id = flask.request.form['crs_id']
            ddl = flask.request.form['ddl']
            desc_asn = flask.request.form['desc_asn']
            query = ("INSERT INTO learn_manage.assignments (name, course_id, deadline, description) VALUES (%s, %s, "
                     "%s, %s)")
            value = (asn_name, crs_id, ddl, desc_asn)
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new assignment successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred at the first step, please try again.'})


@app.route("/assignment/delete", methods=['GET', 'POST'])
def delete_assignment():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    try:
        asn_id = flask.request.args['id']
        query = "DELETE FROM learn_manage.assignments WHERE id=%s"
        value = (asn_id,)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/assignment")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/assignment")


@app.route("/assignment/edit", methods=['GET', 'POST'])
def edit_assignment():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        query = "SELECT * FROM learn_manage.assignments WHERE id=%s"
        value = (flask.request.args['id'],)
        cursor.execute(query, value)
        result = cursor.fetchone()
        return flask.render_template("assignment.html", title="Edit assignment", edit=True, a_id=result[0],
                                     asn_name=result[1], crs_id=result[2], ddl=result[3], desc_asn=result[4])
    else:
        a_id = flask.request.form['a_id']
        asn_name = flask.request.form['asn_name']
        crs_id = flask.request.form['crs_id']
        ddl = flask.request.form['ddl']
        desc_asn = flask.request.form['desc_asn']
        try:
            query = "UPDATE learn_manage.assignments SET name=%s, course_id=%s, deadline=%s, description=%s WHERE id=%s"
            value = (asn_name, crs_id, ddl, desc_asn, a_id)
            cursor.execute(query, value)
            cnx.commit()
            return flask.jsonify({'status': 'success', 'message': 'Edit assignment successfully.'})
        except Exception as e:
            cnx.rollback()
            return flask.jsonify({'status': 'error', 'message': f'{e} occurred at the first step, please try again.'})


@app.route("/lecture/delete", methods=['GET', 'POST'])
def delete_lecture():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    try:
        lec_id = flask.request.args['id']
        query = "DELETE FROM learn_manage.lectures WHERE id=%s"
        value = (lec_id,)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/lecture")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/lecture")


@app.route("/forum/delete", methods=['GET', 'POST'])
def delete_forum():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    try:
        lec_id = flask.request.args['id']
        query = "DELETE FROM learn_manage.forums WHERE id=%s"
        value = (lec_id,)
        cursor.execute(query, value)
        cnx.commit()
        query = "DELETE FROM learn_manage.user_forum_memberships WHERE forum_id=%s"
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/forum")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/forum")


@app.route("/lecture/create", methods=['GET', 'POST'])
def create_lecture():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if request.method == 'GET':
        return flask.render_template("lecture_window.html", title="Create new lecture", edit=False)
    else:
        try:
            lec_title = flask.request.form['lec_title']
            crs_id = flask.request.form['crs_id']
            print(f"There are files in the request: {lec_title}, {crs_id}")
            for k, v in request.files.items():
                print(k, v)
            print("That's all")
            rse = flask.request.files['rse']
            print("Hello", rse)
            if rse.filename != '':
                filename = secure_filename(rse.filename)
            else:
                filename = "new_file"
            desc_lec = flask.request.form['desc_lec']
            rse_url = os.path.join('static\\files', filename)
            rse.save(rse_url)
            date = datetime.now()

            query = ("INSERT INTO learn_manage.lectures (course_id, name, resource_url, description, upload_date) "
                     "VALUES (%s, %s, %s, %s, %s)")
            value = (crs_id, lec_title, rse_url, desc_lec, date.strftime("%Y-%m-%d"))
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new assignment successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred at the first step, please try again.'})


@app.route("/forum/create", methods=['GET', 'POST'])
def create_forum():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if request.method == 'GET':
        return flask.render_template("forum_window.html", title="Create new forum", edit=False)
    else:
        try:
            frm_name = flask.request.form['frm_name']
            query = "INSERT INTO learn_manage.forums (name) VALUES (%s)"
            value = (frm_name,)
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Create new forum successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to create, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/lecture/edit', methods=['GET', 'POST'])
def edit_lecture():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        lec_id = flask.request.args['id']
        query = "SELECT course_id, name, description FROM learn_manage.lectures WHERE id=%s"
        value = (lec_id,)
        cursor.execute(query, value)
        result1 = cursor.fetchone()
        if result1 is None:
            return flask.redirect("/course")
        return flask.render_template("lecture_window.html", title="Edit lecture", edit=True, l_id=lec_id,
                                     lec_title=result1[1], crs_id=result1[0], desc_lec=result1[2])
    else:
        l_id = flask.request.form["l_id"]
        lec_title = flask.request.form["lec_title"]
        crs_id = flask.request.form["crs_id"]
        print(request.files)
        rse = flask.request.files["rse"]

        if rse != '' and rse.filename != '':
            query_url = "SELECT resource_url FROM learn_manage.lectures WHERE id=%s"
            value_url = (l_id,)
            cursor.execute(query_url, value_url)
            result1 = cursor.fetchone()
            os.remove(result1[0])

            filename = secure_filename(rse.filename)
            rse_url = os.path.join('static\\files', filename)
            rse.save(rse_url)
        else:
            query_url = "SELECT resource_url FROM learn_manage.lectures WHERE id=%s"
            value_url = (l_id,)
            cursor.execute(query_url, value_url)
            result1 = cursor.fetchone()
            rse_url = result1[0]
        desc_lec = flask.request.form["desc_lec"]

        query = "UPDATE learn_manage.lectures SET name=%s, course_id=%s, resource_url=%s, description=%s WHERE id=%s"
        value = (lec_title, crs_id, rse_url, desc_lec, l_id)
        try:
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Edit lecture successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this lecture.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/forum/edit', methods=['GET', 'POST'])
def edit_forum():
    if 'userid' not in session or session["role_id"] != 0:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        f_id = flask.request.args['id']
        query = "SELECT id, name FROM learn_manage.forums WHERE id=%s"
        value = (f_id,)
        cursor.execute(query, value)
        result1 = cursor.fetchone()
        return flask.render_template("forum_window.html", title="Edit forum", edit=True, id=f_id,
                                     frm_name=result1[1])
    else:
        f_id = flask.request.form["f_id"]
        frm_name = flask.request.form["frm_name"]

        query = "UPDATE learn_manage.forums SET name=%s WHERE id=%s"
        value = (frm_name, f_id)
        try:
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Edit forum successfully.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to edit, cannot find this forum.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/messages', methods=['GET'])
def get_messages():
    if 'userid' not in session:
        return flask.redirect("/login")
    info = fill_bar(session['userid'])
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT m.id, CONCAT_WS(' ', u.firstname, u.lastname), m.content, m.send_time FROM learn_manage.messages AS m "
            "INNER JOIN learn_manage.users AS u ON m.sender_id=u.id WHERE m.receiver_id=%s")
        value = (session['userid'],)
    elif search_key[:4] in ("sen\40", "con\40"):
        search_cmd = search_key[:3]
        search_target = search_key[4:]
        if search_cmd == "sen":
            query = (
                "SELECT m.id, CONCAT_WS(' ', u.firstname, u.lastname), m.content, m.send_time FROM learn_manage.messages AS m "
                "INNER JOIN learn_manage.users AS u ON m.sender_id=u.id WHERE m.receiver_id=%s AND CONCAT_WS(' ', u.firstname, u.lastname) LIKE %s")
            value = (session['userid'], f'%{search_target}%')
        else:
            query = (
                "SELECT m.id, CONCAT_WS(' ', u.firstname, u.lastname), m.content, m.send_time FROM learn_manage.messages AS m "
                "INNER JOIN learn_manage.users AS u ON m.sender_id=u.id WHERE m.receiver_id=%s AND m.content LIKE %s")
            value = (session['userid'], f'%{search_target}%')
    else:
        query = (
            "SELECT m.id, CONCAT_WS(' ', u.firstname, u.lastname), m.content, m.send_time FROM learn_manage.messages AS m "
            "INNER JOIN learn_manage.users AS u ON m.sender_id=u.id WHERE m.receiver_id=%s AND (m.content LIKE %s OR CONCAT_WS(' ', u.firstname, u.lastname) LIKE %s)")
        value = (session['userid'], f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("non_admin_table.html", items=results, type='messages', firstname=session['name'],
                                 courses=info[0], grades=info[1], assignments=info[2], forums=info[3])


@app.route('/messages/create', methods=['GET', 'POST'])
def create_message():
    if 'userid' not in session:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if flask.request.method == 'GET':
        return flask.render_template("msg_window.html", title="Write message")
    else:
        try:
            receiver_id = flask.request.form['receiver_id']
            content = flask.request.form['con']
            send_time = datetime.now().strftime('%Y-%m-%d, %H:%M:%S')
            query = "INSERT INTO learn_manage.messages (sender_id, receiver_id, content, send_time) VALUES (%s, %s, %s, %s)"
            value = (session['userid'], receiver_id, content, send_time)
            cursor.execute(query, value)
            cnx.commit()
            if cursor.rowcount > 0:
                return jsonify({'status': 'success', 'message': 'Message successfully created.'})
            else:
                return jsonify({'status': 'error', 'message': 'Fail to send message.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})


@app.route('/messages/delete', methods=['GET'])
def delete_message():
    if 'userid' not in session:
        return flask.redirect("/login")
    try:
        msg_id = flask.request.args['id']
        query = "DELETE FROM learn_manage.messages WHERE id=%s"
        value = (msg_id,)
        cursor.execute(query, value)
        cnx.commit()
    except Exception as e:
        cnx.rollback()
        print(e)
    finally:
        return flask.redirect("/messages")


@app.route('/course/<crs_id>', methods=['GET'])
def get_course(crs_id):
    if 'userid' not in session:
        return flask.redirect("/login")
    info = fill_bar(session['userid'])
    ids = []
    for c_id in info[0]:
        ids.append(c_id[4])
    print(ids)
    if int(crs_id) not in ids:
        print(crs_id, "??")
        return flask.abort(404)
    query = "SELECT id, name, resource_url, description, upload_date FROM learn_manage.lectures WHERE course_id=%s"
    value = (crs_id,)
    cursor.execute(query, value)
    lec = cursor.fetchall()
    return flask.render_template("non_admin_table.html", items=lec, type='lecture', firstname=session['name'],
                                 courses=info[0], grades=info[1], assignments=info[2], forums=info[3])


@app.route('/course/enroll/request', methods=['GET'])
def enroll_view():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT e.id, CONCAT_WS(' ', u.firstname, u.lastname) AS student_name, u.id AS user_id, c.name AS course_name, c.session AS course_session "
            "FROM learn_manage.enrollments AS e "
            "INNER JOIN learn_manage.users AS u ON e.student_id = u.id "
            "INNER JOIN learn_manage.courses AS c ON e.course_id = c.id "
            "WHERE e.status = %s ")
        value = ("under review",)
    elif search_key.isnumeric():
        query = (
            "SELECT e.id, CONCAT_WS(' ', u.firstname, u.lastname) AS student_name, u.id AS user_id, c.name AS course_name, c.session AS course_session "
            "FROM learn_manage.enrollments AS e "
            "INNER JOIN learn_manage.users AS u ON e.student_id = u.id "
            "INNER JOIN learn_manage.courses AS c ON e.course_id = c.id "
            "WHERE e.status = %s and u.id = %s")
        value = ("under review", int(search_key))
    else:
        query = (
            "SELECT e.id, CONCAT_WS(' ', u.firstname, u.lastname) AS student_name, u.id AS user_id, c.name AS course_name, c.session AS course_session "
            "FROM learn_manage.enrollments AS e "
            "INNER JOIN learn_manage.users AS u ON e.student_id = u.id "
            "INNER JOIN learn_manage.courses AS c ON e.course_id = c.id "
            "WHERE e.status = %s AND (c.name LIKE %s OR CONCAT_WS(' ',u.firstname, u.lastname) LIKE %s)")

        value = ("under review", f'%{search_key}%', f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()
    return flask.render_template("console.html", items=results, firstname=session['name'], type="enrollment requests")


@app.route('/enroll', methods=['GET'])
def student_enroll():
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")

    info = fill_bar(session['userid'])

    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = (
            "SELECT courses.id, courses.name, courses.session, CONCAT_WS(' ', u.firstname, u.lastname) AS Instructor "
            "FROM learn_manage.courses "
            "INNER JOIN learn_manage.users AS u ON u.id = courses.leader_id "
            "LEFT JOIN learn_manage.enrollments AS e ON e.course_id = courses.id AND "
            "e.student_id = %s "
            "WHERE e.student_id IS NULL ")
        value = (session['userid'],)
    elif search_key.isnumeric():
        query = (
            "SELECT courses.id, courses.name, courses.session, CONCAT_WS(' ', u.firstname, u.lastname) AS Instructor "
            "FROM learn_manage.courses "
            "INNER JOIN learn_manage.users AS u ON u.id = courses.leader_id "
            "LEFT JOIN learn_manage.enrollments AS e ON e.course_id = courses.id AND "
            "e.student_id = %s "
            "WHERE e.student_id IS NULL AND courses.id=%s")
        value = (session['userid'], int(search_key))
    else:
        query = (
            "SELECT courses.id, courses.name, courses.session, CONCAT_WS(' ', u.firstname, u.lastname) AS Instructor "
            "FROM learn_manage.courses "
            "INNER JOIN learn_manage.users AS u ON u.id = courses.leader_id "
            "LEFT JOIN learn_manage.enrollments AS e ON e.course_id = courses.id AND "
            "e.student_id = %s "
            "WHERE e.student_id IS NULL AND courses.name LIKE %s")
        value = (session['userid'], f'%{search_key}%')
    cursor.execute(query, value)
    results = cursor.fetchall()

    return flask.render_template("non_admin_table.html", items=results, type='enroll', firstname=session['name'],
                                 courses=info[0], grades=info[1], assignments=info[2], forums=info[3])


@app.route("/enroll/request/send", methods=['GET'])
def enroll_send_request():
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")
    crs_id = request.args['id']
    try:
        query = ("INSERT INTO learn_manage.enrollments (student_id, course_id, enrollment_date, status) VALUES (%s, "
                 "%s, %s, %s)")
        value = (session['userid'], crs_id, datetime.today().strftime('%Y-%m-%d'), "under review")
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/enroll")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/enroll")


@app.route('/course/enroll/receive', methods=['GET'])
def course_enroll_receive():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    erl_id = request.args['id']
    try:
        query = "UPDATE learn_manage.enrollments SET status=%s WHERE id=%s"
        value = ("received", erl_id)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/course/enroll/request")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/course/enroll/request")


@app.route('/course/enroll/deny', methods=['GET'])
def course_enroll_deny():
    if 'userid' not in session or session["role_id"] != 0:
        return flask.redirect("/login")
    erl_id = request.args['id']
    try:
        query = "DELETE FROM learn_manage.enrollments WHERE id=%s"
        value = (erl_id,)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/course/enroll/request")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/course/enroll/request")


@app.route('/forum/stu', methods=['GET'])
def forum_list():
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")
    info = fill_bar(session['userid'])
    search_key = request.args.get('items_keyword')
    if search_key is None or search_key == '':
        query = ("SELECT f.id, f.name "
                 "FROM forums f "
                 "WHERE NOT EXISTS ( "
                 "SELECT 1 "
                 "FROM user_forum_memberships m "
                 "WHERE m.forum_id = f.id AND m.user_id = %s) ")
        value = (session['userid'],)
    elif search_key.isnumeric():
        query = ("SELECT f.id, f.name "
                 "FROM forums f "
                 "WHERE f.id = %s AND NOT EXISTS ( "
                 "SELECT 1 "
                 "FROM user_forum_memberships m "
                 "WHERE m.forum_id = f.id AND m.user_id = %s) ")
        value = (int(search_key), session['userid'])
    else:
        query = ("SELECT f.id, f.name "
                 "FROM forums f "
                 "WHERE f.name LIKE %s AND NOT EXISTS ( "
                 "SELECT 1 "
                 "FROM user_forum_memberships m "
                 "WHERE m.forum_id = f.id AND m.user_id = %s) ")
        value = (f'%{search_key}%', session['userid'])
    cursor.execute(query, value)
    results = cursor.fetchall()

    return flask.render_template("non_admin_table.html", items=results, type='join forum', firstname=session['name'],
                                 courses=info[0], grades=info[1], assignments=info[2], forums=info[3])


@app.route('/forum/stu/join', methods=['GET'])
def forum_join():
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")
    frm_id = request.args['id']
    try:
        query = "INSERT INTO learn_manage.user_forum_memberships (user_id, forum_id) VALUES (%s, %s)"
        value = (session['userid'], frm_id)
        cursor.execute(query, value)
        cnx.commit()
        return flask.redirect("/forum/stu")
    except Exception as e:
        cnx.rollback()
        print(e)
        return flask.redirect("/forum/stu")


@app.route('/forum/view/<frm_id>', methods=['GET'])
def forum_view(frm_id):
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")
    search_key = request.args.get('items_keyword')
    info = fill_bar(session['userid'])
    query = "SELECT id, name FROM learn_manage.forums WHERE id=%s"
    value = (int(frm_id),)
    cursor.execute(query, value)
    frm = cursor.fetchone()
    if search_key is None or search_key == '':
        query = ("SELECT CONCAT_WS(' ', u.firstname, u.lastname), f.name, p.content, p.date, p.id "
                 "FROM learn_manage.forum_posts AS p "
                 "INNER JOIN learn_manage.forums f on p.forum_id = f.id "
                 "INNER JOIN learn_manage.users AS u ON u.id = p.poster_id "
                 "WHERE f.id=%s ")
        value = (int(frm_id),)
    else:
        query = ("SELECT CONCAT_WS(' ', u.firstname, u.lastname), f.name, p.content, p.date, p.id "
                 "FROM learn_manage.forum_posts AS p "
                 "INNER JOIN learn_manage.forums f on p.forum_id = f.id "
                 "INNER JOIN learn_manage.users AS u ON u.id = p.poster_id "
                 "WHERE f.id=%s AND (p.content LIKE %s OR CONCAT_WS(' ', u.firstname, u.lastname) LIKE %s) ")
        value = (frm_id, search_key, search_key)
    cursor.execute(query, value)
    results = cursor.fetchall()
    print("This?")

    return flask.render_template("stu_forum.html", posts=results, firstname=session['name'],
                                 courses=info[0], grades=info[1], assignments=info[2], forums=info[3], frm=frm)


@app.route('/forum/stu/post', methods=['GET', 'POST'])
def forum_post():
    if 'userid' not in session or session["role_id"] != 1:
        return jsonify({'status': 'unauthenticated', 'message': 'You do not have access to perform this operation'})
    if request.method == 'GET':
        frm_id = request.args['id']
        return flask.render_template("post_window.html", title="Your Post", frm_id=frm_id)
    else:
        frm_id = request.form['frm_id']
        content = request.form['content']
        try:
            query = "INSERT INTO learn_manage.forum_posts (poster_id, forum_id, content, date) VALUES (%s, %s, %s, %s)"
            value = (int(session['userid']), int(frm_id), content, datetime.now().strftime("%Y-%m-%d"))
            cursor.execute(query, value)
            cnx.commit()
            return flask.jsonify({'status': 'success', 'message': 'You have successfully posted'})
        except Exception as e:
            cnx.rollback()
            return flask.jsonify({'status': 'error', 'message': str(e)})


@app.route('/forum/poster/detail', methods=['GET', 'POST'])
def forum_poster_detail():
    if 'userid' not in session or session["role_id"] != 1:
        return flask.redirect("/login")
    if request.method == 'GET':
        info = fill_bar(session['userid'])
        pst_id = request.args['id']
        query = ("SELECT CONCAT_WS(' ', u.firstname, u.lastname), p.content, p.date, p.id "
                 "FROM learn_manage.forum_posts AS p "
                 "INNER JOIN learn_manage.users AS u ON u.id = p.poster_id "
                 "WHERE p.id=%s ")
        value = (int(pst_id),)
        cursor.execute(query, value)
        con = cursor.fetchone()
        query = ("SELECT CONCAT_WS(' ', u.firstname, u.lastname), c.content, c.date FROM learn_manage.users AS u "
                 "INNER JOIN learn_manage.comments AS c ON c.sender_id=u.id")
        cursor.execute(query)
        comments = cursor.fetchall()

        return flask.render_template("post_detail.html", firstname=session['name'], post=con,
                                     courses=info[0], grades=info[1], assignments=info[2], forums=info[3], cmts=comments)
    else:
        cmt = request.form['cmt']
        pst_id = request.form['pst_id']
        try:
            query = "INSERT INTO learn_manage.comments (sender_id, content, date,post_id) VALUES (%s, %s, %s, %s)"
            value = (int(session['userid']), cmt, datetime.now().strftime("%Y-%m-%d"), pst_id)
            cursor.execute(query, value)
            cnx.commit()
        except Exception as e:
            cnx.rollback()
            print(e)
        finally:
            return flask.redirect(f"/forum/poster/detail?id={pst_id}")



if __name__ == '__main__':
    app.run()
