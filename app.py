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
        if "userid" not in session:
            session["userid"] = int(flask.request.cookies.get("userid"))
            print(int(flask.request.cookies.get("userid")))
        query = "SELECT role_id, firstname FROM users WHERE id=%s"
        value = (session["userid"],)
        cursor.execute(query, value)
        result = cursor.fetchone()
        fname = result[1]
        print(result)
        if result[0] == 0:  # Admin
            query = "SELECT COUNT(*) FROM users"
            cursor.execute(query)
            result = cursor.fetchone()
            total_users = result[0]
            speech_rate = 0.4
            assign_rate = 0.7
            total_courses = 19
            return flask.render_template("index_admin.html", firstname=fname, total_courses=total_courses,
                                         speech_rate=speech_rate, total_users=total_users, assign_rate=assign_rate)
        elif result[0] == 1:  # Student
            return "You are student."
        elif result[0] == 2:  # Instructor
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
    search_key = request.args.get('account_keyword')
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
    return flask.render_template("account_console.html", accounts=results, firstname=session['name'])


@app.route('/account/create_account', methods=['GET', 'POST'])
def create_account():
    if flask.request.method == 'GET':
        return flask.render_template("create_account.html")
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


if __name__ == '__main__':
    app.run()
