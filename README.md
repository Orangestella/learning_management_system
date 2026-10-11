# Learning Management System

Flask 教学管理系统，包含管理员、学生、教师三种角色。后端使用 SQLite，前端使用 Jinja、原生 JavaScript 和响应式 CSS。

## 启动

建议使用 Python 3.10–3.12。依赖保持仓库原始版本，`requirements.txt` 未改动；`mysql-connector-python` 仍保留，但应用运行不再连接 MySQL。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FLASK_APP = "app"
.venv\Scripts\python.exe -m flask import-legacy
.venv\Scripts\python.exe app.py
```

打开 http://127.0.0.1:5000 ，只需填写生成的 `instance/legacy-credentials-*.csv` 中的个人 ID 和新密码登录。首次启动会创建 SQLite 数据库，导入命令会恢复旧库数据并生成随机密码。若想使用空库，可以跳过导入并执行 `python -m flask create-admin` 创建管理员。

`db.sql` 是唯一的 SQLite 建表文件，包含外键、级联删除、唯一约束和索引；启动自动创建缺失表，也可以执行 `python -m flask init-db`。该命令不会删除现有数据。

## 代码结构

- `app.py`：应用入口。
- `lms/__init__.py`：应用工厂、配置、蓝图注册和公共错误处理。
- `lms/db.py`：请求级数据库连接、事务和管理命令。
- `lms/routes/`：账户、课程、材料、论坛、消息、通知和首页路由。
- `lms/course_service.py`：课程与授课教师关系的原子更新。
- `lms/security.py`：认证、CSRF、角色和资源权限校验。
- `lms/navigation.py`：侧栏数据查询。
- `lms/views.py`：表格列、下载单元格和操作配置。
- `lms/search.py`：字段白名单、统一搜索语法及查询条件。
- `lms/legacy_import.py`：旧库解析、备份和幂等导入。
- `lms/uploads.py`：私有文件保存及授权下载。
- `templates/table.html`：公共表格；`editor_base.html`：公共编辑页。
- `static/js/app.js`：共享表单提交；`static/stylesheets/admin.css`：统一响应式布局。

表格按类型的业务分支集中在 Python 的展示配置中，模板只循环渲染列、单元格和操作。编辑表单保留必要的新增/修改条件。桌面使用 Grid 双栏，小屏改成单栏，宽表格在容器内滚动。

界面文案统一使用英文，登录后页头显示 Personal ID。论坛使用版块目录、主题列表和作者栏/楼层正文布局，显示回复数并提供多行回复框。消息收件箱使用头像和气泡流，按发送时间倒序显示，支持搜索与删除；本人发送给自己的消息显示在右侧。

发消息时，收件人输入框支持个人 ID 或姓名。输入 ID 后显示对应姓名；按姓名查找会显示最多 20 个候选及其 ID，选择候选后回填 ID。同名账户不会自动选择，发送时服务端再次验证收件人存在。

## 安全与数据行为

- 密码使用 Werkzeug 自带的 PBKDF2-SHA256、600,000 次迭代和随机盐；新密码至少 10 字符。
- 登录使用随机会话令牌，服务端只保存其 SHA256 摘要。Flask Cookie 经过签名，启用 HttpOnly、SameSite=Lax，最长有效 8 小时。
- 每次请求从数据库重新读取身份和角色。退出以及修改账户会撤销服务端会话，旧 Cookie 无法继续登录。
- 登录失败按规范化账户 ID 限速：15 分钟内 10 次失败后暂时锁定。
- 所有写操作使用 POST 和 CSRF Token，包括登录、退出、删除、加入论坛、选课和审批。
- 教师只能管理所授课程的资源；学生只能访问已批准课程和已加入论坛；消息只能由接收者删除。
- 上传大小最多 32 MiB，扩展名限定 PDF/DOC/DOCX，随机命名，存储在 `instance/uploads`。下载验证资源权限并以附件返回，上传文件不放入静态目录。
- SQLite 连接按请求创建和关闭，成功请求统一提交，失败请求回滚。课程及教师关系不会分步提交；提交失败时新上传文件也会清理。
- 账户编辑时留空密码会保留原哈希；账户自身删除被阻止。课程删除会级联删除所属材料、选课、通知和提交，账户删除也会级联清理关联记录。

原仓库的 MySQL 数据已恢复到 `data/legacy_mysql.sql`。导入命令会先备份 SQLite，再保留原始 ID 和关联关系导入数据，为新增的旧账户生成独立随机密码，以 PBKDF2 保存。旧 MD5 摘要不用于认证。重复导入不会新增重复记录、覆盖修改过的记录或重置已有密码；ID 冲突会回滚并报告。

```powershell
$env:FLASK_APP = "app"
.venv\Scripts\python.exe -m flask import-legacy
```

导入的新密码保存在 `instance/legacy-credentials-*.csv`，该目录已被 Git 忽略。备份位于 `instance/backups/`。旧仓库没有提交三个附件的实际文件，导入会报告缺失文件并保留受权限保护的附件记录；不会生成虚假文件。原文件放回 `static/files/` 后，重新执行导入会将其复制到私有上传目录。

## 搜索

列表页面和论坛帖子使用同一搜索语法。搜索范围下拉菜单可选择名称、ID、描述、角色等字段；点击 `?` 展开当前页面的字段说明。语法错误会在页面内提示，并保留输入与搜索范围。

- `name:English instructor:Edgar`：多个条件默认 AND。
- `name:"Course One"`：包含带空格的短语。
- `id:1 OR id:2`：任意一组满足，AND 优先于 OR。
- `-name:Python`：排除包含 Python 的名称。
- `name:=English`：精确匹配，文本默认包含匹配。
- `id:>=2 id:<10`：数字范围。
- `deadline:>=2024-01-01 deadline:<2025-01-01`：时间范围；日期字段支持按整天匹配。
- `role:student`：账户角色支持 admin/student/instructor，也支持管理员/学生/教师。

字段条件优先于下拉范围，不带字段的词受下拉范围限制。`%` 和 `_` 按普通字符处理。旧的 crs / ins / asn / lec / sen / con 前缀在适用页面兼容。搜索不支持括号分组；未知字段、错误日期和不合法的操作符会提示错误。所有字段来自白名单，值通过 SQL 参数绑定；OR 和排除条件始终放在原有资源权限条件内。

替换或删除材料后，历史文件保留在私有目录，不再能通过下载路由访问；需要存储清理时可备份后按数据库引用清理。

## 部署配置

开发环境允许本机 HTTP。HTTPS 部署设置：

```powershell
$env:LMS_HTTPS = "1"
$env:LMS_SECRET_KEY = "由部署环境提供的随机密钥"
```

`LMS_HTTPS=1` 开启 Secure Cookie 和 HSTS，需要实际使用 HTTPS。未设置密钥时，本地生成并持久保存于 `instance/secret.key`；部署时应由环境提供稳定密钥并限制实例目录权限。`instance/`、虚拟环境和本地配置均不提交 Git。生产环境使用 WSGI 服务部署，`app.py` 的启动方式用于本地开发。

## 验证

不添加测试依赖，使用 Python 标准库 unittest：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试在实例目录中创建隔离的临时 SQLite 数据库，结束后清理。覆盖三种角色页面与搜索、CSRF、Cookie 伪造、会话过期及撤销、资源越权、密码保存、文件访问、论坛和选课流程、评分、通知查询、级联删除及中途失败的事务回滚，以及高级搜索布尔逻辑、范围、字面量匹配、权限隔离和旧库导入。

安全实现参考 [Flask 安全说明](https://flask.palletsprojects.com/en/stable/web-security/) 和 [Werkzeug 密码哈希实现](https://github.com/pallets/werkzeug/blob/2.1.2/src/werkzeug/security.py)。代码只采用原依赖版本支持的 API。
