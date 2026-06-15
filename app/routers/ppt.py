from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db

router = APIRouter(prefix="/ppt", tags=["Thai Medicine"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการแพทย์แผนไทยรายเดือนตามปีงบประมาณ")
async def get_ppt_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(hs.service_date,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT hs.hn) AS hn_count,
               COUNT(*) AS total,
               DATE_FORMAT(hs.service_date,'%Y')+543 AS AY, DATE_FORMAT(hs.service_date,'%m') AS AM
        FROM health_med_service hs
        WHERE hs.service_date BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(hs.service_date,'%Y-%m')
        ORDER BY DATE_FORMAT(hs.service_date,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนสิทธิการรักษาแพทย์แผนไทยตามปีงบประมาณ")
async def get_ppt_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT t1.hipdata_code, t1.inscl_name, SUM(t1.total) AS total FROM (
            SELECT '00' AS hipdata_code, 'ไม่ทราบ' AS inscl_name, COUNT(*) AS total
            FROM health_med_service hs
            LEFT OUTER JOIN vn_stat v ON v.vn = hs.vn
            LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
            LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
            WHERE hs.service_date BETWEEN :start AND :end AND hs.vn IS NOT NULL AND v.pttype IS NULL
            GROUP BY pt.hipdata_code, h.inscl_name
        UNION ALL
            SELECT pt.hipdata_code, h.inscl_name, COUNT(*) AS total
            FROM health_med_service hs
            LEFT OUTER JOIN vn_stat v ON v.vn = hs.vn
            LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
            LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
            WHERE hs.service_date BETWEEN :start AND :end AND hs.vn IS NOT NULL AND v.pttype IS NOT NULL
            GROUP BY pt.hipdata_code, h.inscl_name
        UNION ALL
            SELECT pt.hipdata_code, h.inscl_name, COUNT(*) AS total
            FROM health_med_service hs
            LEFT OUTER JOIN an_stat v ON v.an = hs.an
            LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
            LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
            WHERE hs.service_date BETWEEN :start AND :end AND hs.an IS NOT NULL
            GROUP BY pt.hipdata_code, h.inscl_name
        ) AS t1
        GROUP BY t1.hipdata_code, t1.inscl_name
        ORDER BY SUM(t1.total) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-treatment-pie", summary="สัดส่วนประเภทการรักษาแพทย์แผนไทย")
async def get_ppt_stats_treatment_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT hs.health_med_treatment_type_id AS ttype,
               ht.health_med_treatment_type_name AS typename,
               COUNT(*) AS total
        FROM health_med_service hs
        LEFT OUTER JOIN health_med_treatment_type ht ON ht.health_med_treatment_type_id = hs.health_med_treatment_type_id
        WHERE hs.service_date BETWEEN :start AND :end AND hs.health_med_treatment_type_id IS NOT NULL
        GROUP BY hs.health_med_treatment_type_id, ht.health_med_treatment_type_name
        ORDER BY COUNT(*) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกประเภทการรักษาตามเดือน")
async def get_ppt_stats_inscl_breakdown(
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
        SELECT hs.health_med_treatment_type_id AS ttype,
               ht.health_med_treatment_type_name AS typename,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s10 AND :e10 THEN hs.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s11 AND :e11 THEN hs.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s12 AND :e12 THEN hs.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s01 AND :e01 THEN hs.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s02 AND :e02 THEN hs.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s03 AND :e03 THEN hs.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s04 AND :e04 THEN hs.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s05 AND :e05 THEN hs.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s06 AND :e06 THEN hs.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s07 AND :e07 THEN hs.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s08 AND :e08 THEN hs.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN hs.service_date BETWEEN :s09 AND :e09 THEN hs.hn END) AS m09,
               COUNT(DISTINCT hs.hn) AS total
        FROM health_med_service hs
        LEFT OUTER JOIN health_med_treatment_type ht ON ht.health_med_treatment_type_id = hs.health_med_treatment_type_id
        WHERE hs.service_date BETWEEN :start AND :end
        GROUP BY hs.health_med_treatment_type_id, ht.health_med_treatment_type_name
        ORDER BY hs.health_med_treatment_type_id ASC
    """

    # Visits (total service instances) SQL
    visits_sql = """
        SELECT hs.health_med_treatment_type_id AS ttype,
               ht.health_med_treatment_type_name AS typename,
               COUNT(CASE WHEN hs.service_date BETWEEN :s10 AND :e10 THEN hs.hn END) AS m10,
               COUNT(CASE WHEN hs.service_date BETWEEN :s11 AND :e11 THEN hs.hn END) AS m11,
               COUNT(CASE WHEN hs.service_date BETWEEN :s12 AND :e12 THEN hs.hn END) AS m12,
               COUNT(CASE WHEN hs.service_date BETWEEN :s01 AND :e01 THEN hs.hn END) AS m01,
               COUNT(CASE WHEN hs.service_date BETWEEN :s02 AND :e02 THEN hs.hn END) AS m02,
               COUNT(CASE WHEN hs.service_date BETWEEN :s03 AND :e03 THEN hs.hn END) AS m03,
               COUNT(CASE WHEN hs.service_date BETWEEN :s04 AND :e04 THEN hs.hn END) AS m04,
               COUNT(CASE WHEN hs.service_date BETWEEN :s05 AND :e05 THEN hs.hn END) AS m05,
               COUNT(CASE WHEN hs.service_date BETWEEN :s06 AND :e06 THEN hs.hn END) AS m06,
               COUNT(CASE WHEN hs.service_date BETWEEN :s07 AND :e07 THEN hs.hn END) AS m07,
               COUNT(CASE WHEN hs.service_date BETWEEN :s08 AND :e08 THEN hs.hn END) AS m08,
               COUNT(CASE WHEN hs.service_date BETWEEN :s09 AND :e09 THEN hs.hn END) AS m09,
               COUNT(*) AS total
        FROM health_med_service hs
        LEFT OUTER JOIN health_med_treatment_type ht ON ht.health_med_treatment_type_id = hs.health_med_treatment_type_id
        WHERE hs.service_date BETWEEN :start AND :end
        GROUP BY hs.health_med_treatment_type_id, ht.health_med_treatment_type_name
        ORDER BY hs.health_med_treatment_type_id ASC
    """

    patients_res = await db.execute(text(patients_sql), params)
    visits_res = await db.execute(text(visits_sql), params)

    return {
        "fiscal_year": fiscal_year,
        "patients": [dict(r) for r in patients_res.mappings().all()],
        "visits": [dict(r) for r in visits_res.mappings().all()]
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการแพทย์แผนไทยรายเดือน")
async def get_ppt_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT hs.service_date,
               hs.hn,
               hs.an,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               COALESCE(v.age_y, a.age_y) AS age,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               COALESCE(pt.name, pt2.name) AS pttypename,
               ht.health_med_treatment_type_name AS ppttname,
               CONCAT(v.pdx, ' ', i.name) AS dxname,
               v.income
        FROM health_med_service hs
        LEFT OUTER JOIN health_med_treatment_type ht ON ht.health_med_treatment_type_id = hs.health_med_treatment_type_id
        LEFT OUTER JOIN vn_stat v ON v.vn = hs.vn
        LEFT OUTER JOIN an_stat a ON a.an = hs.an
        LEFT OUTER JOIN patient p ON p.hn = hs.hn
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN pttype pt2 ON pt2.pttype = a.pttype
        LEFT OUTER JOIN icd101 i ON i.code = v.pdx
        WHERE DATE_FORMAT(hs.service_date, '%Y-%m') = :ym
        ORDER BY hs.service_date ASC
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
