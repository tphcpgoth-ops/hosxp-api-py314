from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db

router = APIRouter(prefix="/pcc", tags=["Primary Care Cluster"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการ PCC ตะพานหินรายเดือนตามปีงบประมาณ")
async def get_pcc_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(o.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT o.hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(o.vstdate,'%Y')+543 AS AY, DATE_FORMAT(o.vstdate,'%m') AS AM
        FROM ovst o
        WHERE o.vstdate BETWEEN :start AND :end AND o.main_dep = '085'
        GROUP BY DATE_FORMAT(o.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(o.vstdate,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนสิทธิการรักษา PCC ตะพานหิน")
async def get_pcc_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT pt.hipdata_code, h.inscl_name, COUNT(DISTINCT o.vn) AS count
        FROM ovst o
        LEFT OUTER JOIN vn_stat v ON v.vn = o.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE o.vstdate BETWEEN :start AND :end AND o.main_dep = '085'
        GROUP BY pt.hipdata_code, h.inscl_name
        ORDER BY COUNT(DISTINCT o.vn) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-diseases", summary="สถิติ 50 อันดับโรคพบบ่อย PCC ตะพานหิน")
async def get_pcc_stats_diseases(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT v.pdx AS code,
               i.name AS name,
               COUNT(DISTINCT v.vn) AS total
        FROM ovst o
        LEFT OUTER JOIN vn_stat v ON v.vn = o.vn
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        WHERE o.vstdate BETWEEN :start AND :end AND o.main_dep = '085' AND v.pdx IS NOT NULL AND v.pdx <> ''
        GROUP BY v.pdx, i.name
        ORDER BY COUNT(DISTINCT v.vn) DESC
        LIMIT 50
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกสิทธิตามเดือน PCC ตะพานหิน")
async def get_pcc_stats_inscl_breakdown(
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
        SELECT v.pttype, pt.name AS pttypename,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s10 AND :e10 THEN o.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s11 AND :e11 THEN o.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s12 AND :e12 THEN o.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s01 AND :e01 THEN o.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s02 AND :e02 THEN o.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s03 AND :e03 THEN o.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s04 AND :e04 THEN o.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s05 AND :e05 THEN o.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s06 AND :e06 THEN o.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s07 AND :e07 THEN o.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s08 AND :e08 THEN o.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN o.vstdate BETWEEN :s09 AND :e09 THEN o.hn END) AS m09,
               COUNT(DISTINCT o.hn) AS total
        FROM ovst o
        LEFT OUTER JOIN vn_stat v ON v.vn = o.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        WHERE o.vstdate BETWEEN :start AND :end AND o.main_dep = '085'
        GROUP BY v.pttype, pt.name
        ORDER BY COUNT(DISTINCT o.hn) DESC
        LIMIT 50
    """

    # Visits (total surgery instances) SQL
    visits_sql = """
        SELECT v.pttype, pt.name AS pttypename,
               COUNT(CASE WHEN o.vstdate BETWEEN :s10 AND :e10 THEN o.vn END) AS m10,
               COUNT(CASE WHEN o.vstdate BETWEEN :s11 AND :e11 THEN o.vn END) AS m11,
               COUNT(CASE WHEN o.vstdate BETWEEN :s12 AND :e12 THEN o.vn END) AS m12,
               COUNT(CASE WHEN o.vstdate BETWEEN :s01 AND :e01 THEN o.vn END) AS m01,
               COUNT(CASE WHEN o.vstdate BETWEEN :s02 AND :e02 THEN o.vn END) AS m02,
               COUNT(CASE WHEN o.vstdate BETWEEN :s03 AND :e03 THEN o.vn END) AS m03,
               COUNT(CASE WHEN o.vstdate BETWEEN :s04 AND :e04 THEN o.vn END) AS m04,
               COUNT(CASE WHEN o.vstdate BETWEEN :s05 AND :e05 THEN o.vn END) AS m05,
               COUNT(CASE WHEN o.vstdate BETWEEN :s06 AND :e06 THEN o.vn END) AS m06,
               COUNT(CASE WHEN o.vstdate BETWEEN :s07 AND :e07 THEN o.vn END) AS m07,
               COUNT(CASE WHEN o.vstdate BETWEEN :s08 AND :e08 THEN o.vn END) AS m08,
               COUNT(CASE WHEN o.vstdate BETWEEN :s09 AND :e09 THEN o.vn END) AS m09,
               COUNT(*) AS total
        FROM ovst o
        LEFT OUTER JOIN vn_stat v ON v.vn = o.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        WHERE o.vstdate BETWEEN :start AND :end AND o.main_dep = '085'
        GROUP BY v.pttype, pt.name
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    return {
        "fiscal_year": fiscal_year,
        "patients": [dict(r) for r in patients_res.mappings().all()],
        "visits": [dict(r) for r in visits_res.mappings().all()]
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการ PCC ตะพานหินรายเดือน")
async def get_pcc_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT o.vstdate,
               o.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               v.age_y AS age,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               pt.name AS pttypename,
               CONCAT(v.pdx, ' ', i.name) AS dxname,
               v.income
        FROM ovst o
        LEFT OUTER JOIN vn_stat v ON v.vn = o.vn
        LEFT OUTER JOIN patient p ON p.hn = o.hn
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        WHERE DATE_FORMAT(o.vstdate, '%Y-%m') = :ym AND o.main_dep = '085'
        ORDER BY o.vstdate ASC
        LIMIT 1000
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
