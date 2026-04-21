import logging

import redis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import init_db
from app.routers.auth import router as auth_router
from app.routers.suppliers import router as suppliers_router
from app.seed import seed_default_user

logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def map_integrity_error(exc: IntegrityError) -> str:
    message = str(exc.orig)
    if "supplier.unified_credit_code" in message or "unified_credit_code" in message:
        return "统一社会信用代码已注册"
    if "supplier.company_name" in message or "company_name" in message:
        return "公司名称已注册"
    if "supplier.login_username" in message or "login_username" in message:
        return "登录账号已存在"
    if "user.username" in message or "username" in message:
        return "用户名已存在"
    return "数据保存失败，请检查提交内容"


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": map_integrity_error(exc)})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = exc.errors()[0]["msg"] if exc.errors() else "请求参数不合法"
    return JSONResponse(status_code=422, content={"detail": message})


@app.on_event("startup")
def on_startup() -> None:
    if settings.auto_create_tables:
        init_db()
        seed_default_user()
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        app.state.redis = client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 连接失败，当前以降级模式启动: %s", exc)
        app.state.redis = None


@app.get(f"{settings.api_v1_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(suppliers_router, prefix=settings.api_v1_prefix)
