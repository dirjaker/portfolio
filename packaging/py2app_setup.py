"""
py2app setup script for building a macOS .app bundle.

Usage:
    python packaging/py2app_setup.py py2app
"""

from setuptools import setup

APP = ['main.py']
DATA_FILES = [
    ('templates', [
        'templates/base.html',
        'templates/index.html',
        'templates/project_detail.html',
        'templates/admin/login.html',
        'templates/admin/dashboard.html',
        'templates/admin/projects.html',
        'templates/admin/project_edit.html',
        'templates/admin/profile.html',
        'templates/admin/themes.html',
        'templates/admin/analytics.html',
    ]),
    ('static/css', ['static/css/style.css']),
    ('', ['requirements.txt']),
]

OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'Portfolio',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.portfolio.app',
        'LSBackgroundOnly': False,
    },
    'packages': ['fastapi', 'uvicorn', 'jinja2', 'passlib', 'itsdangerous', 'starlette'],
}

setup(
    name='Portfolio',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
