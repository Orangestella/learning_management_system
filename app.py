import flask
from flask import Flask, session
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
        return flask.render_template("index.html", id=session["userid"])


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
            resp = flask.make_response(flask.jsonify({'status': 'success', 'message': 'Welcome!'}))
            print(values)
            resp.set_cookie('userid', str(id), max_age=36000)
            print("cookie set")
            return resp



if __name__ == '__main__':
    app.run()
