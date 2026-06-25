from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/er", tags=["Emergency Room"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการห้องฉุกเฉินรายเดือนตามปีงบประมาณ")
async def get_er_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(er.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT o.hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(er.vstdate,'%Y')+543 AS AY, DATE_FORMAT(er.vstdate,'%m') AS AM
        FROM er_regist er
        LEFT OUTER JOIN ovst o ON er.vn = o.vn
        WHERE er.vstdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(er.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(er.vstdate,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-pttype-pie", summary="สัดส่วนสิทธิการรักษาห้องฉุกเฉิน")
async def get_er_stats_pttype_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT pt.hipdata_code, h.inscl_name, COUNT(DISTINCT er.vn) AS total
        FROM er_regist er
        LEFT OUTER JOIN vn_stat v ON v.vn = er.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE er.vstdate BETWEEN :start AND :end
        GROUP BY pt.hipdata_code, h.inscl_name
        ORDER BY COUNT(DISTINCT er.vn) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-type-pie", summary="สัดส่วนประเภทผู้รับบริการห้องฉุกเฉิน")
async def get_er_stats_type_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT er.er_pt_type AS ertype,
               et.name AS typename,
               COUNT(*) AS total
        FROM er_regist er
        LEFT OUTER JOIN er_pt_type et ON et.er_pt_type = er.er_pt_type
        WHERE er.vstdate BETWEEN :start AND :end AND er.er_pt_type IS NOT NULL
        GROUP BY er.er_pt_type, et.name
        ORDER BY COUNT(*) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกสิทธิและประเภทผู้มารับบริการรายเดือน")
async def get_er_stats_inscl_breakdown(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    months = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    params = {"start": start_date, "end": end_date}
    
    for m in months:
        y = year_start if m >= 10 else year_end
        s_date, e_date = get_month_range(y, m)
        params[f"s{m:02d}"] = s_date
        params[f"e{m:02d}"] = e_date

    # Patients (unique HN) SQL
    patients_sql = """
        SELECT er.er_pt_type AS ertype,
               et.name AS typename,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s10 AND :e10 THEN o.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s11 AND :e11 THEN o.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s12 AND :e12 THEN o.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s01 AND :e01 THEN o.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s02 AND :e02 THEN o.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s03 AND :e03 THEN o.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s04 AND :e04 THEN o.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s05 AND :e05 THEN o.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s06 AND :e06 THEN o.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s07 AND :e07 THEN o.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s08 AND :e08 THEN o.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN er.vstdate BETWEEN :s09 AND :e09 THEN o.hn END) AS m09,
               COUNT(DISTINCT o.hn) AS total
        FROM er_regist er
        LEFT OUTER JOIN er_pt_type et ON et.er_pt_type = er.er_pt_type
        LEFT OUTER JOIN ovst o ON er.vn = o.vn
        WHERE er.vstdate BETWEEN :start AND :end
        GROUP BY er.er_pt_type, et.name
        ORDER BY er.er_pt_type ASC
    """

    # Visits (total service instances) SQL
    visits_sql = """
        SELECT er.er_pt_type AS ertype,
               et.name AS typename,
               COUNT(CASE WHEN er.vstdate BETWEEN :s10 AND :e10 THEN er.vn END) AS m10,
               COUNT(CASE WHEN er.vstdate BETWEEN :s11 AND :e11 THEN er.vn END) AS m11,
               COUNT(CASE WHEN er.vstdate BETWEEN :s12 AND :e12 THEN er.vn END) AS m12,
               COUNT(CASE WHEN er.vstdate BETWEEN :s01 AND :e01 THEN er.vn END) AS m01,
               COUNT(CASE WHEN er.vstdate BETWEEN :s02 AND :e02 THEN er.vn END) AS m02,
               COUNT(CASE WHEN er.vstdate BETWEEN :s03 AND :e03 THEN er.vn END) AS m03,
               COUNT(CASE WHEN er.vstdate BETWEEN :s04 AND :e04 THEN er.vn END) AS m04,
               COUNT(CASE WHEN er.vstdate BETWEEN :s05 AND :e05 THEN er.vn END) AS m05,
               COUNT(CASE WHEN er.vstdate BETWEEN :s06 AND :e06 THEN er.vn END) AS m06,
               COUNT(CASE WHEN er.vstdate BETWEEN :s07 AND :e07 THEN er.vn END) AS m07,
               COUNT(CASE WHEN er.vstdate BETWEEN :s08 AND :e08 THEN er.vn END) AS m08,
               COUNT(CASE WHEN er.vstdate BETWEEN :s09 AND :e09 THEN er.vn END) AS m09,
               COUNT(*) AS total
        FROM er_regist er
        LEFT OUTER JOIN er_pt_type et ON et.er_pt_type = er.er_pt_type
        WHERE er.vstdate BETWEEN :start AND :end
        GROUP BY er.er_pt_type, et.name
        ORDER BY er.er_pt_type ASC
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    return {
        "fiscal_year": fiscal_year,
        "patients": [dict(r) for r in patients_res.mappings().all()],
        "visits": [dict(r) for r in visits_res.mappings().all()]
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการห้องฉุกเฉินรายเดือน", dependencies=[Depends(validate_api_key)])
async def get_er_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT e.vstdate,
               v.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               v.age_y AS age,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               pt.name AS pttypename,
               et.name AS erpttype,
               CONCAT(v.pdx, ' ', i.name) AS dxname,
               v.income
        FROM er_regist e
        LEFT OUTER JOIN vn_stat v ON v.vn = e.vn
        LEFT OUTER JOIN patient p ON p.hn = v.hn
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        LEFT OUTER JOIN er_pt_type et ON et.er_pt_type = e.er_pt_type
        WHERE DATE_FORMAT(e.vstdate, '%Y-%m') = :ym
        ORDER BY e.vstdate ASC
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
