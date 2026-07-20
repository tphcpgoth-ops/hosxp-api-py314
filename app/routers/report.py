from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import validate_api_key
import time
import re
import base64
from datetime import date, datetime

router = APIRouter(
    prefix="/report",
    tags=["Report"],
    responses={404: {"description": "Not found"}},
)

class ReportQueryRequest(BaseModel):
    query: str
    params: dict | None = None

def is_read_only_query(sql: str) -> bool:
    cleaned = re.sub(r'--.*$|/\*.*?\*/', '', sql, flags=re.MULTILINE).strip()
    if not re.match(r'^(SELECT|SHOW|DESCRIBE|EXPLAIN|WITH)\s+', cleaned, re.IGNORECASE):
        return False
    forbidden = r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|LOCK|UNLOCK)\b'
    if re.search(forbidden, cleaned, re.IGNORECASE):
        return False
    return True

@router.post("/execute", summary="ประมวลผลคำสั่ง SQL สำหรับระบบรายงาน End Users", dependencies=[Depends(validate_api_key)])
async def execute_report_sql(
    payload: ReportQueryRequest,
    db: AsyncSession = Depends(get_db)
):
    sql = payload.query.strip() if payload.query else ""
    if not sql:
        raise HTTPException(status_code=400, detail="กรุณาระบุคำสั่ง SQL")
    
    if not is_read_only_query(sql):
        raise HTTPException(
            status_code=400,
            detail="อนุญาตให้ใช้เฉพาะคำสั่ง SELECT (Read-only) เท่านั้น ไม่อนุญาตคำสั่ง INSERT, UPDATE, DELETE, DROP หรือคำสั่งแก้ไขโครงสร้าง"
        )
    
    start_time = time.time()
    try:
        # Extract parameter placeholders like :start_date from sql query
        raw_params = payload.params if payload.params else {}
        param_names = set(re.findall(r':([a-zA-Z0-9_]+)', sql))
        bind_params = {k: raw_params[k] for k in param_names if k in raw_params}

        result = await db.execute(text(sql), bind_params)
        rows = result.mappings().all()
        elapsed = time.time() - start_time
        
        data = []
        for row in rows:
            d = dict(row)
            for k, v in d.items():
                if isinstance(v, (bytes, bytearray)):
                    try:
                        d[k] = base64.b64encode(v).decode('utf-8')
                    except Exception:
                        d[k] = "<Binary Data>"
                elif isinstance(v, (date, datetime)):
                    d[k] = v.isoformat()
            data.append(d)
            
        columns = list(data[0].keys()) if data else []
        
        return {
            "success": True,
            "columns": columns,
            "results": data,
            "total_rows": len(data),
            "execution_time": round(elapsed, 2)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ไม่สามารถประมวลผล SQL ได้ หรือไม่สามารถเชื่อมต่อฐานข้อมูล HOSxP: {str(e)}"
        )
