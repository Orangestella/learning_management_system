from .db import get_db

def fill_bar_stu(userid):
    cursor = get_db().cursor()
    query = "SELECT c.name, c.session, (COALESCE(u.firstname, '') || ' ' || COALESCE(u.lastname, '')), c.description, c.id FROM courses AS c INNER JOIN enrollments AS e ON e.course_id=c.id INNER JOIN users AS u ON u.id=c.leader_id WHERE e.student_id=? AND e.status=?"
    value = (userid, 'received')
    cursor.execute(query, value)
    results_crs = cursor.fetchall()
    query = 'SELECT c.name, a.name, s.id FROM submissions AS s INNER JOIN assignments AS a ON s.assignment_id=a.id INNER JOIN courses AS c ON a.course_id = c.id WHERE s.student_id=? AND s.score IS NOT NULL'
    value = (userid,)
    cursor.execute(query, value)
    results_grd = cursor.fetchall()
    query = 'SELECT a.name, a.deadline, a.id FROM assignments AS a INNER JOIN enrollments AS e ON e.course_id=a.course_id WHERE e.student_id=? AND e.status=?'
    value = (userid, 'received')
    cursor.execute(query, value)
    results_asn = cursor.fetchall()
    query = 'SELECT f.name, f.id FROM forums AS f INNER JOIN user_forum_memberships AS m ON f.id = m.forum_id WHERE m.user_id=?'
    value = (userid,)
    cursor.execute(query, value)
    results_frm = cursor.fetchall()
    return (results_crs, results_grd, results_asn, results_frm)

def fill_bar_ins(userid):
    cursor = get_db().cursor()
    query = 'SELECT c.name, c.session, c.id FROM courses AS c INNER JOIN ins_crs_assignments AS i ON i.crs_id = c.id WHERE i.ins_id = ?;'
    value = (userid,)
    cursor.execute(query, value)
    results_crs = cursor.fetchall()
    query = 'SELECT a.name, a.deadline, a.id FROM assignments AS a INNER JOIN ins_crs_assignments AS i ON i.crs_id=a.course_id WHERE i.ins_id=?'
    cursor.execute(query, value)
    results_asn = cursor.fetchall()
    return (results_crs, results_asn)
