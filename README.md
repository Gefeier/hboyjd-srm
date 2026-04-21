# 欧阳聚德供应商协同平台后端骨架

## 启动方式

1. 复制环境变量文件：

```bash
cd backend
cp .env.example .env
```

2. 本地安装依赖：

```bash
cd backend
pip install -e ".[dev]"
```

3. 本地启动：

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Docker 启动：

```bash
cp backend/.env.example backend/.env
docker compose up -d --build
```

## 验收 curl 示例

### 1. 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

### 2. 使用 seed 账号登录

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ouyang","password":"ouyang123"}'
```

### 3. 匿名注册供应商

```bash
curl -X POST http://localhost:8000/api/v1/suppliers/register \
  -H 'Content-Type: application/json' \
  -d '{
    "company_name":"湖北联德钢材有限公司",
    "unified_credit_code":"91420100MA4K123456",
    "legal_person":"张三",
    "founded_date":"2020-05-01",
    "registered_address":"湖北省随州市高新区",
    "registered_capital":"500.00",
    "company_type":"有限责任公司",
    "taxpayer_type":"general",
    "business_intro":"主营钢材与紧固件供应。",
    "contact_name":"李四",
    "contact_phone":"13900000001",
    "contact_email":"supplier@example.com",
    "contact_position":"销售经理",
    "wechat":"steel-li",
    "landline":"0722-1234567",
    "login_password":"abc12345",
    "categories":["steel","fasteners"],
    "qualifications":[{"type":"business_license","url":"./uploads/license.pdf"}]
  }'
```

### 4. 列表查询和审核通过

```bash
curl http://localhost:8000/api/v1/suppliers \
  -H 'Authorization: Bearer <TOKEN>'
```

```bash
curl -X POST http://localhost:8000/api/v1/suppliers/1/review \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"action":"approve","grade":"A","note":"资料齐全，审核通过"}'
```

```bash
curl "http://localhost:8000/api/v1/suppliers?status=approved" \
  -H 'Authorization: Bearer <TOKEN>'
```
