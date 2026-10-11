import tempfile
import unittest
from pathlib import Path
from werkzeug.security import check_password_hash

from lms import create_app
from lms.db import get_db
from lms.legacy_import import import_dump, read_dump, literal_rows

DUMP = Path(__file__).resolve().parent.parent / 'data' / 'legacy_mysql.sql'


class LegacyImportTest(unittest.TestCase):
    def setUp(self):
        root = Path('instance').resolve()
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        assert Path(self.temp.name).resolve().is_relative_to(root)
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'legacy-test',
                               'DATABASE': str(Path(self.temp.name) / 'lms.sqlite3'),
                               'UPLOAD_FOLDER': str(Path(self.temp.name) / 'uploads')})

    def test_literal_parser_and_no_executable_values(self):
        self.assertEqual(literal_rows("(1,'O\\'Neil; hello',NULL),(2,'static\\\\files\\\\test.pdf',3)"),
                         [[1, "O'Neil; hello", None], [2, 'static\\files\\test.pdf', 3]])
        with self.assertRaises(ValueError):
            literal_rows('(1, SELECT password FROM users)')

    def test_original_dump_preserved_and_passwords_replaced(self):
        original = read_dump(DUMP)
        with self.app.app_context():
            report = import_dump(DUMP)
            self.assertEqual(report['imported'], sum(len(rows) for rows in original.values()))
            self.assertEqual(len(report['credentials']), 9)
            self.assertEqual(len(report['missing_files']), 3)
            db = get_db()
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            lecture_file = db.execute('SELECT resource_url FROM lectures WHERE id=2').fetchone()[0]
            submission_file = db.execute('SELECT attach_file FROM submissions WHERE id=1').fetchone()[0]
            self.assertNotEqual(lecture_file, submission_file)
            for account in report['credentials']:
                hashed = db.execute('SELECT password FROM users WHERE id=?', (account['id'],)).fetchone()[0]
                self.assertTrue(hashed.startswith('pbkdf2:sha256:600000$'))
                self.assertTrue(check_password_hash(hashed, account['password']))
            before = db.execute('SELECT id, password FROM users ORDER BY id').fetchall()
            repeated = import_dump(DUMP)
            self.assertEqual(repeated['imported'], 0)
            self.assertEqual(repeated['credentials'], [])
            self.assertEqual(db.execute('SELECT id, password FROM users ORDER BY id').fetchall(), before)

    def test_conflict_rolls_back_whole_import(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO users VALUES (2, 'Existing', 'Person', 'existing-hash', 2)")
            db.commit()
            with self.assertRaisesRegex(ValueError, 'ID conflict'):
                import_dump(DUMP)
            self.assertEqual(db.execute('SELECT id, firstname FROM users').fetchall(), [(2, 'Existing')])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM courses').fetchone()[0], 0)

    def test_cli_backs_up_database_and_exports_passwords(self):
        result = self.app.test_cli_runner().invoke(args=['import-legacy'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(list(Path(self.temp.name).glob('backups/*.sqlite3'))), 1)
        self.assertEqual(len(list(Path(self.temp.name).glob('legacy-credentials-*.csv'))), 1)
        self.assertIn('Missing original attachments:', result.output)
