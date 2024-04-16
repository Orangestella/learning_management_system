import flask
from flask import Flask, session
import utils
import mysql.connector

cnx = mysql.connector.connect(user='root',
                              password='SECRET', host='127.0.0.1',
                              database='learn_manage')
cursor = cnx.cursor()

app = Flask(__name__)
app.secret_key = 'SECRET'


@app.route('/')
def index():  # put application's code here
    if 'userid' not in session:
        return flask.redirect("/login")
    else:
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
            return flask.jsonify({'status': 'success', 'message': 'Welcome!'})



if __name__ == '__main__':
    app.run()
