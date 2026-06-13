# Portfolio

A personal portfolio/showcase website built with FastAPI, SQLite, and Jinja2.

## Features

- **Public Frontend**: Dark-themed project showcase with smooth animations
- **Admin Panel**: Full CRUD for projects, profile management, theme customization, analytics
- **API**: RESTful endpoints for projects, profile, and themes
- **Themes**: CSS variable-based theming system
- **Analytics**: Page view tracking per project

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

Visit http://localhost:8000 for the public site.
Admin panel at http://localhost:8000/admin/login

**Default credentials:** admin / admin123

## Tech Stack

- **Backend**: FastAPI + SQLite + Jinja2
- **Frontend**: Single-page HTML with CSS custom properties
- **Auth**: Session-based with password hashing (passlib)

## Configuration

Environment variables:
- `SECRET_KEY` - Session signing key
- `ADMIN_USERNAME` - Default admin username
- `ADMIN_PASSWORD` - Default admin password
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List visible projects |
| GET | `/api/projects/:slug` | Get project detail |
| POST | `/api/view/:slug` | Record a page view |
| GET | `/api/profile` | Get profile info |
| GET | `/api/theme` | Get active theme CSS vars |
