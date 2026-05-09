"""
รันด้วย:  python run.py
Production: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.is_dev,
        log_level="info",
    )
