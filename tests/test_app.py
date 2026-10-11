import ast
import io
import re
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from lms import create_app
from lms.db import get_db
from lms.security import hash_password


class ApplicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'correct-test-password'
        cls.hashed = hash_password(cls.password)

    def setUp(self):
        temporary_root = Path('instance').resolve()
        temporary_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        assert Path(self.temp.name).resolve().is_relative_to(temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key',
                               'DATABASE': str(Path(self.temp.name) / 'test.sqlite'),
                               'UPLOAD_FOLDER': str(Path(self.temp.name) / 'uploads')})
        with self.app.app_context():
            db = get_db()
            for identifier, role in [(1, 0), (2, 2), (3, 1), (4, 2), (5, 1)]:
                db.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?)', (identifier, f'User{identifier}', 'Test', self.hashed, role))
            db.executescript("""
                INSERT INTO courses VALUES (1,'Course One',2,'Description','2026'),(2,'Course Two',4,'Private','2026');
                INSERT INTO ins_crs_assignments(ins_id,crs_id) VALUES (2,1),(4,2);
                INSERT INTO enrollments(student_id,course_id,enrollment_date,status) VALUES (3,1,'2026-01-01','received'),(5,2,'2026-01-01','received');
                INSERT INTO assignments VALUES (1,'Assignment One',1,'2027-01-01T10:00','Essay'),(2,'Assignment Two',2,'2027-01-01T10:00','Private');
                INSERT INTO forums VALUES (1,'Forum One'),(2,'Forum Two');
                INSERT INTO user_forum_memberships(user_id,forum_id) VALUES (3,1),(5,2);
                INSERT INTO forum_posts VALUES (1,3,1,'Public post','2026-01-01'),(2,5,2,'Private post','2026-01-01');
                INSERT INTO comments(sender_id,post_id,content,date) VALUES (3,1,'First comment','2026-01-01'),(5,2,'Secret comment','2026-01-01');
                INSERT INTO submissions VALUES (1,1,90,'Good',3,'2026-01-01','/files/test.pdf'),(2,2,80,'Private',5,'2026-01-01','/files/private.pdf');
                INSERT INTO lectures VALUES (1,1,'Lecture One','/files/lecture.pdf','Notes','2026-01-01');
                INSERT INTO notifications VALUES (1,'Notice One','Visible', '2026-01-01',1,2),(2,'Notice Two','Private', '2026-01-01',2,4);
                INSERT INTO messages VALUES (1,2,3,'Message One','2026-01-01'),(2,4,5,'Message Two','2026-01-01');
            """)
            db.commit()
        for name in ('test.pdf', 'private.pdf', 'lecture.pdf'):
            (Path(self.temp.name) / 'uploads' / name).write_bytes(b'%PDF-1.4 test')
        self.client = self.app.test_client()

    def csrf(self, client=None):
        client = client or self.client
        client.get('/login')
        with client.session_transaction() as state:
            return state['csrf_token']

    def login(self, identifier=1, client=None):
        client = client or self.client
        response = client.post('/login', data={'id': str(identifier),
                             'psw': self.password, 'csrf_token': self.csrf(client)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'success')

    def post(self, path, data=None):
        with self.client.session_transaction() as state:
            token = state['csrf_token']
        return self.client.post(path, data=data or {}, headers={'X-CSRF-Token': token})

    def scalar(self, query, args=()):
        with self.app.app_context():
            row = get_db().execute(query, args).fetchone()
            return row[0] if row else None

    def test_sqlite_queries_compile(self):
        with self.app.app_context():
            for path in Path('lms').rglob('*.py'):
                if path.name == 'legacy_import.py':
                    continue  # The dump parser contains SQL-shaped regexes; its queries are exercised by import tests.
                tree = ast.parse(path.read_text(encoding='utf-8'))
                parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and not isinstance(parents.get(node), ast.JoinedStr) and isinstance(node.value, str) and re.match(r'^(SELECT|INSERT|UPDATE|DELETE) ', node.value):
                        with self.subTest(file=str(path), sql=node.value):
                            get_db().execute('EXPLAIN ' + node.value, (1,) * node.value.count('?'))

    def test_unsigned_cookie_cannot_authenticate(self):
        self.client.set_cookie('localhost', 'userid', '1')
        response = self.client.get('/account')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')

    def test_login_with_personal_id_and_password_only(self):
        page = self.client.get('/login').get_data(as_text=True)
        self.assertIn('autocomplete="username"', page)
        self.assertNotIn('name="firstname"', page)
        self.assertNotIn('name="lastname"', page)
        token = self.csrf()
        for identifier, password, status in [('1', 'wrong', 401), ('999', self.password, 401),
                                             ('invalid', self.password, 400)]:
            response = self.client.post('/login', data={'id': identifier, 'psw': password, 'csrf_token': token})
            self.assertEqual(response.status_code, status)
        self.login()
        self.assertEqual(self.client.get('/account').status_code, 200)

    def test_csrf_and_safe_gets(self):
        self.assertEqual(self.client.post('/login', data={'id':'1'}).status_code, 400)
        self.login()
        for path in ('/logout', '/account/delete?id=3', '/course/delete?id=1', '/forum/delete?id=1', '/course/enroll/receive?id=1'):
            self.assertEqual(self.client.get(path).status_code, 405)
            self.assertEqual(self.client.post(path).status_code, 400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM users'), 5)

    def test_role_pages_and_searches(self):
        paths = {1: ['/', '/account', '/course', '/assignment', '/lecture', '/forum', '/forum/membership/1', '/course/enroll/request', '/account/create', '/account/edit?id=3', '/course/create', '/course/edit?id=1', '/assignment/edit?id=1', '/lecture/edit?id=1', '/forum/edit?id=1'],
                 2: ['/', '/course/1', '/student/1', '/assignment/1', '/notification', '/messages', '/assignment/create', '/lecture/create?id=1', '/submission/eval?id=1', '/notification/create', '/notification/edit?id=1', '/notification/view?id=1'],
                 3: ['/', '/course/1', '/assignment/1', '/grade/1', '/enroll', '/forum/stu', '/forum/view/1', '/forum/stu/post?id=1', '/forum/poster/detail?id=1', '/notification', '/notification/view?id=1', '/messages', '/messages/create']}
        for identifier, pages in paths.items():
            self.login(identifier)
            for page in pages:
                for keyword in ('', '1', 'One', "' OR 1=1 --"):
                    url = page + ('&' if '?' in page else '?') + 'items_keyword=' + keyword
                    with self.subTest(role=identifier, page=url):
                        self.assertEqual(self.client.get(url).status_code, 200)

    def test_student_resource_authorization(self):
        self.login(3)
        for path in ('/account', '/course/2', '/assignment/2', '/forum/view/2', '/forum/poster/detail?id=2', '/notification/view?id=2', '/files/private.pdf'):
            self.assertIn(self.client.get(path).status_code, (403, 404))
        self.assertEqual(self.post('/assignment/2', {'asn_file':(io.BytesIO(b'test'), 'test.pdf')}).status_code, 404)
        self.assertEqual(self.post('/messages/delete?id=2').status_code, 404)
        self.assertEqual(self.post('/forum/stu/post', {'frm_id':'2', 'content':'Forbidden'}).status_code, 404)

    def test_instructor_resource_authorization(self):
        self.login(2)
        for path in ('/student/2', '/assignment/2', '/submission/eval?id=2', '/notification/edit?id=2'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.post('/assignment/create', {'asn_name':'Bad', 'crs_id':'2','ddl':'2027-01-01','desc_asn':''}).status_code, 404)
        self.assertEqual(self.post('/notification/delete?id=2').status_code, 404)

    def test_private_uploads_and_random_names(self):
        self.login(3)
        self.assertEqual(self.client.get('/files/test.pdf').status_code, 200)
        response = self.post('/assignment/1', {'asn_file':(io.BytesIO(b'%PDF-1.4'), '../../same.pdf')})
        self.assertEqual(response.json['status'], 'success')
        url = self.scalar('SELECT attach_file FROM submissions ORDER BY id DESC LIMIT 1')
        self.assertRegex(url, r'^/files/[a-f0-9]{32}\.pdf$')
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment', download.headers['Content-Disposition'])
        count = self.scalar('SELECT COUNT(*) FROM submissions')
        with self.assertLogs(self.app.logger, level='ERROR'):
            response = self.post('/assignment/1', {'asn_file':(io.BytesIO(b'html'), 'test.html')})
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM submissions'), count)
        self.assertEqual(self.client.get('/static/files/test.pdf').status_code, 404)

    def test_logout_revokes_replayed_session(self):
        self.login(3)
        cookie = next(cookie.value for cookie in self.client.cookie_jar if cookie.name == 'lms_session')
        self.assertEqual(self.post('/logout').status_code, 302)
        replay = self.app.test_client()
        replay.set_cookie('localhost', 'lms_session', cookie)
        self.assertEqual(replay.get('/').location, '/login')

    def test_expired_session(self):
        self.login(3)
        with self.app.app_context():
            get_db().execute('UPDATE auth_sessions SET expires_at=?', (int(time.time()) - 1,))
            get_db().commit()
        self.assertEqual(self.client.get('/').location, '/login')

    def test_blank_password_keeps_hash_and_role(self):
        self.login()
        response = self.post('/account/edit', {'e_id':'3','c_firstname':'User3','c_lastname':'Test','c_roles':'1','c_psw':'','e_psw':''})
        self.assertEqual(response.json['status'], 'success')
        self.assertEqual(self.scalar('SELECT password FROM users WHERE id=3'), self.hashed)
        self.assertEqual(self.scalar('SELECT role_id FROM users WHERE id=3'), 1)

    def test_course_creation_and_cascades(self):
        self.login()
        response = self.post('/course/create', {'course_name':'New', 'session':'2026', 'ins_ids':'2  2 4', 'description':'Test'})
        self.assertEqual(response.json['status'], 'success')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM ins_crs_assignments WHERE crs_id=3'), 2)
        self.assertEqual(self.post('/course/delete?id=1').status_code, 302)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM assignments WHERE course_id=1'), 0)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM submissions WHERE assignment_id=1'), 0)

    def test_notification_search_and_delete(self):
        self.login(2)
        html = self.client.get('/notification?items_keyword=One').text
        self.assertIn('Notice One', html)
        self.assertNotIn('Notice Two', html)
        self.assertEqual(self.post('/notification/delete?id=1').status_code, 302)
        self.assertIsNone(self.scalar('SELECT id FROM notifications WHERE id=1'))

    def test_comments_are_scoped_and_escaped(self):
        self.login(3)
        self.post('/forum/poster/detail?id=1', {'pst_id':'1', 'cmt':'<script>alert(1)</script>'})
        html = self.client.get('/forum/poster/detail?id=1').text
        self.assertIn('First comment', html)
        self.assertNotIn('Secret comment', html)
        self.assertIn('&lt;script&gt;', html)

    def test_cookie_flags_and_login_rate_limit(self):
        response = self.client.get('/login')
        cookie = response.headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Lax', cookie)
        token = self.csrf()
        for i in range(10):
            response = self.client.post('/login', data={'id':'1','psw':'wrong','csrf_token':token})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.post('/login', data={'id':'1','csrf_token':token}).status_code, 429)
        self.assertEqual(self.client.post('/login', data={'id':'0001','csrf_token':token}).status_code, 429)

    def test_password_storage_and_self_delete(self):
        self.login()
        response = self.post('/account/create', {'c_firstname':'New','c_lastname':'Person','c_psw':'new-password-123','c_roles':'1'})
        self.assertEqual(response.json['status'], 'success')
        self.assertTrue(self.scalar('SELECT password FROM users ORDER BY id DESC LIMIT 1').startswith('pbkdf2:sha256:600000$'))
        self.post('/account/delete?id=1')
        self.assertEqual(self.scalar('SELECT role_id FROM users WHERE id=1'), 0)

    def test_course_transaction_rolls_back_after_partial_write(self):
        self.login()
        with self.app.app_context():
            get_db().execute("CREATE TRIGGER reject_mapping BEFORE INSERT ON ins_crs_assignments BEGIN SELECT RAISE(ABORT, 'test failure'); END")
            get_db().commit()
        with self.assertLogs(self.app.logger, level='ERROR'):
            response = self.post('/course/create', {'course_name':'Must roll back','session':'2026','ins_ids':'2','description':''})
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM courses'), 2)

    def test_invalid_grade_rejected_and_valid_grade_saved(self):
        self.login(2)
        self.assertEqual(self.post('/submission/eval', {'s_id':'1','score':'101','fb':'bad'}).status_code, 400)
        self.assertEqual(self.post('/submission/eval', {'s_id':'1','score':'85','fb':'Updated'}).json['status'], 'success')
        self.assertEqual(self.scalar('SELECT score FROM submissions WHERE id=1'), 85)

    def test_enrollment_and_forum_membership_flow(self):
        self.login(3)
        self.assertEqual(self.post('/enroll/request/send?id=2').status_code, 302)
        self.assertEqual(self.client.get('/course/2').status_code, 404)
        self.assertEqual(self.post('/forum/stu/join?id=2').status_code, 302)
        self.assertEqual(self.client.get('/forum/view/2').status_code, 200)
        self.assertEqual(self.post('/forum/stu/leave?id=2').status_code, 302)
        self.assertEqual(self.client.get('/forum/view/2').status_code, 404)
        enrollment = self.scalar('SELECT id FROM enrollments WHERE student_id=3 AND course_id=2')
        self.login(1)
        self.assertEqual(self.post(f'/course/enroll/receive?id={enrollment}').status_code, 302)
        self.login(3)
        self.assertEqual(self.client.get('/course/2').status_code, 200)

    def test_account_change_revokes_existing_login(self):
        student = self.app.test_client()
        self.login(3, student)
        self.login()
        response = self.post('/account/edit', {'e_id':'3','c_firstname':'User3','c_lastname':'Test','c_roles':'1','c_psw':'','e_psw':''})
        self.assertEqual(response.json['status'], 'success')
        self.assertEqual(student.get('/').location, '/login')

    def test_failed_submission_removes_pending_upload(self):
        self.login(3)
        with self.app.app_context():
            get_db().execute("CREATE TRIGGER reject_submission BEFORE INSERT ON submissions BEGIN SELECT RAISE(ABORT, 'test failure'); END")
            get_db().commit()
        upload_directory = Path(self.temp.name) / 'uploads'
        before = set(upload_directory.iterdir())
        with self.assertLogs(self.app.logger, level='ERROR'):
            response = self.post('/assignment/1', {'asn_file':(io.BytesIO(b'%PDF-1.4'), 'test.pdf')})
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(set(upload_directory.iterdir()), before)

    def table_ids(self, path, query='', scope='all'):
        response = self.client.get(path, query_string={'items_keyword': query, 'search_field': scope})
        self.assertEqual(response.status_code, 200)
        if path == '/messages':
            return [int(identifier) for identifier in re.findall(r'data-message-id="(\d+)"', response.text)]
        body = re.search(r'<tbody>(.*?)</tbody>', response.text, re.S).group(1)
        return [int(identifier) for identifier in re.findall(r'<tr>\s*<td>\s*(\d+)\s*</td>', body)]

    def test_advanced_search_boolean_logic_and_field_scope(self):
        self.login()
        self.assertEqual(self.table_ids('/course', 'name:"Course One" id:1'), [1])
        self.assertEqual(self.table_ids('/course', 'name:"Course One" OR name:"Course Two" id:2'), [1, 2])
        self.assertEqual(self.table_ids('/course', 'Course -name:Two'), [1])
        self.assertEqual(self.table_ids('/course', 'Private', 'description'), [2])
        self.assertEqual(self.table_ids('/course', 'Private', 'name'), [])
        self.assertEqual(self.table_ids('/course', 'id:>=1 id:<2'), [1])
        self.assertEqual(self.table_ids('/course', 'name:=Course'), [])
        self.assertEqual(self.table_ids('/course', 'crs 1'), [1])
        self.assertEqual(self.table_ids('/course', 'ins 4'), [2])
        self.assertEqual(self.table_ids('/account', 'role:student -id:5'), [3])

    def test_advanced_search_literal_wildcards_and_apostrophes(self):
        self.login()
        with self.app.app_context():
            get_db().execute("UPDATE courses SET name=? WHERE id=1", ("100%_O'Neil",))
            get_db().commit()
        self.assertEqual(self.table_ids('/course', "O'Neil"), [1])
        self.assertEqual(self.table_ids('/course', '%'), [1])
        self.assertEqual(self.table_ids('/course', '_'), [1])
        with self.app.app_context():
            get_db().execute('UPDATE courses SET name=? WHERE id=2', ('OR',))
            get_db().commit()
        self.assertEqual(self.table_ids('/course', '"OR"'), [2])

    def test_advanced_search_errors_remain_in_page(self):
        self.login()
        for query in ('missing:foo', 'name:"unfinished', 'id:not-a-number', 'OR name:One', 'name:One OR', 'name:>=One'):
            response = self.client.get('/course', query_string={'items_keyword': query})
            self.assertEqual(response.status_code, 200)
            self.assertIn('role="alert"', response.text)
            self.assertIn('Advanced search syntax', response.text)
            self.assertIn('No items found.', response.text)

    def test_advanced_search_or_cannot_bypass_authorization(self):
        self.login(3)
        self.assertEqual(self.table_ids('/messages', 'content:"Message One" OR content:"Message Two"'), [1])
        self.assertEqual(self.table_ids('/notification', 'title:"Notice One" OR title:"Notice Two"'), [1])
        self.assertEqual(self.table_ids('/course/1', 'id:1 OR course_id:2'), [1])

    def test_advanced_search_dates_and_help_controls(self):
        self.login()
        self.assertEqual(self.table_ids('/assignment', 'deadline:>=2027-01-01 deadline:<2027-01-02'), [1, 2])
        self.assertEqual(self.table_ids('/lecture', 'date:2026-01-01'), [1])
        self.assertEqual(self.table_ids('/lecture', 'date:<2026-01-01'), [])
        html = self.client.get('/course', query_string={'items_keyword':'Private','search_field':'description'}).text
        self.assertIn('aria-controls="search-help"', html)
        self.assertIn('name="search_field"', html)
        self.assertIn('value="description" selected', html)

    def test_forum_floors_message_bubbles_and_personal_id(self):
        self.login(3)
        board = self.client.get('/forum/view/1').text
        self.assertIn('Topic / author', board)
        self.assertIn('Personal ID: <strong>3</strong>', board)
        self.assertIn('New topic', board)
        thread = self.client.get('/forum/poster/detail?id=1').text
        self.assertIn('forum-floor', thread)
        self.assertIn('#2', thread)
        self.assertIn('Personal ID: 3', thread)
        self.assertNotIn('Secret comment', thread)
        with self.app.app_context():
            get_db().execute("INSERT INTO messages(sender_id,receiver_id,content,send_time) VALUES (2,3,?,?)", ('<script>alert(1)</script>\nSecond line', '2026-01-02'))
            get_db().execute("INSERT INTO messages(sender_id,receiver_id,content,send_time) VALUES (3,3,?,?)", ('Older self message', '2025-12-31'))
            get_db().commit()
        inbox = self.client.get('/messages').text
        self.assertIn('message-waterfall', inbox)
        self.assertIn('message-bubble', inbox)
        self.assertIn('&lt;script&gt;', inbox)
        self.assertNotIn('<script>alert(1)</script>', inbox)
        self.assertNotIn('Message Two', inbox)
        self.assertLess(inbox.index('Second line'), inbox.index('Message One'))
        self.assertLess(inbox.index('Message One'), inbox.index('Older self message'))
        self.assertIn('message-self', inbox)
        self.assertEqual(self.post('/messages/delete?id=2').status_code, 404)
        self.assertEqual(self.post('/messages/delete?id=1').status_code, 302)

    def test_recipient_lookup_by_id_or_name_and_send_validation(self):
        self.assertEqual(self.client.get('/messages/recipients?q=User').status_code, 302)
        self.login(3)
        for keyword in ('2', '0002', 'User2', 'Test User2'):
            result = self.client.get('/messages/recipients', query_string={'q': keyword}).json
            self.assertEqual(result['users'], [{'id': 2, 'name': 'User2 Test'}])
            self.assertFalse(result['has_more'])
        for keyword in ('', '999', '%', '_', "' OR 1=1 --"):
            self.assertEqual(self.client.get('/messages/recipients', query_string={'q': keyword}).json['users'], [])
        self.assertEqual(self.client.get('/messages/recipients', query_string={'q': 'x' * 101}).status_code, 400)
        with self.app.app_context():
            db = get_db()
            for identifier in range(10, 32):
                db.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?)', (identifier, 'Match', 'Test', self.hashed, 1))
            db.commit()
        result = self.client.get('/messages/recipients?q=Match').json
        self.assertEqual(len(result['users']), 20)
        self.assertTrue(result['has_more'])
        before = self.scalar('SELECT COUNT(*) FROM messages')
        self.assertEqual(self.post('/messages/create', {'receiver_id': '999', 'con': 'No recipient'}).status_code, 400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM messages'), before)
        self.assertEqual(self.post('/messages/create', {'receiver_id': '2', 'con': 'Resolved recipient'}).json['status'], 'success')
        self.assertEqual(self.scalar('SELECT receiver_id FROM messages WHERE content=?', ('Resolved recipient',)), 2)


if __name__ == '__main__':
    unittest.main()
