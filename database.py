import sqlite3
from datetime import datetime
from config import DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD
from passlib.hash import pbkdf2_sha256


def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS admin_user (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            name TEXT,
            title TEXT,
            bio TEXT,
            avatar_url TEXT,
            github_url TEXT,
            email TEXT,
            location TEXT
        );

        CREATE TABLE IF NOT EXISTS project (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            detail TEXT,
            tech_stack TEXT,
            category TEXT,
            github_url TEXT,
            web_url TEXT,
            pages_url TEXT,
            show_github INTEGER DEFAULT 1,
            show_web INTEGER DEFAULT 1,
            show_pages INTEGER DEFAULT 1,
            show_tech INTEGER DEFAULT 1,
            show_detail INTEGER DEFAULT 1,
            is_visible INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS site_view (
            id INTEGER PRIMARY KEY,
            page TEXT,
            ip_address TEXT,
            user_agent TEXT,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS theme (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            css_vars TEXT NOT NULL,
            is_active INTEGER DEFAULT 0
        );
    """)

    # Seed admin user
    existing = cursor.execute("SELECT id FROM admin_user WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
    if not existing:
        pw_hash = pbkdf2_sha256.hash(ADMIN_PASSWORD)
        cursor.execute("INSERT INTO admin_user (username, password_hash) VALUES (?, ?)", (ADMIN_USERNAME, pw_hash))

    # Seed profile
    existing = cursor.execute("SELECT id FROM profile").fetchone()
    if not existing:
        cursor.execute("""INSERT INTO profile (name, title, bio, avatar_url, github_url, email, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("Your Name", "Software Engineer",
             "Building things for the web. Focused on clean code, thoughtful design, and shipping products that matter.",
             "", "https://github.com/dirjaker", "hello@example.com", "San Francisco, CA"))

    # Seed default theme
    existing = cursor.execute("SELECT id FROM theme WHERE is_active = 1").fetchone()
    if not existing:
        default_vars = """{
    "--bg-primary": "#0a0a0f",
    "--bg-secondary": "#12121a",
    "--bg-card": "#16161f",
    "--text-primary": "#e4e4e7",
    "--text-secondary": "#a1a1aa",
    "--accent": "#4f8eff",
    "--accent-hover": "#3b7aed",
    "--border": "#27272a",
    "--shadow": "0 4px 24px rgba(0,0,0,0.4)"
}"""
        cursor.execute("INSERT OR IGNORE INTO theme (name, css_vars, is_active) VALUES (?, ?, 1)", ("Dark", default_vars))

    conn.commit()
    conn.close()
