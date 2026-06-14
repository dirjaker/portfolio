import json
import shutil
import psutil
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import pbkdf2_sha256
from database import get_db, init_db
from auth import create_session_token, get_current_user, require_admin
from config import HOST, PORT

app = FastAPI(title="Portfolio")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def startup():
    init_db()

# --- Public API ---
@app.get("/api/projects")
def api_projects():
    db = get_db()
    projects = db.execute(
        "SELECT id, name, slug, description, tech_stack, category, github_url, web_url, pages_url, "
        "show_github, show_web, show_pages, show_tech, view_count "
        "FROM project WHERE is_visible = 1 ORDER BY sort_order ASC, created_at DESC"
    ).fetchall()
    db.close()
    return [dict(p) for p in projects]

@app.get("/api/projects/{slug}")
def api_project(slug: str):
    db = get_db()
    p = db.execute("SELECT * FROM project WHERE slug = ? AND is_visible = 1", (slug,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404, "Not found")
    return dict(p)

@app.post("/api/view/{slug}")
def api_record_view(slug: str, request: Request):
    db = get_db()
    p = db.execute("SELECT id FROM project WHERE slug = ?", (slug,)).fetchone()
    if not p:
        db.close()
        raise HTTPException(404)
    db.execute("UPDATE project SET view_count = view_count + 1 WHERE id = ?", (p["id"],))
    db.execute("INSERT INTO site_view (page, ip_address, user_agent) VALUES (?, ?, ?)",
               (slug, request.client.host if request.client else "", request.headers.get("user-agent", "")))
    db.commit()
    db.close()
    return {"ok": True}

@app.get("/api/profile")
def api_profile():
    db = get_db()
    p = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    db.close()
    return dict(p) if p else {}

@app.get("/api/theme")
def api_theme():
    db = get_db()
    t = db.execute("SELECT * FROM theme WHERE is_active = 1 LIMIT 1").fetchone()
    db.close()
    if t:
        return {"name": t["name"], "css_vars": json.loads(t["css_vars"])}
    return {}

# --- Public Pages ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    db = get_db()
    profile = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    theme = db.execute("SELECT * FROM theme WHERE is_active = 1 LIMIT 1").fetchone()
    db.execute("INSERT INTO site_view (page, ip_address, user_agent) VALUES (?, ?, ?)",
               ("home", request.client.host if request.client else "", request.headers.get("user-agent", "")))
    db.commit()
    db.close()
    theme_vars = json.loads(theme["css_vars"]) if theme else {}
    return templates.TemplateResponse(request, "index.html", {
        "profile": dict(profile) if profile else {}, "theme_vars": theme_vars
    })

@app.get("/project/{slug}", response_class=HTMLResponse)
def project_detail(request: Request, slug: str):
    db = get_db()
    p = db.execute("SELECT * FROM project WHERE slug = ?", (slug,)).fetchone()
    theme = db.execute("SELECT css_vars FROM theme WHERE is_active = 1").fetchone()
    db.close()
    if not p:
        raise HTTPException(404)
    theme_vars = json.loads(theme["css_vars"]) if theme else {}
    return templates.TemplateResponse(request, "project_detail.html", {"project": dict(p), "theme_vars": theme_vars})

# --- Auth ---
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})

@app.post("/admin/login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM admin_user WHERE username = ?", (username,)).fetchone()
    db.close()
    if not user or not pbkdf2_sha256.verify(password, user["password_hash"]):
        return templates.TemplateResponse(request, "admin/login.html", {"error": "Invalid credentials"})
    token = create_session_token(username)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("session", token, httponly=True, max_age=86400)
    return response

@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session")
    return response

# --- Admin Pages ---
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    require_admin(request)
    db = get_db()
    total_projects = db.execute("SELECT COUNT(*) as c FROM project").fetchone()["c"]
    visible_projects = db.execute("SELECT COUNT(*) as c FROM project WHERE is_visible = 1").fetchone()["c"]
    today_views = db.execute(
        "SELECT COUNT(*) as c FROM site_view WHERE DATE(viewed_at) = DATE('now')"
    ).fetchone()["c"]
    total_views = db.execute("SELECT COUNT(*) as c FROM site_view").fetchone()["c"]
    top_projects = db.execute(
        "SELECT name, slug, view_count FROM project WHERE view_count > 0 ORDER BY view_count DESC LIMIT 5"
    ).fetchall()
    recent_home = db.execute(
        "SELECT ip_address, viewed_at FROM site_view WHERE page = 'home' ORDER BY viewed_at DESC LIMIT 10"
    ).fetchall()
    daily_7 = db.execute(
        "SELECT DATE(viewed_at) as day, COUNT(*) as count FROM site_view "
        "WHERE viewed_at >= datetime('now', '-7 days') GROUP BY DATE(viewed_at) ORDER BY day"
    ).fetchall()
    # 项目分类统计
    categories = db.execute(
        "SELECT COALESCE(category, '未分类') as cat, COUNT(*) as count FROM project GROUP BY category ORDER BY count DESC"
    ).fetchall()
    # 本月 vs 上月
    this_month = db.execute(
        "SELECT COUNT(*) as c FROM site_view WHERE viewed_at >= date('now', 'start of month')"
    ).fetchone()["c"]
    last_month = db.execute(
        "SELECT COUNT(*) as c FROM site_view WHERE viewed_at >= date('now', 'start of month', '-1 month') AND viewed_at < date('now', 'start of month')"
    ).fetchone()["c"]
    db.close()
    # 服务器状态
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    server_stats = {
        "cpu": round(cpu_percent, 1),
        "mem_used": round(mem.used / (1024**3), 1),
        "mem_total": round(mem.total / (1024**3), 1),
        "mem_percent": mem.percent,
        "disk_used": round(disk.used / (1024**3), 1),
        "disk_total": round(disk.total / (1024**3), 1),
        "disk_percent": round(disk.used / disk.total * 100, 1),
    }
    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "total_projects": total_projects,
        "visible_projects": visible_projects,
        "today_views": today_views,
        "total_views": total_views,
        "top_projects": [dict(p) for p in top_projects],
        "recent_home": [dict(v) for v in recent_home],
        "daily_7": [dict(d) for d in daily_7],
        "categories": [dict(c) for c in categories],
        "this_month": this_month,
        "last_month": last_month,
        "server_stats": server_stats,
    })

@app.get("/api/admin/views")
def api_admin_views(request: Request, page_num: int = Query(1), page_size: int = Query(20),
                    ip_filter: str = Query(""), date_from: str = Query(""), date_to: str = Query("")):
    require_admin(request)
    db = get_db()
    where = ["1=1"]
    params = []
    if ip_filter:
        where.append("sv.ip_address LIKE ?")
        params.append(f"%{ip_filter}%")
    if date_from:
        where.append("DATE(sv.viewed_at) >= ?")
        params.append(date_from)
    if date_to:
        where.append("DATE(sv.viewed_at) <= ?")
        params.append(date_to)
    where_sql = " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) as c FROM site_view sv WHERE {where_sql}", params).fetchone()["c"]
    offset = (page_num - 1) * page_size
    rows = db.execute(
        f"SELECT sv.ip_address, sv.viewed_at, sv.page, p.name as project_name FROM site_view sv "
        f"LEFT JOIN project p ON sv.page = p.slug WHERE {where_sql} "
        f"ORDER BY sv.viewed_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    db.close()
    return {"total": total, "page": page_num, "pages": (total + page_size - 1) // page_size, "rows": [dict(r) for r in rows]}

@app.get("/admin/projects", response_class=HTMLResponse)
def admin_projects(request: Request):
    require_admin(request)
    db = get_db()
    projects = db.execute("SELECT * FROM project ORDER BY sort_order ASC, created_at DESC").fetchall()
    db.close()
    return templates.TemplateResponse(request, "admin/projects.html", {
        "projects": [dict(p) for p in projects]
    })

@app.get("/admin/projects/new", response_class=HTMLResponse)
def admin_project_new(request: Request):
    require_admin(request)
    return templates.TemplateResponse(request, "admin/project_edit.html", {"project": None, "error": None})

@app.get("/admin/projects/{pid}/edit", response_class=HTMLResponse)
def admin_project_edit(request: Request, pid: int):
    require_admin(request)
    db = get_db()
    p = db.execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "admin/project_edit.html", {"project": dict(p), "error": None})

@app.post("/admin/projects/save")
def admin_project_save(request: Request, pid: int = Form(0), name: str = Form(...), slug: str = Form(...),
                        description: str = Form(""), detail: str = Form(""), tech_stack: str = Form(""),
                        category: str = Form(""), github_url: str = Form(""), web_url: str = Form(""),
                        pages_url: str = Form(""), show_github: int = Form(0), show_web: int = Form(0),
                        show_pages: int = Form(0), show_tech: int = Form(0), show_detail: int = Form(0),
                        is_visible: int = Form(0), sort_order: int = Form(0)):
    require_admin(request)
    db = get_db()
    if pid > 0:
        db.execute("""UPDATE project SET name=?, slug=?, description=?, detail=?, tech_stack=?, category=?,
            github_url=?, web_url=?, pages_url=?, show_github=?, show_web=?, show_pages=?, show_tech=?,
            show_detail=?, is_visible=?, sort_order=? WHERE id=?""",
            (name, slug, description, detail, tech_stack, category, github_url, web_url, pages_url,
             show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order, pid))
    else:
        db.execute("""INSERT INTO project (name, slug, description, detail, tech_stack, category, github_url,
            web_url, pages_url, show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, slug, description, detail, tech_stack, category, github_url, web_url, pages_url,
             show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order))
    db.commit()
    db.close()
    return RedirectResponse("/admin/projects", status_code=303)

@app.post("/admin/projects/{pid}/delete")
def admin_project_delete(request: Request, pid: int):
    require_admin(request)
    db = get_db()
    db.execute("DELETE FROM project WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return RedirectResponse("/admin/projects", status_code=303)

@app.get("/admin/profile", response_class=HTMLResponse)
def admin_profile(request: Request):
    require_admin(request)
    db = get_db()
    profile = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    db.close()
    return templates.TemplateResponse(request, "admin/profile.html", {"profile": dict(profile) if profile else {}})

@app.post("/admin/profile/save")
def admin_profile_save(request: Request, name: str = Form(""), title: str = Form(""), bio: str = Form(""),
                        avatar_url: str = Form(""), github_url: str = Form(""), email: str = Form(""),
                        location: str = Form("")):
    require_admin(request)
    db = get_db()
    existing = db.execute("SELECT id FROM profile LIMIT 1").fetchone()
    if existing:
        db.execute("UPDATE profile SET name=?, title=?, bio=?, avatar_url=?, github_url=?, email=?, location=? WHERE id=?",
                   (name, title, bio, avatar_url, github_url, email, location, existing["id"]))
    else:
        db.execute("INSERT INTO profile (name, title, bio, avatar_url, github_url, email, location) VALUES (?,?,?,?,?,?,?)",
                   (name, title, bio, avatar_url, github_url, email, location))
    db.commit()
    db.close()
    return RedirectResponse("/admin/profile", status_code=303)

@app.get("/admin/themes", response_class=HTMLResponse)
def admin_themes(request: Request):
    require_admin(request)
    db = get_db()
    themes = db.execute("SELECT * FROM theme ORDER BY is_active DESC, is_custom ASC, id").fetchall()
    db.close()
    result = []
    for t in themes:
        d = dict(t)
        try:
            d["css_vars_parsed"] = json.loads(d["css_vars"])
        except:
            d["css_vars_parsed"] = {}
        result.append(d)
    return templates.TemplateResponse(request, "admin/themes.html", {"themes": result})

@app.post("/admin/themes/save")
def admin_theme_save(request: Request, tid: int = Form(0), name: str = Form(""), css_vars: str = Form(""),
                      is_active: int = Form(0), is_custom: int = Form(0)):
    require_admin(request)
    db = get_db()
    if is_active and tid > 0:
        # 只是激活预设主题，不需要更新 css_vars
        db.execute("UPDATE theme SET is_active = 0")
        db.execute("UPDATE theme SET is_active = 1 WHERE id = ?", (tid,))
    elif tid > 0:
        # 编辑已有主题
        db.execute("UPDATE theme SET name=?, css_vars=? WHERE id=?", (name, css_vars, tid))
    elif name and css_vars:
        # 新建自定义主题
        db.execute("INSERT INTO theme (name, css_vars, is_custom, desc) VALUES (?, ?, 1, '自定义主题')", (name, css_vars))
    db.commit()
    db.close()
    return RedirectResponse("/admin/themes", status_code=303)

@app.post("/admin/themes/{tid}/delete")
def admin_theme_delete(request: Request, tid: int):
    require_admin(request)
    db = get_db()
    db.execute("DELETE FROM theme WHERE id = ?", (tid,))
    db.commit()
    db.close()
    return RedirectResponse("/admin/themes", status_code=303)

@app.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request):
    require_admin(request)
    db = get_db()
    projects = db.execute("SELECT name, slug, view_count FROM project ORDER BY view_count DESC").fetchall()
    daily_views = db.execute(
        "SELECT DATE(viewed_at) as day, COUNT(*) as count FROM site_view "
        "GROUP BY DATE(viewed_at) ORDER BY day DESC LIMIT 30"
    ).fetchall()
    db.close()
    return templates.TemplateResponse(request, "admin/analytics.html", {
        "projects": [dict(p) for p in projects],
        "daily_views": [dict(d) for d in daily_views]
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
