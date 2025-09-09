import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'app.db')


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def connect():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                role TEXT NOT NULL DEFAULT 'Admin',
                enabled INTEGER NOT NULL DEFAULT 1,
                password_hash TEXT NOT NULL,
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                obj TEXT NOT NULL,
                content TEXT NOT NULL,
                level TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                obj TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                k TEXT PRIMARY KEY,
                v TEXT
            );
            """
        )


def user_get_by_username(username: str):
    with get_db() as db:
        cur = db.execute("SELECT * FROM users WHERE username=?", (username,))
        return cur.fetchone()


def user_list():
    with get_db() as db:
        cur = db.execute("SELECT username, email, role, enabled, last_login FROM users ORDER BY username")
        return cur.fetchall()


def user_insert(username: str, email: str, role: str, enabled: int, password_hash: str):
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO users(username, email, role, enabled, password_hash) VALUES(?,?,?,?,?)",
            (username, email, role, enabled, password_hash),
        )


def user_update_last_login(username: str, ts: str):
    with get_db() as db:
        db.execute("UPDATE users SET last_login=? WHERE username=?", (ts, username))


def audit_append(username: str, action: str, obj: str = None, ts: str = None):
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_logs(ts, username, action, obj) VALUES(datetime('now','localtime'), ?, ?, ?)",
            (username, action, obj),
        )


def seed_admin_if_missing(password_hash: str):
    # default admin
    user_insert("admin", "admin@local", "Admin", 1, password_hash)

