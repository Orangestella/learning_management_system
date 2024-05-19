from datetime import datetime

import flask
from flask import Flask, session, request, make_response, jsonify
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
            return "You are student."
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
                    return jsonify({'status': 'error', 'message': 'Invalid Instructor ID.'})
                else:
                    query = "SELECT"

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
        print("?")
        return flask.render_template("course_window.html", title="Edit course", edit=True, id=crs_id,
                                     crs_name=result1[0], ids=ids, desc=result1[1], crs_session=result1[2])
    else:
        print("??")
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
                query = "SELECT id FROM learn_manage.users WHERE id=%s"
                value = (int(std_id),)
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
                            query = ("INSERT INTO learn_manage.enrollments (student_id, course_id, enrollment_date) "
                                     "VALUES (%s, %s, %s)")
                            value = (int(std_id), crs_id, date.strftime("%Y-%m-%d"))
                            cursor.execute(query, value)
                            cnx.commit()
                return flask.jsonify({'status': 'success', 'message': 'Success.'})
            else:
                try:
                    for std_id in std_ids_list:
                        print("?????")
                        date = datetime.now()
                        query = ("INSERT INTO learn_manage.enrollments (student_id, course_id, enrollment_date) VALUES "
                                 "(%s, %s, %s)")
                        value = (int(std_id), crs_id, date.strftime("%Y-%m-%d"))
                        cursor.execute(query, value)
                        cnx.commit()
                    return flask.jsonify({'status': 'success', 'message': 'Success.'})
                except Exception as e:
                    cnx.rollback()
                    return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})
        except Exception as e:
            cnx.rollback()
            return jsonify({'status': 'error', 'message': f'{e} occurred, please try again.'})





if __name__ == '__main__':
    app.run()
