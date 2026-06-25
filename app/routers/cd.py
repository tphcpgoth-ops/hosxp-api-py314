from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/cd", tags=["Communicable Diseases"])


@router.get("/stats-summary", summary="สรุปสถิติผู้ป่วยโรคติดต่อรายเดือนตามปีปฏิทิน")
async def get_cd_stats_summary(
    year: int = Query(default=date.today().year),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT DATE_FORMAT(s.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT s.hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(s.vstdate,'%Y') AS AY, DATE_FORMAT(s.vstdate,'%m') AS AM
        FROM surveil_member s
        WHERE DATE_FORMAT(s.vstdate,'%Y') = :year
        GROUP BY DATE_FORMAT(s.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(s.vstdate,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"year": str(year)})
    rows = result.mappings().all()
    return {"year": year, "data": [dict(r) for r in rows]}


@router.get("/stats-diseases", summary="สถิติโรคติดต่อยอดฮิต (อันดับ 506)")
async def get_cd_stats_diseases(
    year: int = Query(default=date.today().year),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT n.code506,
               COALESCE(p.name, 'ไม่ระบุ') AS namee,
               COALESCE(n.name, 'ไม่ระบุ') AS namet,
               COUNT(*) AS count
        FROM surveil_member s
        LEFT OUTER JOIN provis_code506 p ON p.code = s.code506
        LEFT OUTER JOIN name506 n ON n.code = s.code506
        WHERE DATE_FORMAT(s.vstdate,'%Y') = :year
        GROUP BY n.code506, p.name, n.name
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """
    
    result = await db.execute(text(sql), {"year": str(year)})
    rows = result.mappings().all()
    return {"year": year, "data": [dict(r) for r in rows]}


@router.get("/patients", summary="รายชื่อผู้ป่วยโรคติดต่อตามเดือน", dependencies=[Depends(validate_api_key)])
async def get_cd_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT s.vstdate,
               s.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               n.name AS name506,
               s.pdx,
               i.name AS dxname,
               CONCAT(s.addr, ' ม.', s.moo, ' ', t.full_name) AS address
        FROM surveil_member s
        LEFT OUTER JOIN patient p ON p.hn = s.hn
        LEFT OUTER JOIN icd101 i ON i.code = s.pdx
        LEFT OUTER JOIN name506 n ON n.code = s.code506
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(s.chwpart, s.amppart, s.tmbpart)
        WHERE DATE_FORMAT(s.vstdate, '%Y-%m') = :ym
        ORDER BY s.vstdate ASC
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
