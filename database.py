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


# 预设主题
PRESET_THEMES = [
    {
        "name": "暖日",
        "desc": "温暖的米白色调，适合日常使用",
        "css_vars": """{
    "--bg-primary": "#f5f0e8",
    "--bg-secondary": "#faf7f2",
    "--bg-card": "#ffffff",
    "--text-primary": "#2c2520",
    "--text-secondary": "#8a7e72",
    "--accent": "#c47d3c",
    "--accent-hover": "#b06c2e",
    "--border": "#e0d8cc",
    "--shadow": "0 2px 12px rgba(44,37,32,0.06)"
}""",
    },
    {
        "name": "深夜",
        "desc": "深色护眼主题，适合夜间浏览",
        "css_vars": """{
    "--bg-primary": "#0a0a0f",
    "--bg-secondary": "#12121a",
    "--bg-card": "#16161f",
    "--text-primary": "#e4e4e7",
    "--text-secondary": "#a1a1aa",
    "--accent": "#4f6eff",
    "--accent-hover": "#3d5bd9",
    "--border": "#27272a",
    "--shadow": "0 4px 24px rgba(0,0,0,0.4)"
}""",
    },
    {
        "name": "晨雾",
        "desc": "清爽的蓝灰色调，简约干净",
        "css_vars": """{
    "--bg-primary": "#f0f2f5",
    "--bg-secondary": "#f8f9fb",
    "--bg-card": "#ffffff",
    "--text-primary": "#1e293b",
    "--text-secondary": "#64748b",
    "--accent": "#3b82f6",
    "--accent-hover": "#2563eb",
    "--border": "#e2e8f0",
    "--shadow": "0 2px 12px rgba(30,41,59,0.06)"
}""",
    },
    {
        "name": "落日",
        "desc": "暖橙色调，充满活力",
        "css_vars": """{
    "--bg-primary": "#faf5f0",
    "--bg-secondary": "#fef9f4",
    "--bg-card": "#ffffff",
    "--text-primary": "#1c1917",
    "--text-secondary": "#78716c",
    "--accent": "#ea580c",
    "--accent-hover": "#c2410c",
    "--border": "#e7e0d8",
    "--shadow": "0 2px 12px rgba(28,25,23,0.06)"
}""",
    },
    {
        "name": "森林",
        "desc": "自然绿色调，清新舒适",
        "css_vars": """{
    "--bg-primary": "#f0f5f0",
    "--bg-secondary": "#f5faf5",
    "--bg-card": "#ffffff",
    "--text-primary": "#1a2e1a",
    "--text-secondary": "#5c7a5c",
    "--accent": "#16a34a",
    "--accent-hover": "#15803d",
    "--border": "#d4e4d4",
    "--shadow": "0 2px 12px rgba(26,46,26,0.06)"
}""",
    },
]


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
            is_active INTEGER DEFAULT 0,
            is_custom INTEGER DEFAULT 0,
            desc TEXT DEFAULT ''
        );
    """)

    # 添加 desc 和 is_custom 列（如果不存在）
    try:
        cursor.execute("ALTER TABLE theme ADD COLUMN is_custom INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE theme ADD COLUMN desc TEXT DEFAULT ''")
    except:
        pass

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
             "", "https://github.com/yourusername", "hello@example.com", "San Francisco, CA"))

    # Seed 预设主题
    active_theme = cursor.execute("SELECT id FROM theme WHERE is_active = 1").fetchone()
    for pt in PRESET_THEMES:
        existing = cursor.execute("SELECT id FROM theme WHERE name = ?", (pt["name"],)).fetchone()
        if not existing:
            cursor.execute(
                "INSERT INTO theme (name, css_vars, is_active, is_custom, desc) VALUES (?, ?, 0, 0, ?)",
                (pt["name"], pt["css_vars"], pt["desc"])
            )

    # 如果没有激活的主题，激活"暖日"
    if not active_theme:
        cursor.execute("UPDATE theme SET is_active = 1 WHERE name = '暖日'")

    conn.commit()
    conn.close()
