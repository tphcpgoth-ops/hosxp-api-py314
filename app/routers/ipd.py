from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter(prefix="/ipd", tags=["IPD"])

@router.get("/stats-summary", summary="สรุปสถิติผู้ป่วยในรายเดือนตามปีงบประมาณ")
async def get_ipd_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(regdate,'%Y-%m') AS AMONTH, COUNT(an) AS count,
               DATE_FORMAT(regdate,'%m') AS AM
        FROM ipt
        WHERE regdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(regdate,'%Y-%m')
        ORDER BY DATE_FORMAT(regdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-occupancy", summary="อัตราการครองเตียงตามปีงบประมาณ")
async def get_ipd_stats_occupancy(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    # Note: 115 is total beds, 30 is days. This is an approximation from the legacy code.
    sql = """
        SELECT DATE_FORMAT(dchdate,'%Y-%m') AS AMONTH, 
               (SUM(i.admdate)*100)/(115*30) AS admsum,
               DATE_FORMAT(dchdate,'%m') AS AM
        FROM an_stat i
        WHERE i.dchdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(dchdate,'%Y-%m')
        ORDER BY DATE_FORMAT(dchdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-gender", summary="สัดส่วนเพศผู้ป่วยในตามปีงบประมาณ")
async def get_ipd_stats_gender(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT s.name, COUNT(*) AS count 
        FROM an_stat i
        LEFT OUTER JOIN sex s ON s.code = i.sex
        WHERE i.regdate BETWEEN :start AND :end
        GROUP BY i.sex
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-icd10", summary="20 อันดับโรคผู้ป่วยในตามปีงบประมาณ")
async def get_ipd_stats_icd10(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT i.pdx, d.name AS diag, d.tname, COUNT(*) AS count,
               SUM(IF(i.sex = '1',1,0)) AS male,
               SUM(IF(i.sex = '2',1,0)) AS female
        FROM an_stat i
        LEFT OUTER JOIN icd101 d ON d.code = i.pdx
        WHERE i.regdate BETWEEN :start AND :end AND pdx <> ''
        GROUP BY i.pdx
        ORDER BY count DESC
        LIMIT 20
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}
