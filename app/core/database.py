from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_dev,   # log SQL ตอน development
    poolclass=NullPool,     # ไม่ค้าง connection — เหมาะกับ HOSxP
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """FastAPI Dependency — ใช้กับ Depends(get_db) ใน router"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """ทดสอบการเชื่อมต่อ DB ตอน startup"""
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False
