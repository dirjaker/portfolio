# 开发指南

> 本文档为 Portfolio 项目的开发环境搭建、代码结构和开发规范说明。

---

## 📋 环境要求

| 工具 | 版本要求 |
|------|----------|
| Python | >= 3.11（推荐 3.12） |
| pip | 最新版 |
| Conda（可选） | 最新版 |
| Git | 任意版本 |

## 🚀 开发环境搭建

### 1. 克隆项目

```bash
git clone https://github.com/dirjaker/portfolio.git
cd portfolio
```

### 2. 创建虚拟环境

```bash
# 方式一：Conda
conda create -n portfolio python=3.12 -y
conda activate portfolio

# 方式二：venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，按需修改以下配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | 会话签名密钥 | `dev-secret-change-in-production` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `10000` |
| `DATABASE_URL` | SQLite 数据库路径 | `portfolio.db` |

> ⚠️ 生产环境必须修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`！

### 5. 启动开发服务器

```bash
python main.py
```

服务启动后访问：
- 前台首页：http://localhost:10000
- 管理后台：http://localhost:10000/admin
- API 文档：http://localhost:10000/docs（FastAPI 自动生成）

---

## 🏗️ 代码架构

### 核心模块

| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 应用入口，所有路由定义、视图函数 |
| `database.py` | 数据库初始化、表结构定义、预设数据填充 |
| `config.py` | 配置项管理，从环境变量读取 |
| `auth.py` | 认证模块：会话 Token 创建/验证、权限校验 |

### 请求流程

```
客户端请求
  │
  ├── 静态资源 → /static/ → 文件直接返回
  ├── API 请求 → /api/* → JSON 响应
  ├── 公开页面 → / , /project/{slug} → Jinja2 渲染
  └── 管理后台 → /admin/* → 认证检查 → Jinja2 渲染
         │
         └── require_admin() 校验 session cookie
```

### 数据库表结构

| 表名 | 说明 |
|------|------|
| `admin_user` | 管理员账号（用户名、密码哈希） |
| `profile` | 个人资料（姓名、头衔、简介、头像、链接） |
| `project` | 项目信息（名称、slug、描述、技术栈、链接、排序、可见性） |
| `theme` | 主题配置（名称、CSS 变量、是否激活/自定义） |
| `site_view` | 访问记录（页面、IP、User-Agent、时间） |
| `site_setting` | 站点设置（键值对） |
| `avatar_history` | 头像历史记录（最近 3 张） |

---

## 🔧 开发规范

### 代码风格

- Python 代码遵循 PEP 8 规范
- 使用 4 空格缩进
- 函数和变量使用 snake_case 命名
- 路由函数命名格式：`{scope}_{resource}_{action}`（如 `admin_project_save`）

### 模板规范

- 所有模板继承自 `base.html`
- 管理后台模板放在 `templates/admin/` 目录
- 使用 Jinja2 模板语法，避免在模板中写复杂逻辑
- 前端文本使用中文

### 数据库操作

- 使用 `get_db()` 获取数据库连接
- 操作完成后必须调用 `db.close()` 关闭连接
- 写操作后调用 `db.commit()` 提交事务
- 使用参数化查询防止 SQL 注入

---

## 🧪 测试

目前项目暂无自动化测试。手动测试流程：

1. 启动开发服务器 `python main.py`
2. 访问首页确认项目列表正常显示
3. 登录管理后台 `/admin/login`
4. 测试项目 CRUD 操作
5. 切换主题确认样式生效
6. 检查 API 端点返回正确数据

---

## 📦 构建与部署

### GitHub Pages 自动部署

项目配置了 GitHub Actions 工作流，推送到 `main` 或 `dev` 分支时自动触发：

1. 初始化数据库并生成静态 HTML
2. 复制静态资源
3. 部署到 GitHub Pages

配置文件：`.github/workflows/deploy.yml`

### macOS 应用打包

```bash
python packaging/py2app_setup.py py2app
```

打包后的 `.app` 文件位于 `dist/` 目录。

### 手动部署

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export SECRET_KEY="your-production-secret"
export ADMIN_PASSWORD="your-secure-password"

# 启动服务
python main.py
```

生产环境建议使用 `uvicorn` 直接运行并配合反向代理：

```bash
uvicorn main:app --host 0.0.0.0 --port 10000 --workers 4
```

---

## ⚠️ 安全注意事项

根据代码审查报告（`REVIEW.md`），以下安全问题需要关注：

1. **生产环境必须设置强密码和随机 SECRET_KEY**
2. **添加 CSRF 防护**（推荐 `starlette-csrf`）
3. **文件上传需要校验** MIME 类型和大小限制
4. **Cookie 应设置** `samesite` 和 `secure` 属性
5. **添加登录频率限制** 防止暴力破解

详细安全审查见 [REVIEW.md](../REVIEW.md)。

---

## 📖 相关文档

- [README.md](../README.md) — 项目介绍
- [CHANGELOG.md](./CHANGELOG.md) — 版本更新日志
- [REVIEW.md](../REVIEW.md) — 代码审查报告
