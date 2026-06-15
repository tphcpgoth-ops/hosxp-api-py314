from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db

router = APIRouter(prefix="/pts", tags=["Physical Therapy"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการกายภาพบำบัดรายเดือนตามปีงบประมาณ")
async def get_pts_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(pm.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT pm.hn) AS hn_count,
               COUNT(DISTINCT pm.vn) AS total,
               DATE_FORMAT(pm.vstdate,'%Y')+543 AS AY, DATE_FORMAT(pm.vstdate,'%m') AS AM
        FROM physic_main pm
        WHERE pm.vstdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(pm.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(pm.vstdate,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนผู้ป่วยกายภาพบำบัดแยกตามสิทธิ์การรักษา")
async def get_pts_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT COALESCE(h.inscl_name, 'ไม่ระบุ') AS inscl_name,
               COUNT(*) AS total
        FROM physic_main pm
        LEFT OUTER JOIN ovst v ON v.vn = pm.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE pm.vstdate BETWEEN :start AND :end
        GROUP BY h.inscl_name
        ORDER BY COUNT(*) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-type-pie", summary="สัดส่วนรายการกายภาพบำบัดแยกประเภทการบำบัดรักษา")
async def get_pts_stats_type_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT 'ส่งเสริมและป้องกัน' AS itemname, COUNT(pm.type1) AS total FROM physic_main pm WHERE pm.vstdate BETWEEN :start AND :end AND pm.type1 IS NOT NULL AND pm.type1 <> ''
        UNION ALL
        SELECT 'รักษา' AS itemname, COUNT(pm.type2) AS total FROM physic_main pm WHERE pm.vstdate BETWEEN :start AND :end AND pm.type2 IS NOT NULL AND pm.type2 <> ''
        UNION ALL
        SELECT 'ฟื้นฟูสมรรถภาพ' AS itemname, COUNT(pm.type3) AS total FROM physic_main pm WHERE pm.vstdate BETWEEN :start AND :end AND pm.type3 IS NOT NULL AND pm.type3 <> ''
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    # Filter out 0 count items if necessary, or return all
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-group-pie", summary="สัดส่วนกลุ่มอาการทางกายภาพบำบัด")
async def get_pts_stats_group_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT COALESCE(pg.physic_group_name, 'ไม่ระบุ') AS groupname,
               COUNT(DISTINCT pm.vn) AS total
        FROM physic_main pm
        LEFT OUTER JOIN physic_list pl ON pl.vn = pm.vn
        LEFT OUTER JOIN physic_group pg ON pg.physic_group_id = pl.physic_group_id
        WHERE pm.vstdate BETWEEN :start AND :end
        GROUP BY pg.physic_group_name
        ORDER BY COUNT(DISTINCT pm.vn) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกกลุ่มอาการกายภาพบำบัดรายเดือน")
async def get_pts_stats_inscl_breakdown(
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
        SELECT pg.physic_group_id AS groupcode,
               COALESCE(pg.physic_group_name, 'ไม่ระบุ') AS itemname,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s10 AND :e10 THEN pm.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s11 AND :e11 THEN pm.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s12 AND :e12 THEN pm.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s01 AND :e01 THEN pm.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s02 AND :e02 THEN pm.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s03 AND :e03 THEN pm.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s04 AND :e04 THEN pm.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s05 AND :e05 THEN pm.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s06 AND :e06 THEN pm.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s07 AND :e07 THEN pm.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s08 AND :e08 THEN pm.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN pm.vstdate BETWEEN :s09 AND :e09 THEN pm.hn END) AS m09,
               COUNT(DISTINCT pm.hn) AS total
        FROM physic_main pm
        LEFT OUTER JOIN physic_list pl ON pl.vn = pm.vn
        LEFT OUTER JOIN physic_group pg ON pg.physic_group_id = pl.physic_group_id
        WHERE pm.vstdate BETWEEN :start AND :end
        GROUP BY pg.physic_group_id, pg.physic_group_name
        ORDER BY pg.physic_group_id ASC
    """

    # Visits (total surgery instances) SQL
    visits_sql = """
        SELECT pg.physic_group_id AS groupcode,
               COALESCE(pg.physic_group_name, 'ไม่ระบุ') AS itemname,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s10 AND :e10 THEN pm.vn END) AS m10,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s11 AND :e11 THEN pm.vn END) AS m11,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s12 AND :e12 THEN pm.vn END) AS m12,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s01 AND :e01 THEN pm.vn END) AS m01,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s02 AND :e02 THEN pm.vn END) AS m02,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s03 AND :e03 THEN pm.vn END) AS m03,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s04 AND :e04 THEN pm.vn END) AS m04,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s05 AND :e05 THEN pm.vn END) AS m05,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s06 AND :e06 THEN pm.vn END) AS m06,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s07 AND :e07 THEN pm.vn END) AS m07,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s08 AND :e08 THEN pm.vn END) AS m08,
               COUNT(CASE WHEN pm.vstdate BETWEEN :s09 AND :e09 THEN pm.vn END) AS m09,
               COUNT(*) AS total
        FROM physic_main pm
        LEFT OUTER JOIN physic_list pl ON pl.vn = pm.vn
        LEFT OUTER JOIN physic_group pg ON pg.physic_group_id = pl.physic_group_id
        WHERE pm.vstdate BETWEEN :start AND :end
        GROUP BY pg.physic_group_id, pg.physic_group_name
        ORDER BY pg.physic_group_id ASC
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    # Convert groupcode to string for frontend safety
    patients_data = []
    for r in patients_res.mappings().all():
        d = dict(r)
        d["itemcode"] = str(d["groupcode"]) if d["groupcode"] is not None else "N/A"
        patients_data.append(d)

    visits_data = []
    for r in visits_res.mappings().all():
        d = dict(r)
        d["itemcode"] = str(d["groupcode"]) if d["groupcode"] is not None else "N/A"
        visits_data.append(d)

    return {
        "fiscal_year": fiscal_year,
        "patients": patients_data,
        "visits": visits_data
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการกายภาพบำบัดรายเดือน")
async def get_pts_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT pm.vstdate AS service_date,
               pm.vn,
               pm.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               v.age_y AS age,
               ptt.name AS pttypename,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               pg.physic_group_name AS itemname,
               CONCAT(v.pdx, ' ', i.name) AS dxname,
               COALESCE(v.income, 0) AS income
        FROM physic_main pm
        LEFT OUTER JOIN ovst v ON v.vn = pm.vn
        LEFT OUTER JOIN patient p ON p.hn = pm.hn
        LEFT OUTER JOIN pttype ptt ON ptt.pttype = v.pttype
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        LEFT OUTER JOIN physic_list pl ON pl.vn = pm.vn
        LEFT OUTER JOIN physic_group pg ON pg.physic_group_id = pl.physic_group_id
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        WHERE DATE_FORMAT(pm.vstdate, '%Y-%m') = :ym
        ORDER BY pm.vstdate ASC
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
