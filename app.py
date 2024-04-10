import flask
from flask import Flask
import mysql.connector


app = Flask(__name__)


@app.route('/')
def index():  # put application's code here
    if not flask.request.cookies.get("userInfo"):
        return flask.redirect("/login")
    else:
        return 'Hello World!'


@app.route('/login', methods=['GET', 'POST'])
def login():
    return flask.render_template("login.html")


if __name__ == '__main__':
    app.run()
