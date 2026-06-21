# 代码审查报告 — Portfolio 项目

> 审查时间：2026-06-22 | 审查范围：Python 5 files + HTML 23 files
> 审查维度：安全漏洞 · 代码质量 · 依赖安全 · 配置问题 · 架构问题

---

## 🔴 致命问题

### S-01 | 硬编码默认管理员凭据
- **文件**：`config.py:6`
- **描述**：`ADMIN_PASSWORD` 默认值为 `admin123`，如果未设置环境变量，任何人都能以默认密码登录管理后台。
- **建议**：生产环境强制要求设置环境变量，未设置时拒绝启动；或首次启动时强制用户设置密码。

### S-02 | 弱默认 SECRET_KEY
- **文件**：`config.py:4`
- **描述**：`SECRET_KEY` 默认值为 `"change-this-to-a-random-secret-key-in-production"`，可被猜测用于伪造 session token。
- **建议**：未设置时用 `os.urandom(32)` 生成随机密钥，或直接拒绝启动。

### S-03 | 无 CSRF 防护
- **文件**：`main.py` 所有 POST 端点
- **描述**：所有表单提交（登录、保存项目、上传头像、主题管理等）均无 CSRF token 校验。攻击者可诱导管理员在已登录状态下执行恶意操作。
- **建议**：引入 `starlette-csrf` 或自定义 middleware 为所有 POST 请求添加 CSRF token 验证。

### S-04 | 文件上传缺乏安全验证
- **文件**：`main.py:407-422`
- **描述**：头像上传仅根据文件扩展名命名，未校验文件内容类型（MIME type）、文件大小限制、以及是否为合法图片。攻击者可上传恶意文件（如 `.html`、`.svg` 含脚本）。
- **建议**：(1) 校验 `content-type` 为 `image/*`；(2) 限制文件大小（如 5MB）；(3) 使用 Pillow 等库验证图片完整性；(4) 白名单允许的扩展名。

### S-05 | Cookie 缺少安全属性
- **文件**：`main.py:136`
- **描述**：`set_cookie("session", token, httponly=True, max_age=86400)` 未设置 `samesite` 和 `secure` 属性，存在 CSRF 和中间人攻击风险。
- **建议**：`response.set_cookie("session", token, httponly=True, samesite="lax", secure=True, max_age=86400)`

---

## 🟡 警告问题

### W-01 | 无登录频率限制
- **文件**：`main.py:126-137`
- **描述**：登录接口无任何速率限制，可被暴力破解。
- **建议**：引入 `slowapi` 或记录失败次数进行临时封禁。

### W-02 | 裸 `except:` 吞噬异常（5处）
- **文件**：`main.py:379,462` / `database.py:188,192,196`
- **描述**：`except:` 会捕获所有异常（包括 `KeyboardInterrupt`、`SystemExit`），隐藏真实错误。
- **建议**：改为 `except Exception:` 或更具体的异常类型，并添加日志记录。

### W-03 | `require_admin` 返回 303 而非 401/403
- **文件**：`auth.py:26`
- **描述**：未认证时返回 HTTP 303（See Other），语义不正确，且返回的是 `HTTPException` 带 headers，实际上 `HTTPException` 的 `headers` 参数在某些 FastAPI 版本中不保证被传递。
- **建议**：改用 `RedirectResponse` 或返回标准 401 状态码。

### W-04 | 服务器信息泄露
- **文件**：`main.py:178-190`
- **描述**：管理后台仪表盘暴露了 CPU、内存、磁盘使用率等服务器内部信息。若管理后台被突破，攻击者可获取完整的服务器状态。
- **建议**：评估是否真正需要这些信息，或限制为本地访问。

### W-05 | 同步阻塞调用在异步上下文中
- **文件**：`main.py:179`
- **描述**：`psutil.cpu_percent(interval=0.1)` 是同步阻塞调用，在 FastAPI 异步框架中会阻塞事件循环。
- **建议**：使用 `asyncio.to_thread()` 或 `run_in_executor` 包装。

### W-06 | `psutil` 未声明在 requirements.txt 中
- **文件**：`main.py:3` vs `requirements.txt`
- **描述**：`main.py` 中 `import psutil`，但 `requirements.txt` 中未列出。
- **建议**：在 `requirements.txt` 中添加 `psutil>=5.9`。

### W-07 | innerHTML 潜在 XSS
- **文件**：`templates/index.html:442`、`templates/admin/dashboard.html:455`、`templates/admin/settings.html:574` 等多处
- **描述**：前端多处使用 `innerHTML` 直接插入从 API 获取的数据（如项目名称、头像 URL），若数据含恶意脚本可触发 XSS。
- **建议**：使用 `textContent` 替代，或对数据进行 HTML 转义。

### W-08 | 依赖版本未锁定
- **文件**：`requirements.txt`
- **描述**：所有依赖仅指定最低版本（`>=`），不同环境安装可能获得不同版本，导致兼容性问题。
- **建议**：生成 `requirements.lock` 或使用 `==` 固定版本。

---

## 🔵 建议改进

### A-01 | 数据库连接管理不统一
- **描述**：部分端点中 `get_db()` 返回的连接通过手动 `close()` 管理，容易遗漏导致连接泄漏。
- **建议**：使用 FastAPI 的 `Depends` + context manager 模式统一管理数据库连接。

### A-02 | 缺少全局错误处理中间件
- **描述**：未定义统一的异常处理中间件，500 错误会暴露栈信息。
- **建议**：添加 `@app.exception_handler(Exception)` 返回友好错误页面。

### A-03 | 缺少日志框架
- **描述**：整个项目无 `logging` 模块使用，所有错误静默处理。
- **建议**：引入 `logging` 模块，记录关键操作和异常。

### A-04 | `require_admin` 应使用 FastAPI 依赖注入
- **描述**：当前 `require_admin` 在函数体内手动调用，未利用 FastAPI 的 `Depends` 系统。
- **建议**：重构为 `def require_admin(request: Request) -> str` 作为依赖项。

### A-05 | 模板缺少 autoescape 配置确认
- **描述**：Jinja2 默认开启 autoescape（对 `.html` 文件），但未显式确认。
- **建议**：在创建 `Jinja2Templates` 时明确设置 `autoescape=True`。

---

## 评分

| 维度 | 得分 | 说明 |
|------|------|------|
| 安全漏洞 | **3/10** | 5个致命安全问题：默认凭据、无CSRF、文件上传无防护 |
| 代码质量 | **6/10** | 结构清晰，但异常处理粗糙，同步阻塞问题 |
| 依赖安全 | **5/10** | 使用了合理的库，但版本未锁定、有遗漏依赖 |
| 配置问题 | **4/10** | 默认配置极不安全，需强制要求环境变量 |
| 架构问题 | **6/10** | 模块划分合理，但缺少中间件层和统一错误处理 |

### 综合评分：**4.8 / 10** — 需要重大安全修复后方可上线
