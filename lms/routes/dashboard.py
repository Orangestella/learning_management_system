from ..search import search_rows
import flask
from flask import session, request
from ..db import get_db
from ..security import require_roles
from ..views import render
from ..navigation import fill_bar_stu, fill_bar_ins
bp = flask.Blueprint('dashboard', __name__)

@bp.route('/', methods=['GET'])
@require_roles()
def index():
    cursor = get_db().cursor()
    query1 = 'SELECT role_id, firstname FROM users WHERE id=?'
    value = (session['userid'],)
    cursor.execute(query1, value)
    result1 = cursor.fetchone()
    fname = result1[1]
    session['role_id'] = result1[0]
    session['name'] = fname
    if result1[0] == 0:
        query1 = 'SELECT COUNT(*) FROM users'
        cursor.execute(query1)
        result1 = cursor.fetchone()
        query2 = 'SELECT COUNT(*) FROM courses'
        cursor.execute(query2)
        result2 = cursor.fetchone()
        total_users = result1[0]
        query3 = 'SELECT COALESCE(1.0 * COUNT(fp.id) / NULLIF(COUNT(DISTINCT ufm.user_id), 0), 0) FROM user_forum_memberships AS ufm LEFT JOIN forum_posts AS fp ON ufm.user_id = fp.poster_id AND ufm.forum_id = fp.forum_id'
        cursor.execute(query3)
        result3 = cursor.fetchone()
        speech_rate = result3[0]
        query4 = 'SELECT COALESCE(1.0 * COUNT(DISTINCT sub.id) / NULLIF(COUNT(DISTINCT asn.id), 0), 0) FROM assignments AS asn LEFT JOIN submissions AS sub ON sub.assignment_id=asn.id'
        cursor.execute(query4)
        result4 = cursor.fetchone()
        assign_rate = result4[0]
        total_courses = result2[0]
        return render('index_admin.html', firstname=fname, total_courses=total_courses, speech_rate=speech_rate, total_users=total_users, assign_rate=assign_rate)
    elif result1[0] == 1:
        results = fill_bar_stu(session['userid'])
        return render('index_stu.html', firstname=fname, courses=results[0], grades=results[1], assignments=results[2], forums=results[3])
    elif result1[0] == 2:
        info = fill_bar_ins(session['userid'])
        items = search_rows('lecture', "SELECT l.id, l.name, (c.name || ' ' || c.session), l.resource_url, l.description, l.upload_date FROM lectures l JOIN courses c ON c.id=l.course_id WHERE EXISTS (SELECT 1 FROM ins_crs_assignments i WHERE i.crs_id=c.id AND i.ins_id=?)", (session['userid'],), order_by='l.id')
        return render('ins_table.html', firstname=fname, courses=info[0], assignments=info[1], edit=False, type='lecture', items=items)
    else:
        return flask.abort(404)
