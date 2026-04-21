# 欧阳聚德供应商协同平台 · MVP 第一刀 Brief

## 你是谁 / 任务背景
你是「澜心」，本次任务是为湖北欧阳聚德汽车有限公司搭建一套供应商关系管理（SRM）系统的**后端骨架**。这是从零开始的项目，目标是让供应商在线注册、采购方审核，后续还会加询价单、报价、比价、定点、订单等模块。当前这一刀**只做供应商入驻闭环**（注册 → 入库 → 采购员审核通过/驳回）。

参考同行业的用友 BIP 采购云、金蝶采购云、鲸采云 SRM。术语用行业标准：**供应商、入驻、准入审核、合格供应商库、采购员**。不要用"招投标/中标/投标"这套词——这不是招投标平台。

---

## 本次交付范围（仅这些，不要多做）

### 后端
- FastAPI + SQLModel + PostgreSQL 15 + Redis 7
- JWT 登录（用 `python-jose`）
- 密码哈希用 `passlib[bcrypt]`
- Alembic 迁移
- `uv` 或 `pip` 均可，选一个
- Dockerfile + docker-compose.yml（起 pg / redis / api 三个服务）
- 环境变量走 `.env` + `pydantic-settings`
- 最少必要的 pytest 冒烟测试

### 不做
- 前端（下一刀）
- 询价单/报价/比价/订单（后续）
- 文件上传到 OSS（先存本地 `./uploads/`，字段留接口）
- 短信/邮件（接口留，实现先 print）
- 微信小程序
- 电子签章
- 金蝶对接

---

## 目录结构（严格遵守）

```
G:/hboyjd-srm/
├── brief.md                     ← 本文件（你在读）
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              ← FastAPI 入口
│   │   ├── config.py            ← pydantic-settings
│   │   ├── db.py                ← engine + session
│   │   ├── security.py          ← JWT + 密码哈希
│   │   ├── deps.py              ← Depends 依赖（get_current_user 等）
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py          ← 采购方员工
│   │   │   └── supplier.py      ← 供应商
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   └── supplier.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          ← /auth/login, /auth/me
│   │   │   └── suppliers.py     ← /suppliers/*
│   │   └── seed.py              ← 塞一个默认采购员账号: ouyang / ouyang123
│   ├── alembic/                 ← alembic init 后的结构
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_suppliers.py    ← 冒烟: 注册 + 列表 + 审核
│   ├── Dockerfile
│   ├── pyproject.toml           ← 或 requirements.txt
│   └── .env.example
├── docker-compose.yml           ← pg + redis + api
├── .gitignore
└── README.md                    ← 启动命令
```

---

## 数据库 Schema

### `user`（采购方员工）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK autoincrement | |
| username | varchar(32) UNIQUE NOT NULL | 登录账号 |
| password_hash | varchar(256) NOT NULL | bcrypt |
| name | varchar(64) NOT NULL | 真实姓名 |
| role | enum('admin', 'buyer', 'approver') NOT NULL | 管理员/采购员/审批人 |
| phone | varchar(20) | |
| email | varchar(128) | |
| is_active | bool NOT NULL default true | |
| created_at | datetime NOT NULL default now | |
| updated_at | datetime NOT NULL default now on update | |

### `supplier`（供应商主档）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK autoincrement | |
| code | varchar(32) UNIQUE NOT NULL | 系统生成，如 `SUP20260420001` |
| company_name | varchar(128) UNIQUE NOT NULL | 公司全称 |
| unified_credit_code | varchar(18) UNIQUE NOT NULL | 统一社会信用代码 |
| legal_person | varchar(32) NOT NULL | 法人 |
| founded_date | date | 成立日期 |
| registered_address | varchar(256) | 注册地 |
| registered_capital | decimal(12,2) | 注册资本（万元） |
| company_type | varchar(32) | 企业类型 |
| taxpayer_type | enum('general', 'small_scale') | 纳税人身份 |
| business_intro | text | 主营业务简介 |
| contact_name | varchar(32) NOT NULL | 联系人 |
| contact_phone | varchar(20) NOT NULL | |
| contact_email | varchar(128) NOT NULL | |
| contact_position | varchar(32) | 职位 |
| wechat | varchar(64) | |
| landline | varchar(32) | |
| login_username | varchar(32) UNIQUE NOT NULL | 登录账号（默认用手机号）|
| login_password_hash | varchar(256) NOT NULL | |
| status | enum('pending', 'approved', 'rejected', 'frozen') NOT NULL default 'pending' | |
| grade | enum('A', 'B', 'C', 'D') | 分级（审核通过后由采购员打） |
| review_note | text | 审核备注 |
| reviewed_by | int FK(user.id) | 审核人 |
| reviewed_at | datetime | 审核时间 |
| categories | json | 供应品类 `["steel", "fasteners", ...]` |
| qualifications | json | 资质文件引用 `[{"type":"business_license","url":"..."}]` |
| created_at | datetime NOT NULL | |
| updated_at | datetime NOT NULL | |

索引：`(status, created_at DESC)`, `(unified_credit_code)`, `(company_name)`

---

## API 接口清单（本刀只做这 7 个）

所有接口前缀 `/api/v1`。JSON 格式。错误返回 `{"detail": "xxx"}`。

### Auth
1. `POST /auth/login` — body `{username, password}`，返回 `{access_token, token_type:"bearer", user:{...}}`（采购员登录，后续供应商登录复用同接口，通过 username 前缀或独立字段区分）。MVP 先只做采购员登录。
2. `GET /auth/me` — 返回当前登录用户

### Suppliers
3. `POST /suppliers/register` — 供应商自注册，**公开接口不需要 token**。body 接收所有 `supplier` 字段（除了系统字段）。成功返回 201 + `{id, code, status:"pending"}`。code 由后端按 `SUP{yyyymmdd}{3位序号}` 生成。
4. `GET /suppliers` — 采购员看列表，需要 token。query 参数：`status` / `grade` / `category` / `keyword` / `page=1` / `page_size=20`。返回 `{items:[], total, page, page_size}`。
5. `GET /suppliers/{id}` — 看详情，需要 token。
6. `POST /suppliers/{id}/review` — 审核，需要 token + role in `[admin, buyer]`。body `{action: "approve"|"reject", note?, grade?}`。action=approve 时 grade 必填。成功后更新 `status` / `grade` / `reviewed_by` / `reviewed_at` / `review_note`。
7. `POST /suppliers/{id}/freeze` — 冻结（加黑名单），同权限。body `{note}`。设置 status='frozen'。

---

## 约束 · 一定遵守

1. **不装新奇依赖**。核心依赖：`fastapi`, `uvicorn[standard]`, `sqlmodel`, `alembic`, `psycopg[binary]`, `redis`, `python-jose[cryptography]`, `passlib[bcrypt]`, `pydantic-settings`, `python-multipart`（给未来上传用）。Dev 依赖：`pytest`, `httpx`, `pytest-asyncio`。
2. **字段命名**：Python 属性用 `snake_case`，数据库列名也用 `snake_case`，JSON 字段名保持 `snake_case`。
3. **错误处理**：全局 exception handler 把 SQLAlchemy IntegrityError（比如重复 unified_credit_code）转成 400 `{"detail": "统一社会信用代码已注册"}`，用**中文错误消息**。
4. **密码强度**：注册时要求至少 8 位，含字母和数字。后端校验。
5. **CORS**：开发环境放开 `http://localhost:5173` 和 `http://localhost:3000`。
6. **不要过度设计**：别加什么 CQRS、事件总线、六边形架构。朴素 router → service → model 三层就够了。
7. **代码里的注释用中文**，但标识符用英文。
8. **日期时间**：统一用 UTC 存储，API 返回 ISO 8601。

---

## 验收标准（你跑完必须做的自检）

1. `cd backend && python -m pytest tests/ -v` 全绿
2. `docker compose up -d --build` 起来后，`curl http://localhost:8000/api/v1/health` 返回 `{"status":"ok"}`
3. 用 seed 账号登录 `curl -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"ouyang","password":"ouyang123"}'` 拿到 token
4. 匿名注册一个假供应商 → 拿 token 调列表能看到它 status=pending → 调 review 审核通过 → 再查列表 status=approved

最后在 `README.md` 写清楚启动命令和以上四步的 curl 示例。

---

## 交付形式

把本次所有文件写在 `G:/hboyjd-srm/` 下（严格按上面目录结构）。跑完最后在**终端输出**一行清晰的 `DONE: <简要 summary + 测试结果>`，不要长篇回顾。你的主要输出是**文件落盘**，不是文字陈述。

开工。
