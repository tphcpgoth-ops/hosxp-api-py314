from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.security import validate_api_key
from app.routers.cd import get_date_range

router = APIRouter(prefix="/psy", tags=["Psychiatry"])


@router.get("/stats-summary", summary="สรุปสถิติคลินิกจิตเวชรายเดือนตามปีงบประมาณ")
async def get_psy_stats_summary(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT DATE_FORMAT(o.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT c.hn) AS hn_count,
               COUNT(DISTINCT c.vn) AS total,
               DATE_FORMAT(o.vstdate,'%Y')+543 AS AY, DATE_FORMAT(o.vstdate,'%m') AS AM
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '109'
        GROUP BY DATE_FORMAT(o.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(o.vstdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": res_year, "year": res_year, "data": [dict(r) for r in rows]}


@router.get("/stats-diseases", summary="สถิติโรคในคลินิกจิตเวชตามปีงบประมาณ")
async def get_psy_stats_diseases(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT od.icd10 AS code,
               COALESCE(i.name, 'ไม่ระบุ') AS name,
               COUNT(*) AS count
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        INNER JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
        LEFT JOIN icd101 i ON i.code = od.icd10
        WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '109'
        GROUP BY od.icd10, i.name
        ORDER BY count DESC
        LIMIT 30
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    
    data = []
    for r in rows:
        item = dict(r)
        msql = """
            SELECT DATE_FORMAT(o.vstdate,'%m') AS m, COUNT(*) AS cnt
            FROM clinic_visit c
            INNER JOIN ovst o ON o.vn = c.vn
            INNER JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
            WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '109' AND od.icd10 = :code
            GROUP BY DATE_FORMAT(o.vstdate,'%m')
        """
        mres = await db.execute(text(msql), {"start": start_date, "end": end_date, "code": item["code"]})
        mrows = mres.mappings().all()
        item["months"] = {mr["m"]: mr["cnt"] for mr in mrows}
        data.append(item)
        
    return {"fiscal_year": res_year, "year": res_year, "data": data}


@router.get("/patients", summary="รายชื่อผู้รับบริการคลินิกจิตเวชตามเดือน", dependencies=[Depends(validate_api_key)])
async def get_psy_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT o.vstdate,
               o.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               od.icd10 AS pdx,
               COALESCE(i.name, 'ไม่ระบุ') AS dxname
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        LEFT JOIN patient p ON p.hn = o.hn
        LEFT JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
        LEFT JOIN icd101 i ON i.code = od.icd10
        WHERE DATE_FORMAT(o.vstdate, '%Y-%m') = :ym AND c.clinic = '109'
        ORDER BY o.vstdate ASC
        LIMIT 500
    """
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
