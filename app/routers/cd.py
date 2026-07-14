from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/cd", tags=["Communicable Diseases"])


def get_date_range(fiscal_year: Optional[int] = None, year: Optional[int] = None):
    val = fiscal_year if fiscal_year is not None else year
    if val is None:
        val = date.today().year + (1 if date.today().month > 9 else 0) + 543
    if val > 2400:  # BE fiscal year
        year_end = val - 543
        year_start = year_end - 1
        return f"{year_start}-10-01", f"{year_end}-09-30", val
    else:  # AD calendar year
        return f"{val}-01-01", f"{val}-12-31", val


@router.get("/stats-summary", summary="สรุปสถิติผู้ป่วยโรคติดต่อรายเดือนตามปีงบประมาณ")
async def get_cd_stats_summary(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT DATE_FORMAT(s.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT s.hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(s.vstdate,'%Y')+543 AS AY, DATE_FORMAT(s.vstdate,'%m') AS AM
        FROM surveil_member s
        WHERE s.vstdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(s.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(s.vstdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": res_year, "year": res_year, "data": [dict(r) for r in rows]}


@router.get("/stats-diseases", summary="สถิติโรคติดต่อยอดฮิต (อันดับ 506)")
async def get_cd_stats_diseases(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT n.code506,
               COALESCE(p.name, 'ไม่ระบุ') AS namee,
               COALESCE(n.name, 'ไม่ระบุ') AS namet,
               COUNT(*) AS count
        FROM surveil_member s
        LEFT OUTER JOIN provis_code506 p ON p.code = s.code506
        LEFT OUTER JOIN name506 n ON n.code = s.code506
        WHERE s.vstdate BETWEEN :start AND :end
        GROUP BY n.code506, p.name, n.name
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    
    data = []
    for r in rows:
        item = dict(r)
        msql = """
            SELECT DATE_FORMAT(s.vstdate,'%m') AS m, COUNT(*) AS cnt
            FROM surveil_member s
            WHERE s.vstdate BETWEEN :start AND :end AND s.code506 = :code
            GROUP BY DATE_FORMAT(s.vstdate,'%m')
        """
        mres = await db.execute(text(msql), {"start": start_date, "end": end_date, "code": item["code506"]})
        mrows = mres.mappings().all()
        item["months"] = {mr["m"]: mr["cnt"] for mr in mrows}
        data.append(item)
        
    return {"fiscal_year": res_year, "year": res_year, "data": data}


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
