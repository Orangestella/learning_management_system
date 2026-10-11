CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    course_id INTEGER,
    deadline TEXT,
    description TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER,
    post_id INTEGER,
    content TEXT,
    date TEXT,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES forum_posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    leader_id INTEGER,
    description TEXT,
    session TEXT,
    FOREIGN KEY (leader_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    enrollment_date TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (student_id, course_id)
);

CREATE TABLE IF NOT EXISTS forum_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poster_id INTEGER,
    forum_id INTEGER,
    content TEXT,
    date TEXT,
    FOREIGN KEY (poster_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);

CREATE TABLE IF NOT EXISTS ins_crs_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ins_id INTEGER,
    crs_id INTEGER,
    FOREIGN KEY (ins_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (crs_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (ins_id, crs_id)
);

CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    name TEXT,
    resource_url TEXT,
    description TEXT,
    upload_date TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER,
    receiver_id INTEGER,
    content TEXT,
    send_time TEXT,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    score INTEGER,
    feedback TEXT,
    student_id INTEGER NOT NULL,
    submission_date TEXT NOT NULL,
    attach_file TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_forum_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    forum_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE,
    UNIQUE (user_id, forum_id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firstname TEXT NOT NULL,
    lastname TEXT NOT NULL,
    password TEXT NOT NULL,
    role_id INTEGER CHECK(role_id IN (0, 1, 2))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, content TEXT NOT NULL, send_date TEXT NOT NULL,
    crs_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    account_id TEXT PRIMARY KEY, failures INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS submissions_assignment ON submissions(assignment_id);
CREATE INDEX IF NOT EXISTS comments_post ON comments(post_id);
CREATE INDEX IF NOT EXISTS notifications_course ON notifications(crs_id);
