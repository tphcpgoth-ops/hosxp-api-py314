from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/or", tags=["Operating Room"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการห้องผ่าตัดรายเดือนตามปีงบประมาณ")
async def get_or_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(operation_date,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(operation_date,'%Y')+543 AS AY, DATE_FORMAT(operation_date,'%m') AS AM
        FROM operation_list
        WHERE operation_date BETWEEN :start AND :end AND status_id = '3'
        GROUP BY DATE_FORMAT(operation_date,'%Y-%m')
        ORDER BY DATE_FORMAT(operation_date,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-type-pie", summary="สัดส่วนประเภทการผ่าตัด")
async def get_or_stats_type_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT COALESCE(opt.name, 'ไม่ระบุ') AS typename,
               COUNT(*) AS total
        FROM operation_list o
        LEFT OUTER JOIN operation_type opt ON opt.operation_type_id = o.operation_type_id
        WHERE o.operation_date BETWEEN :start AND :end AND o.status_id = '3'
        GROUP BY opt.name
        ORDER BY COUNT(*) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกประเภทการผ่าตัดตามเดือน")
async def get_or_stats_inscl_breakdown(
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
        SELECT o.operation_type_id AS oprtype,
               COALESCE(opt.name, 'ไม่ระบุ') AS typename,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s10 AND :e10 THEN o.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s11 AND :e11 THEN o.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s12 AND :e12 THEN o.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s01 AND :e01 THEN o.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s02 AND :e02 THEN o.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s03 AND :e03 THEN o.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s04 AND :e04 THEN o.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s05 AND :e05 THEN o.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s06 AND :e06 THEN o.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s07 AND :e07 THEN o.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s08 AND :e08 THEN o.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN o.operation_date BETWEEN :s09 AND :e09 THEN o.hn END) AS m09,
               COUNT(DISTINCT o.hn) AS total
        FROM operation_list o
        LEFT OUTER JOIN operation_type opt ON opt.operation_type_id = o.operation_type_id
        WHERE o.operation_date BETWEEN :start AND :end AND o.status_id = '3'
        GROUP BY o.operation_type_id, opt.name
        ORDER BY o.operation_type_id ASC
    """

    # Visits (total surgery instances) SQL
    visits_sql = """
        SELECT o.operation_type_id AS oprtype,
               COALESCE(opt.name, 'ไม่ระบุ') AS typename,
               COUNT(CASE WHEN o.operation_date BETWEEN :s10 AND :e10 THEN o.hn END) AS m10,
               COUNT(CASE WHEN o.operation_date BETWEEN :s11 AND :e11 THEN o.hn END) AS m11,
               COUNT(CASE WHEN o.operation_date BETWEEN :s12 AND :e12 THEN o.hn END) AS m12,
               COUNT(CASE WHEN o.operation_date BETWEEN :s01 AND :e01 THEN o.hn END) AS m01,
               COUNT(CASE WHEN o.operation_date BETWEEN :s02 AND :e02 THEN o.hn END) AS m02,
               COUNT(CASE WHEN o.operation_date BETWEEN :s03 AND :e03 THEN o.hn END) AS m03,
               COUNT(CASE WHEN o.operation_date BETWEEN :s04 AND :e04 THEN o.hn END) AS m04,
               COUNT(CASE WHEN o.operation_date BETWEEN :s05 AND :e05 THEN o.hn END) AS m05,
               COUNT(CASE WHEN o.operation_date BETWEEN :s06 AND :e06 THEN o.hn END) AS m06,
               COUNT(CASE WHEN o.operation_date BETWEEN :s07 AND :e07 THEN o.hn END) AS m07,
               COUNT(CASE WHEN o.operation_date BETWEEN :s08 AND :e08 THEN o.hn END) AS m08,
               COUNT(CASE WHEN o.operation_date BETWEEN :s09 AND :e09 THEN o.hn END) AS m09,
               COUNT(*) AS total
        FROM operation_list o
        LEFT OUTER JOIN operation_type opt ON opt.operation_type_id = o.operation_type_id
        WHERE o.operation_date BETWEEN :start AND :end AND o.status_id = '3'
        GROUP BY o.operation_type_id, opt.name
        ORDER BY o.operation_type_id ASC
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    return {
        "fiscal_year": fiscal_year,
        "patients": [dict(r) for r in patients_res.mappings().all()],
        "visits": [dict(r) for r in visits_res.mappings().all()]
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการผ่าตัดรายเดือน", dependencies=[Depends(validate_api_key)])
async def get_or_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT o.operation_date,
               o.hn,
               o.an,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               o.age_text AS age,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               COALESCE(pt.name, pt2.name) AS pttypename,
               opt.name AS typename,
               o.patient_department,
               o.operation_name,
               o.operation_sum_price
        FROM operation_list o
        LEFT OUTER JOIN operation_type opt ON opt.operation_type_id = o.operation_type_id
        LEFT OUTER JOIN patient p ON p.hn = o.hn
        LEFT OUTER JOIN vn_stat ov ON ov.vn = o.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = ov.pttype
        LEFT OUTER JOIN an_stat av ON av.an = o.an
        LEFT OUTER JOIN pttype pt2 ON pt2.pttype = av.pttype
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        WHERE DATE_FORMAT(o.operation_date, '%Y-%m') = :ym AND o.status_id = '3'
        ORDER BY o.operation_date ASC
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
