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

@router.get("/stats-ward-monthly", summary="สรุปผู้ป่วยในรายเดือนแยกตามหอผู้ป่วย (ตึก)")
async def get_ipd_stats_ward_monthly(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT 
            w.ward, 
            w.name AS ward_name,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '10', 1, 0)) AS m10,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '11', 1, 0)) AS m11,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '12', 1, 0)) AS m12,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '01', 1, 0)) AS m01,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '02', 1, 0)) AS m02,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '03', 1, 0)) AS m03,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '04', 1, 0)) AS m04,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '05', 1, 0)) AS m05,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '06', 1, 0)) AS m06,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '07', 1, 0)) AS m07,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '08', 1, 0)) AS m08,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '09', 1, 0)) AS m09,
            COUNT(i.an) AS total
        FROM ward w
        LEFT JOIN ipt i ON i.ward = w.ward AND i.regdate BETWEEN :start AND :end
        WHERE w.ward_active = 'Y'
        GROUP BY w.ward, w.name
        ORDER BY w.ward ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-ward-occupancy", summary="อัตราการครองเตียงแยกตามหอผู้ป่วย (ตึก)")
async def get_ipd_stats_ward_occupancy(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT 
            w.ward, 
            w.name AS ward_name,
            COALESCE(w.bedcount, 0) AS bedcount,
            COUNT(i.an) AS patient_count,
            COALESCE(SUM(i.admdate), 0) AS total_admdate,
            IF(COUNT(i.an) > 0, SUM(i.admdate) / COUNT(i.an), 0) AS avg_admdate,
            IF(w.bedcount > 0, (SUM(i.admdate) * 100) / (w.bedcount * 365), 0) AS occupancy_rate
        FROM ward w
        LEFT JOIN an_stat i ON i.ward = w.ward AND i.dchdate BETWEEN :start AND :end
        WHERE w.ward_active = 'Y'
        GROUP BY w.ward, w.name, w.bedcount
        ORDER BY w.ward ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

