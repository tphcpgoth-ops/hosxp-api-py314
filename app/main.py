from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import check_db_connection
from app.routers import opd, drug, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────
    print(f"\n🏥  {settings.APP_NAME}")
    print(f"    DB Type : {settings.DB_TYPE.upper()}")
    print(f"    DB Host : {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    ok = await check_db_connection()
    print(f"    DB Conn : {'✅ เชื่อมต่อสำเร็จ' if ok else '❌ เชื่อมต่อไม่ได้ — ตรวจสอบ .env'}\n")
    yield
    # ── Shutdown ─────────────────────────────────
    print("🛑  HOSxP API ปิดแล้ว")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "REST API สำหรับดึงข้อมูลจากฐานข้อมูล HOSxP\n\n"
        "รองรับ **MySQL** และ **PostgreSQL** — Python 3.14 compatible"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Production: ระบุ IP/Domain จริง
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────
app.include_router(opd.router,       prefix="/api/v1")
app.include_router(drug.router,      prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "db_type": settings.DB_TYPE,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = await check_db_connection()
    return {
        "status": "ok" if db_ok else "error",
        "database": settings.DB_TYPE,
        "db_connected": db_ok,
    }
