import os

DATABASE_URL = os.getenv("DATABASE_URL", "portfolio.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "10000"))
