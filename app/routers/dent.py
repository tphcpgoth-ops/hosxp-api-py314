from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/dent", tags=["Dental"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปสถิติทันตกรรมรายเดือนตามปีงบประมาณ")
async def get_dent_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT hn) AS hn_count,
               COUNT(DISTINCT vn) AS vn_count,
               DATE_FORMAT(vstdate,'%Y')+543 AS AY, DATE_FORMAT(vstdate,'%m') AS AM
        FROM dtmain
        WHERE vstdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(vstdate,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนสิทธิการรักษาทันตกรรมตามปีงบประมาณ")
async def get_dent_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT pt.hipdata_code, h.inscl_name, COUNT(DISTINCT d.vn) AS count
        FROM dtmain d
        LEFT OUTER JOIN vn_stat v ON v.vn = d.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE d.vstdate BETWEEN :start AND :end
        GROUP BY pt.hipdata_code, h.inscl_name
        ORDER BY COUNT(DISTINCT d.vn) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกสิทธิตามเดือน")
async def get_dent_stats_inscl_breakdown(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    # Compute date ranges for each month in the fiscal year
    months = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    params = {"start": start_date, "end": end_date}
    
    for m in months:
        y = year_start if m >= 10 else year_end
        s_date, e_date = get_month_range(y, m)
        params[f"s{m:02d}"] = s_date
        params[f"e{m:02d}"] = e_date

    # Patients SQL
    patients_sql = """
        SELECT v.pttype, pc.code AS pcode, pc.name AS pcodename, pt.nhso_code, pt.name AS pttypename,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s10 AND :e10 THEN d.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s11 AND :e11 THEN d.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s12 AND :e12 THEN d.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s01 AND :e01 THEN d.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s02 AND :e02 THEN d.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s03 AND :e03 THEN d.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s04 AND :e04 THEN d.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s05 AND :e05 THEN d.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s06 AND :e06 THEN d.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s07 AND :e07 THEN d.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s08 AND :e08 THEN d.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s09 AND :e09 THEN d.hn END) AS m09,
               COUNT(DISTINCT d.hn) AS hn_count
        FROM dtmain d
        LEFT OUTER JOIN vn_stat v ON v.vn = d.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN pcode pc ON pc.code = pt.pcode
        WHERE d.vstdate BETWEEN :start AND :end
        GROUP BY v.pttype, pc.code, pc.name, pt.nhso_code, pt.name
        ORDER BY v.pttype ASC
    """

    # Visits SQL
    visits_sql = """
        SELECT v.pttype, pc.code AS pcode, pc.name AS pcodename, pt.nhso_code, pt.name AS pttypename,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s10 AND :e10 THEN d.vn END) AS m10,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s11 AND :e11 THEN d.vn END) AS m11,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s12 AND :e12 THEN d.vn END) AS m12,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s01 AND :e01 THEN d.vn END) AS m01,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s02 AND :e02 THEN d.vn END) AS m02,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s03 AND :e03 THEN d.vn END) AS m03,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s04 AND :e04 THEN d.vn END) AS m04,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s05 AND :e05 THEN d.vn END) AS m05,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s06 AND :e06 THEN d.vn END) AS m06,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s07 AND :e07 THEN d.vn END) AS m07,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s08 AND :e08 THEN d.vn END) AS m08,
               COUNT(DISTINCT CASE WHEN d.vstdate BETWEEN :s09 AND :e09 THEN d.vn END) AS m09,
               COUNT(DISTINCT d.vn) AS vn_count
        FROM dtmain d
        LEFT OUTER JOIN vn_stat v ON v.vn = d.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN pcode pc ON pc.code = pt.pcode
        WHERE d.vstdate BETWEEN :start AND :end
        GROUP BY v.pttype, pc.code, pc.name, pt.nhso_code, pt.name
        ORDER BY v.pttype ASC
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    return {
        "fiscal_year": fiscal_year,
        "patients": [dict(r) for r in patients_res.mappings().all()],
        "visits": [dict(r) for r in visits_res.mappings().all()]
    }


@router.get("/stats-treatments", summary="จำนวนการรักษา แยกตามการรักษา")
async def get_dent_stats_treatments(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT d.dtcode, d.name, COUNT(n.vn) AS vn_count
        FROM dtdetail_name d
        LEFT OUTER JOIN dtdetail n ON n.dtcode = d.dtcode 
          AND n.vn IN (SELECT vn FROM dtmain WHERE vstdate BETWEEN :start AND :end)
        GROUP BY d.dtcode, d.name HAVING COUNT(n.vn) > 0 
        ORDER BY d.dtcode, d.name
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-groups", summary="จำนวนการรักษา แยกตามกลุ่มทันตกรรม")
async def get_dent_stats_groups(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT d.group_name, d.name, COUNT(n.vn) AS vn_count
        FROM dtdetail_name2 d
        LEFT OUTER JOIN dtdetail2 n ON n.dtcode = d.dtcode 
          AND n.vn IN (SELECT vn FROM dtmain WHERE vstdate BETWEEN :start AND :end)
        GROUP BY d.group_name, d.name HAVING COUNT(n.vn) > 0
        ORDER BY d.group_name, d.name
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-group-pie", summary="สัดส่วนการรักษา แยกตามกลุ่มทันตกรรม (Pie Chart)")
async def get_dent_stats_group_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT d.group_name, COUNT(n.vn) AS vn_count
        FROM dtdetail_name2 d
        LEFT OUTER JOIN dtdetail2 n ON n.dtcode = d.dtcode 
          AND n.vn IN (SELECT vn FROM dtmain WHERE vstdate BETWEEN :start AND :end)
        GROUP BY d.group_name HAVING COUNT(n.vn) > 0
        ORDER BY COUNT(n.vn) DESC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/patients", summary="รายชื่อผู้รับบริการทันตกรรมแยกตามเดือน", dependencies=[Depends(validate_api_key)])
async def get_dent_patients(
    ym: str = Query(..., description="เดือนในรูปแบบ YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT d.vn, d.vstdate, d.hn, p.pname, p.fname, p.lname, v.age_y, p.addrpart, p.road, p.moopart, t.full_name,
               GROUP_CONCAT(d.icd) AS icd, v.pdx, i.name AS dxname, v.pttype, pt.name AS pttypename, v.income, SUM(d.fee) AS dent_fee
        FROM dtmain d
        LEFT OUTER JOIN vn_stat v ON v.vn = d.vn
        LEFT OUTER JOIN patient p ON p.hn = d.hn
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        WHERE DATE_FORMAT(d.vstdate, '%Y-%m') = :ym
        GROUP BY d.vn, d.vstdate, d.hn, p.pname, p.fname, p.lname, v.age_y, p.addrpart, p.road, p.moopart, t.full_name, v.pdx, i.name, v.pttype, pt.name, v.income
    """
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    
    # Format dates/datetimes as standard strings
    formatted_data = []
    for r in rows:
        d_dict = dict(r)
        if d_dict.get("vstdate") and hasattr(d_dict["vstdate"], "isoformat"):
            d_dict["vstdate"] = d_dict["vstdate"].isoformat()
        formatted_data.append(d_dict)
        
    return {"ym": ym, "data": formatted_data}
