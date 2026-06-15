from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db

router = APIRouter(prefix="/xray", tags=["X-Ray"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการรังสีวินิจฉัย (X-Ray) รายเดือนตามปีงบประมาณ")
async def get_xray_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(x.order_date,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT x.hn) AS hn_count,
               COUNT(CASE WHEN x.department = 'OPD' THEN 1 END) AS opd_count,
               COUNT(CASE WHEN x.department = 'IPD' THEN 1 END) AS ipd_count,
               COUNT(*) AS total,
               DATE_FORMAT(x.order_date,'%Y')+543 AS AY, DATE_FORMAT(x.order_date,'%m') AS AM
        FROM xray_head x
        WHERE x.order_date BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(x.order_date,'%Y-%m')
        ORDER BY DATE_FORMAT(x.order_date,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนผู้ป่วยรังสีวินิจฉัยแยกตามสิทธิ์การรักษา")
async def get_xray_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT COALESCE(pt.name, 'ไม่ระบุ') AS inscl_name,
               COUNT(*) AS total
        FROM xray_head x
        LEFT OUTER JOIN pttype pt ON pt.pttype = x.pttype
        WHERE x.order_date BETWEEN :start AND :end
        GROUP BY pt.name
        ORDER BY COUNT(*) DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-type-pie", summary="สัดส่วนฟิล์มเอ็กซเรย์ตามประเภทการส่งตรวจ")
@router.get("/stats-groups-pie", summary="สัดส่วนฟิล์มเอ็กซเรย์ตามประเภทการส่งตรวจ")
async def get_xray_stats_groups_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT CASE 
            WHEN x.xray_list LIKE '%chest%' OR x.xray_list LIKE '%ทรวงอก%' OR x.xray_list LIKE '%CXR%' THEN 'Chest X-Ray'
            WHEN x.xray_list LIKE '%skull%' OR x.xray_list LIKE '%ศีรษะ%' THEN 'Skull & Head'
            WHEN x.xray_list LIKE '%spine%' OR x.xray_list LIKE '%กระดูกสันหลัง%' THEN 'Spine'
            WHEN x.xray_list LIKE '%extremity%' OR x.xray_list LIKE '%แขน%' OR x.xray_list LIKE '%ขา%' OR x.xray_list LIKE '%hand%' OR x.xray_list LIKE '%foot%' THEN 'Extremities'
            WHEN x.xray_list LIKE '%abdomen%' OR x.xray_list LIKE '%ช่องท้อง%' OR x.xray_list LIKE '%KUB%' THEN 'Abdomen'
            ELSE 'Other / General'
        END AS groupname,
        COUNT(*) AS total
        FROM xray_head x
        WHERE x.order_date BETWEEN :start AND :end
        GROUP BY groupname
        ORDER BY total DESC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกประเภทการส่งตรวจรายเดือน")
async def get_xray_stats_inscl_breakdown(
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
        SELECT COALESCE(x.pttype, 'N/A') AS groupcode,
               COALESCE(pt.name, 'ไม่ระบุ') AS groupname,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s10 AND :e10 THEN x.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s11 AND :e11 THEN x.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s12 AND :e12 THEN x.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s01 AND :e01 THEN x.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s02 AND :e02 THEN x.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s03 AND :e03 THEN x.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s04 AND :e04 THEN x.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s05 AND :e05 THEN x.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s06 AND :e06 THEN x.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s07 AND :e07 THEN x.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s08 AND :e08 THEN x.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN x.order_date BETWEEN :s09 AND :e09 THEN x.hn END) AS m09,
               COUNT(DISTINCT x.hn) AS total
        FROM xray_head x
        LEFT OUTER JOIN pttype pt ON pt.pttype = x.pttype
        WHERE x.order_date BETWEEN :start AND :end
        GROUP BY x.pttype, pt.name
        ORDER BY COUNT(DISTINCT x.hn) DESC
        LIMIT 50
    """

    # Visits (total surgery instances) SQL
    visits_sql = """
        SELECT COALESCE(x.pttype, 'N/A') AS groupcode,
               COALESCE(pt.name, 'ไม่ระบุ') AS groupname,
               COUNT(CASE WHEN x.order_date BETWEEN :s10 AND :e10 THEN 1 END) AS m10,
               COUNT(CASE WHEN x.order_date BETWEEN :s11 AND :e11 THEN 1 END) AS m11,
               COUNT(CASE WHEN x.order_date BETWEEN :s12 AND :e12 THEN 1 END) AS m12,
               COUNT(CASE WHEN x.order_date BETWEEN :s01 AND :e01 THEN 1 END) AS m01,
               COUNT(CASE WHEN x.order_date BETWEEN :s02 AND :e02 THEN 1 END) AS m02,
               COUNT(CASE WHEN x.order_date BETWEEN :s03 AND :e03 THEN 1 END) AS m03,
               COUNT(CASE WHEN x.order_date BETWEEN :s04 AND :e04 THEN 1 END) AS m04,
               COUNT(CASE WHEN x.order_date BETWEEN :s05 AND :e05 THEN 1 END) AS m05,
               COUNT(CASE WHEN x.order_date BETWEEN :s06 AND :e06 THEN 1 END) AS m06,
               COUNT(CASE WHEN x.order_date BETWEEN :s07 AND :e07 THEN 1 END) AS m07,
               COUNT(CASE WHEN x.order_date BETWEEN :s08 AND :e08 THEN 1 END) AS m08,
               COUNT(CASE WHEN x.order_date BETWEEN :s09 AND :e09 THEN 1 END) AS m09,
               COUNT(*) AS total
        FROM xray_head x
        LEFT OUTER JOIN pttype pt ON pt.pttype = x.pttype
        WHERE x.order_date BETWEEN :start AND :end
        GROUP BY x.pttype, pt.name
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


@router.get("/patients", summary="รายชื่อผู้รับบริการรังสีวินิจฉัยรายเดือน")
async def get_xray_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT x.order_date AS request_date,
               x.hn,
               x.vn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               x.age_y AS age,
               COALESCE(pt.name, 'ไม่ระบุ') AS pttypename,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               x.xray_list AS xrayname,
               x.xray_price AS price,
               'ทั่วไป' AS xray_room
        FROM xray_head x
        LEFT OUTER JOIN patient p ON p.hn = x.hn
        LEFT OUTER JOIN pttype pt ON pt.pttype = x.pttype
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        WHERE DATE_FORMAT(x.order_date, '%Y-%m') = :ym
        ORDER BY x.order_date ASC
        LIMIT 1000
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
