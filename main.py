import json
import re
import shutil
import psutil
import markdown as md_lib
import bleach
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import pbkdf2_sha256
from database import get_db, init_db
from auth import create_session_token, get_current_user, require_admin
from config import HOST, PORT

# 允许的 HTML 标签和属性（用于 Markdown 渲染安全过滤）
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd',
    'strong', 'em', 'b', 'i', 'u', 's', 'del', 'ins', 'mark',
    'a', 'img', 'code', 'pre', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'div', 'figure', 'figcaption',
]
ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target', 'rel', 'class'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'class'],
    '*': ['class', 'id', 'style'],
}

def render_markdown(text: str) -> str:
    """将 Markdown 渲染为安全 HTML"""
    if not text:
        return ''
    html = md_lib.markdown(text, extensions=['fenced_code', 'tables', 'codehilite'])
    safe_html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return safe_html

def build_preset_html(preset: dict, show_screenshots: bool = True) -> str:
    """将 Preset 模式的结构化字段拼成 HTML"""
    if not preset:
        return ''
    parts = []
    
    screenshots = preset.get('screenshots', [])
    if show_screenshots and screenshots and isinstance(screenshots, list):
        slides = []
        for s in screenshots:
            if not s.get('url'):
                continue
            url = bleach.clean(s['url'], tags=[], attributes={}, strip=True)
            caption = bleach.clean(s.get('caption', ''), tags=[], attributes={}, strip=True)
            slides.append(
                '<div class="ss-slide">'
                '<img src="' + url + '" alt="' + caption + '" loading="lazy">'
                '</div>'
            )
        if slides:
            imgs_html = ''.join(slides)
            dots_html = ''.join('<span class="ss-dot"></span>' for _ in slides)
            parts.append(
                '<div class="ss-carousel" id="ss-carousel">'
                '<div class="ss-viewport"><div class="ss-track">' + imgs_html + '</div></div>'
                '<button class="ss-arrow ss-prev" type="button">&lsaquo;</button>'
                '<button class="ss-arrow ss-next" type="button">&rsaquo;</button>'
                '<div class="ss-dots">' + dots_html + '</div>'
                '</div>'
            )
    
    overview = preset.get('overview', '').strip()
    if overview:
        parts.append(f'<div class="preset-section"><h2>概述</h2><div class="preset-overview">{render_markdown(overview)}</div></div>')
    
    features = preset.get('features', [])
    if features and isinstance(features, list):
        items = ''.join(f'<li class="feature-item">{render_markdown(f.strip())}</li>' for f in features if f.strip())
        if items:
            parts.append(f'<div class="preset-section"><h2>功能特性</h2><ul class="feature-list">{items}</ul></div>')
    
    architecture = preset.get('architecture', '').strip()
    if architecture:
        parts.append(f'<div class="preset-section"><h2>项目详情</h2><div class="preset-architecture">{render_markdown(architecture)}</div></div>')
    
    return '\n'.join(parts)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Portfolio", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_theme_vars():
    """获取当前激活主题的CSS变量"""
    db = get_db()
    theme = db.execute("SELECT css_vars FROM theme WHERE is_active = 1 LIMIT 1").fetchone()
    db.close()
    return json.loads(theme["css_vars"]) if theme else {}

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
    
    # 记录访问
    db.execute("INSERT INTO site_view (page, ip_address, user_agent) VALUES (?, ?, ?)",
               ("home", request.client.host if request.client else "", request.headers.get("user-agent", "")))
    
    # 获取统计数据
    total_projects = db.execute("SELECT COUNT(*) FROM project").fetchone()[0]
    visible_projects = db.execute("SELECT COUNT(*) FROM project WHERE is_visible = 1").fetchone()[0]
    total_views = db.execute("SELECT SUM(view_count) FROM project").fetchone()[0] or 0
    
    db.commit()
    db.close()
    
    theme_vars = json.loads(theme["css_vars"]) if theme else {}
    return templates.TemplateResponse(request, "index.html", {
        "profile": dict(profile) if profile else {},
        "theme_vars": theme_vars,
        "total_projects": total_projects,
        "visible_projects": visible_projects,
        "total_views": total_views
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
    project = dict(p)
    
    # 根据模式构建详情 HTML
    content_mode = project.get('content_mode', 'preset')
    if content_mode == 'preset':
        try:
            preset = json.loads(project.get('detail_preset') or '{}')
        except (json.JSONDecodeError, TypeError):
            preset = {}
        project['detail_html'] = build_preset_html(preset, show_screenshots=project.get('show_screenshots', 1))
        project['detail_mode'] = 'preset'
    else:
        project['detail_html'] = render_markdown(project.get('detail') or '')
        project['detail_mode'] = 'advanced'
    
    # 检查是否为管理员（用于显示编辑按钮）
    is_admin = get_current_user(request) is not None
    
    # 解析 detail_preset 供 modal 编辑用
    try:
        detail_preset = json.loads(project.get('detail_preset') or '{}')
    except (json.JSONDecodeError, TypeError):
        detail_preset = {}
    
    # 渲染文档 Markdown
    doc_raw = project.get('doc_content') or ''
    doc_html = render_markdown(doc_raw) if doc_raw else ''
    
    # 确定返回链接
    from_param = request.query_params.get("from", "")
    from_admin = from_param == "admin"
    back_url = "/admin/projects" if from_admin else "/"
    
    return templates.TemplateResponse(request, "project_detail.html", {
        "project": project, "theme_vars": theme_vars,
        "is_admin": is_admin,
        "detail_preset": detail_preset,
        "back_url": back_url,
        "from_admin": from_admin,
        "doc_html": doc_html
    })

# --- Auth ---
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/login.html", {"error": None, "theme_vars": theme_vars})

@app.post("/admin/login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM admin_user WHERE username = ?", (username,)).fetchone()
    db.close()
    if not user or not pbkdf2_sha256.verify(password, user["password_hash"]):
        theme_vars = get_theme_vars()
        return templates.TemplateResponse(request, "admin/login.html", {"error": "用户名或密码错误", "theme_vars": theme_vars})
    token = create_session_token(username)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("session", token, httponly=True, max_age=86400, samesite="lax")
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
        "SELECT COUNT(*) as c FROM site_view WHERE page = 'home' AND viewed_at >= datetime('now', 'start of day')"
    ).fetchone()["c"]
    total_views = db.execute("SELECT COUNT(*) as c FROM site_view WHERE page = 'home'").fetchone()["c"]
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
        "SELECT COUNT(*) as c FROM site_view WHERE page = 'home' AND viewed_at >= date('now', 'start of month')"
    ).fetchone()["c"]
    last_month = db.execute(
        "SELECT COUNT(*) as c FROM site_view WHERE page = 'home' AND viewed_at >= date('now', 'start of month', '-1 month') AND viewed_at < date('now', 'start of month')"
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
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "theme_vars": theme_vars,
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
    visible_projects = db.execute(
        "SELECT * FROM project WHERE is_visible = 1 ORDER BY sort_order ASC"
    ).fetchall()
    hidden_projects = db.execute(
        "SELECT * FROM project WHERE is_visible = 0 ORDER BY sort_order ASC"
    ).fetchall()
    db.close()
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/projects.html", {
        "theme_vars": theme_vars,
        "visible_projects": [dict(p) for p in visible_projects],
        "hidden_projects": [dict(p) for p in hidden_projects],
    })

@app.get("/admin/projects/new", response_class=HTMLResponse)
def admin_project_new(request: Request):
    require_admin(request)
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/project_edit.html", {
        "project": None, "error": None, "theme_vars": theme_vars,
        "detail_preset": {}
    })

@app.get("/admin/projects/{pid}/edit", response_class=HTMLResponse)
def admin_project_edit(request: Request, pid: int):
    require_admin(request)
    db = get_db()
    p = db.execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)
    project = dict(p)
    theme_vars = get_theme_vars()
    # 解析 detail_preset JSON
    try:
        detail_preset = json.loads(project.get('detail_preset') or '{}')
    except (json.JSONDecodeError, TypeError):
        detail_preset = {}
    return templates.TemplateResponse(request, "admin/project_edit.html", {
        "project": project, "error": None, "theme_vars": theme_vars,
        "detail_preset": detail_preset
    })

@app.post("/admin/projects/save")
def admin_project_save(
    request: Request,
    pid: int = Form(0), name: str = Form(...), slug: str = Form(...),
    description: str = Form(""), detail: str = Form(""), tech_stack: str = Form(""),
    category: str = Form(""), github_url: str = Form(""), web_url: str = Form(""),
    pages_url: str = Form(""), show_github: int = Form(0), show_web: int = Form(0),
    show_pages: int = Form(0), show_tech: int = Form(0), show_detail: int = Form(0),
    is_visible: int = Form(0), sort_order: int = Form(0),
    content_mode: str = Form("preset"),
    overview: str = Form(""), features: str = Form(""),
    screenshots: str = Form(""), architecture: str = Form(""),
    doc_content: str = Form(""),
    show_screenshots: int = Form(1)):
    require_admin(request)
    
    detail_preset = {}
    if content_mode == 'preset':
        # 功能列表 - 每行一条
        feature_list = [f.strip() for f in features.split('\n') if f.strip()]
        # 截图集 - URL|标题 每行一条
        screenshot_list = []
        for line in screenshots.strip().split('\n'):
            line = line.strip()
            if line:
                parts = line.split('|', 1)
                url = parts[0].strip()
                caption = parts[1].strip() if len(parts) > 1 else ''
                if url:
                    screenshot_list.append({'url': url, 'caption': caption})
        
        detail_preset = {
            'overview': overview,
            'features': feature_list,
            'screenshots': screenshot_list,
            'architecture': architecture
        }
    
    detail_preset_json = json.dumps(detail_preset, ensure_ascii=False)
    
    db = get_db()
    if pid > 0:
        db.execute("""UPDATE project SET name=?, slug=?, description=?, detail=?, tech_stack=?, category=?,
            github_url=?, web_url=?, pages_url=?, show_github=?, show_web=?, show_pages=?, show_tech=?,
            show_detail=?, is_visible=?, sort_order=?, content_mode=?, detail_preset=?, doc_content=?,
            show_screenshots=? WHERE id=?""",
            (name, slug, description, detail, tech_stack, category, github_url, web_url, pages_url,
             show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order,
             content_mode, detail_preset_json, doc_content, show_screenshots, pid))
        saved_slug = slug
    else:
        db.execute("""INSERT INTO project (name, slug, description, detail, tech_stack, category, github_url,
            web_url, pages_url, show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order,
            content_mode, detail_preset, doc_content, show_screenshots)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, slug, description, detail, tech_stack, category, github_url, web_url, pages_url,
             show_github, show_web, show_pages, show_tech, show_detail, is_visible, sort_order,
             content_mode, detail_preset_json, doc_content, show_screenshots))
        saved_slug = slug
    db.commit()
    db.close()
    
    # 支持 return_to 参数：从弹窗保存后回到项目页
    return_to = request.query_params.get('return_to', '')
    if return_to:
        return RedirectResponse(return_to, status_code=303)
    return RedirectResponse("/admin/projects", status_code=303)

@app.post("/admin/projects/{pid}/delete")
def admin_project_delete(request: Request, pid: int):
    require_admin(request)
    db = get_db()
    db.execute("DELETE FROM project WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return RedirectResponse("/admin/projects", status_code=303)

@app.post("/admin/upload-screenshot")
async def admin_upload_screenshot(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    import uuid, os
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        return JSONResponse({"error": "只支持图片文件"}, status_code=400)
    # Generate unique filename
    ext = os.path.splitext(file.filename or '.png')[1] or '.png'
    filename = f"screenshot_{uuid.uuid4().hex[:8]}{ext}"
    save_dir = Path("static/screenshots")
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / filename
    # Save file
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return JSONResponse({"url": f"/static/screenshots/{filename}"})

@app.post("/admin/upload-doc")
async def admin_upload_doc(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    if not file.filename or not file.filename.lower().endswith('.md'):
        return JSONResponse({"error": "只支持 .md 文件"}, status_code=400)
    content = await file.read()
    text = content.decode('utf-8')
    return JSONResponse({"content": text, "filename": file.filename})

@app.post("/admin/view-mode")
async def admin_set_view_mode(request: Request):
    require_admin(request)
    form = await request.form()
    mode = form.get("mode", "card")
    if mode not in ("list", "card"):
        mode = "card"
    db = get_db()
    db.execute("INSERT OR REPLACE INTO site_setting (key, value) VALUES ('project_view_mode', ?)", (mode,))
    db.commit()
    db.close()
    return RedirectResponse("/admin/projects", status_code=303)

@app.post("/admin/projects/{pid}/toggle")
async def admin_project_toggle(request: Request, pid: int):
    require_admin(request)
    data = await request.json()
    new_visible = data.get("is_visible", 0)
    db = get_db()
    # 获取目标区域的最大 sort_order
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) as m FROM project WHERE is_visible = ?", (new_visible,)
    ).fetchone()["m"]
    db.execute("UPDATE project SET is_visible = ?, sort_order = ? WHERE id = ?", (new_visible, max_order + 1, pid))
    db.commit()
    db.close()
    return {"ok": True}

@app.post("/admin/projects/reorder")
async def admin_projects_reorder(request: Request):
    require_admin(request)
    data = await request.json()
    visible_ids = data.get("visible", [])
    hidden_ids = data.get("hidden", [])
    db = get_db()
    # 更新显示项目的顺序
    for i, pid in enumerate(visible_ids):
        db.execute("UPDATE project SET sort_order = ?, is_visible = 1 WHERE id = ?", (i + 1, pid))
    # 更新隐藏项目的顺序
    for i, pid in enumerate(hidden_ids):
        db.execute("UPDATE project SET sort_order = ?, is_visible = 0 WHERE id = ?", (i + 1, pid))
    db.commit()
    db.close()
    return {"ok": True}

@app.get("/api/admin/projects/{pid}")
def api_admin_project(request: Request, pid: int):
    require_admin(request)
    db = get_db()
    p = db.execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    db.close()
    if not p:
        raise HTTPException(404)
    return dict(p)

@app.get("/admin/profile", response_class=HTMLResponse)
def admin_profile(request: Request):
    return RedirectResponse("/admin/settings", status_code=301)

@app.get("/admin/themes", response_class=HTMLResponse)
def admin_themes(request: Request):
    return RedirectResponse("/admin/settings", status_code=301)

@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings(request: Request):
    require_admin(request)
    db = get_db()
    profile = db.execute("SELECT * FROM profile LIMIT 1").fetchone()
    themes = db.execute("SELECT * FROM theme ORDER BY id").fetchall()
    db.close()
    result = []
    for t in themes:
        d = dict(t)
        try:
            d["css_vars_parsed"] = json.loads(d["css_vars"])
        except:
            d["css_vars_parsed"] = {}
        result.append(d)
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/settings.html", {
        "theme_vars": theme_vars,
        "profile": dict(profile) if profile else {},
        "themes": result
    })

@app.post("/admin/profile/save")
async def admin_profile_save(request: Request, name: str = Form(""), title: str = Form(""), bio: str = Form(""),
                        github_url: str = Form(""), email: str = Form(""),
                        location: str = Form("")):
    require_admin(request)
    
    db = get_db()
    existing = db.execute("SELECT id FROM profile LIMIT 1").fetchone()
    if existing:
        db.execute("UPDATE profile SET name=?, title=?, bio=?, github_url=?, email=?, location=? WHERE id=?",
                   (name, title, bio, github_url, email, location, existing["id"]))
    else:
        db.execute("INSERT INTO profile (name, title, bio, github_url, email, location) VALUES (?,?,?,?,?,?)",
                   (name, title, bio, github_url, email, location))
    db.commit()
    db.close()
    return RedirectResponse("/admin/settings?saved=1", status_code=303)

@app.post("/admin/avatar/upload")
async def admin_avatar_upload(request: Request, avatar_file: UploadFile = File(None), avatar_x: int = Form(50), avatar_y: int = Form(50)):
    require_admin(request)
    if not avatar_file or not avatar_file.filename:
        return JSONResponse({"ok": False, "error": "请选择图片文件"}, status_code=400)
    
    import uuid
    ext = Path(avatar_file.filename).suffix or ".jpg"
    filename = f"avatar_{uuid.uuid4().hex[:8]}{ext}"
    upload_dir = Path("static/uploads/avatars")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    
    with open(file_path, "wb") as f:
        content = await avatar_file.read()
        f.write(content)
    
    final_avatar_url = f"/static/uploads/avatars/{filename}"
    avatar_position = f"{avatar_x},{avatar_y}"
    
    db = get_db()
    # 保存到历史记录
    db.execute("INSERT INTO avatar_history (avatar_url) VALUES (?)", (final_avatar_url,))
    # 只保留最近3个历史头像
    db.execute("DELETE FROM avatar_history WHERE id NOT IN (SELECT id FROM avatar_history ORDER BY created_at DESC LIMIT 3)")
    # 更新 profile
    db.execute("UPDATE profile SET avatar_url=?, avatar_position=?", (final_avatar_url, avatar_position))
    db.commit()
    db.close()
    return JSONResponse({"ok": True, "avatar_url": final_avatar_url, "avatar_position": avatar_position})

@app.get("/api/admin/avatars")
def api_admin_avatars(request: Request):
    require_admin(request)
    db = get_db()
    avatars = db.execute("SELECT * FROM avatar_history ORDER BY created_at DESC LIMIT 3").fetchall()
    db.close()
    return [dict(a) for a in avatars]

@app.post("/admin/themes/activate")
def admin_theme_activate(request: Request, tid: int = Form(...)):
    require_admin(request)
    db = get_db()
    # 先将所有主题设为非激活
    db.execute("UPDATE theme SET is_active = 0")
    # 再激活指定主题
    db.execute("UPDATE theme SET is_active = 1 WHERE id = ?", (tid,))
    db.commit()
    # 获取新激活主题的 CSS 变量
    theme = db.execute("SELECT css_vars FROM theme WHERE id = ?", (tid,)).fetchone()
    db.close()
    css_vars = {}
    if theme:
        try:
            css_vars = json.loads(theme["css_vars"])
        except:
            pass
    return JSONResponse({"ok": True, "css_vars": css_vars})

@app.post("/admin/themes/save")
def admin_theme_save(request: Request, tid: int = Form(0), name: str = Form(""), css_vars: str = Form(""),
                      is_custom: int = Form(0)):
    require_admin(request)
    db = get_db()
    if tid > 0:
        # 编辑已有主题
        db.execute("UPDATE theme SET name=?, css_vars=? WHERE id=?", (name, css_vars, tid))
    elif name and css_vars:
        # 新建自定义主题
        db.execute("INSERT INTO theme (name, css_vars, is_custom, desc) VALUES (?, ?, 1, '自定义主题')", (name, css_vars))
    db.commit()
    db.close()
    return RedirectResponse("/admin/settings?saved=1#theme", status_code=303)

@app.post("/admin/themes/{tid}/delete")
def admin_theme_delete(request: Request, tid: int):
    require_admin(request)
    db = get_db()
    # 检查是否为当前激活主题
    theme = db.execute("SELECT is_active FROM theme WHERE id = ?", (tid,)).fetchone()
    if theme and theme["is_active"]:
        # 如果删除的是激活主题，激活"暖日"作为默认
        db.execute("UPDATE theme SET is_active = 1 WHERE name = '暖日'")
    db.execute("DELETE FROM theme WHERE id = ?", (tid,))
    db.commit()
    db.close()
    return RedirectResponse("/admin/settings?saved=1#theme", status_code=303)

@app.get("/admin/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request):
    require_admin(request)
    db = get_db()
    
    # 汇总数据
    total_views = db.execute("SELECT SUM(view_count) FROM project").fetchone()[0] or 0
    total_projects = db.execute("SELECT COUNT(*) FROM project WHERE is_visible = 1").fetchone()[0] or 0
    has_data = db.execute("SELECT COUNT(*) FROM site_view").fetchone()[0] or 0
    
    # 每日访问数据（用于热力图）
    daily_data = db.execute(
        "SELECT DATE(viewed_at) as day, COUNT(*) as count "
        "FROM site_view GROUP BY day ORDER BY day ASC"
    ).fetchall() if has_data else []
    
    # 页面访问分布（排除 home 页面）
    page_distribution = db.execute(
        "SELECT page, COUNT(*) as count FROM site_view "
        "WHERE page != 'home' GROUP BY page ORDER BY count DESC LIMIT 10"
    ).fetchall() if has_data else []
    
    # 周分布
    dow_data = []
    if has_data:
        raw_dow = {
            r["dow"]: r["count"]
            for r in db.execute(
                "SELECT CAST(strftime('%w', viewed_at) AS INTEGER) as dow, COUNT(*) as count "
                "FROM site_view GROUP BY dow ORDER BY dow ASC"
            ).fetchall()
        }
        dow_data = [{"dow": d, "count": raw_dow.get(d, 0)} for d in range(7)]
    
    # 项目访问排名（全量）
    project_views = db.execute(
        "SELECT name, slug, view_count FROM project ORDER BY view_count DESC"
    ).fetchall()
    
    db.close()
    theme_vars = get_theme_vars()
    return templates.TemplateResponse(request, "admin/analytics.html", {
        "theme_vars": theme_vars,
        "total_views": total_views,
        "total_projects": total_projects,
        "has_data": has_data,
        "daily_data": [dict(d) for d in daily_data],
        "page_distribution": [dict(d) for d in page_distribution],
        "dow_data": [dict(d) for d in dow_data],
        "project_views": [dict(p) for p in project_views],
    })

@app.get("/api/admin/analytics/heatmap")
def analytics_heatmap_api(request: Request, offset: int = 0):
    """返回 2 个月窗口的热力图数据，offset 每 +1 往前推 2 个月"""
    require_admin(request)
    db = get_db()

    today = datetime.today().date()
    end_date = today - timedelta(days=offset * 365)
    start_date = end_date - timedelta(days=365)

    daily = db.execute(
        "SELECT DATE(viewed_at) as day, COUNT(*) as count "
        "FROM site_view WHERE DATE(viewed_at) BETWEEN ? AND ? "
        "GROUP BY day ORDER BY day ASC",
        (start_date.isoformat(), end_date.isoformat())
    ).fetchall() if db.execute("SELECT COUNT(*) FROM site_view").fetchone()[0] else []

    active = [d for d in daily if d["count"] > 0]
    total_active = len(active)
    total_days = (end_date - start_date).days
    avg = round(sum(d["count"] for d in active) / total_active, 1) if active else 0
    highest = max(d["count"] for d in active) if active else 0

    db.close()
    return {
        "daily_data": [dict(d) for d in daily],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_days": total_days,
        "active_days": total_active,
        "avg": avg,
        "highest": highest,
        "can_forward": offset > 0,
    }

@app.get("/admin/analytics/export")
def admin_analytics_export(request: Request):
    require_admin(request)
    db = get_db()
    rows = db.execute(
        "SELECT strftime('%Y-%m-%d %H:%M:%S', viewed_at) as time, page, ip_address "
        "FROM site_view ORDER BY viewed_at DESC"
    ).fetchall()
    db.close()
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["时间", "页面", "IP地址"])
    for r in rows:
        w.writerow([r["time"], r["page"], r["ip_address"]])
    from fastapi.responses import Response
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics_export.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
