# Portfolio

A personal portfolio/showcase website built with FastAPI, SQLite, and Jinja2.

## Features

- **Public Frontend**: Dark-themed project showcase with smooth animations
- **Admin Panel**: Full CRUD for projects, profile management, theme customization, analytics
- **API**: RESTful endpoints for projects, profile, and themes
- **Themes**: CSS variable-based theming system
- **Analytics**: Page view tracking per project
- **Responsive**: Works on desktop and mobile devices

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

Environment variables (create a `.env` file):

```env
SECRET_KEY=your-random-secret-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
HOST=0.0.0.0
PORT=8000
DATABASE_URL=portfolio.db
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List visible projects |
| GET | `/api/projects/:slug` | Get project detail |
| POST | `/api/view/:slug` | Record a page view |
| GET | `/api/profile` | Get profile info |
| GET | `/api/theme` | Get active theme CSS vars |

## Project Structure

```
portfolio/
├── main.py              # FastAPI application
├── database.py          # Database operations & schema
├── auth.py              # Authentication logic
├── config.py            # Configuration (env vars)
├── requirements.txt     # Python dependencies
├── templates/           # Jinja2 templates
│   ├── index.html       # Public homepage
│   ├── project_detail.html
│   └── admin/           # Admin panel templates
├── static/              # Static assets (CSS, JS, images)
└── packaging/           # Packaging configuration
```

## Deployment

### Local Development

```bash
python main.py
```

### Production (with uvicorn)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker (optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Customization

### Changing Theme

1. Login to admin panel
2. Go to Themes
3. Edit CSS variables (colors, shadows, borders)

### Adding Projects

1. Login to admin panel
2. Go to Projects
3. Click "Add Project"
4. Fill in project details

### Updating Profile

1. Login to admin panel
2. Go to Profile
3. Update your information

## Security Notes

- Change the default admin password immediately
- Set a strong `SECRET_KEY` in production
- Use HTTPS in production
- Consider adding rate limiting for API endpoints

## License

MIT License

## Author

Your Name - [GitHub](https://github.com/yourusername)
