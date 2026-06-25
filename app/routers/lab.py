from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional
import calendar

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/lab", tags=["Laboratory"])


def get_month_range(year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


@router.get("/stats-summary", summary="สรุปผู้รับบริการชันสูตร (Lab) รายเดือนตามปีงบประมาณ")
async def get_lab_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(lh.order_date,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT lh.hn) AS hn_count,
               COUNT(CASE WHEN lh.department = 'OPD' THEN lh.lab_order_number END) AS opd_count,
               COUNT(CASE WHEN lh.department = 'IPD' THEN lh.lab_order_number END) AS ipd_count,
               COUNT(*) AS total,
               DATE_FORMAT(lh.order_date,'%Y')+543 AS AY, DATE_FORMAT(lh.order_date,'%m') AS AM
         FROM lab_head lh
         WHERE lh.order_date BETWEEN :start AND :end
         GROUP BY DATE_FORMAT(lh.order_date,'%Y-%m')
         ORDER BY DATE_FORMAT(lh.order_date,'%Y-%m') ASC
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-groups-pie", summary="สัดส่วนใบสั่งแล็บแยกตามกลุ่มงาน")
async def get_lab_stats_groups_pie(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT COALESCE(lg.lab_items_group_name, 'ไม่ระบุ') AS groupname,
               COUNT(DISTINCT lh.lab_order_number) AS total
        FROM lab_head lh
        LEFT OUTER JOIN lab_order lo ON lo.lab_order_number = lh.lab_order_number
        LEFT OUTER JOIN lab_items li ON li.lab_items_code = lo.lab_items_code
        LEFT OUTER JOIN lab_items_group lg ON lg.lab_items_group_code = li.lab_items_group
        WHERE lh.order_date BETWEEN :start AND :end
        GROUP BY lg.lab_items_group_name
        ORDER BY COUNT(DISTINCT lh.lab_order_number) DESC
        LIMIT 10
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl-breakdown", summary="ตารางแยกกลุ่มการตรวจแล็บรายเดือน")
async def get_lab_stats_inscl_breakdown(
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
        SELECT lg.lab_items_group_code AS groupcode,
               COALESCE(lg.lab_items_group_name, 'ไม่ระบุ') AS groupname,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s10 AND :e10 THEN lh.hn END) AS m10,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s11 AND :e11 THEN lh.hn END) AS m11,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s12 AND :e12 THEN lh.hn END) AS m12,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s01 AND :e01 THEN lh.hn END) AS m01,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s02 AND :e02 THEN lh.hn END) AS m02,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s03 AND :e03 THEN lh.hn END) AS m03,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s04 AND :e04 THEN lh.hn END) AS m04,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s05 AND :e05 THEN lh.hn END) AS m05,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s06 AND :e06 THEN lh.hn END) AS m06,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s07 AND :e07 THEN lh.hn END) AS m07,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s08 AND :e08 THEN lh.hn END) AS m08,
               COUNT(DISTINCT CASE WHEN lh.order_date BETWEEN :s09 AND :e09 THEN lh.hn END) AS m09,
               COUNT(DISTINCT lh.hn) AS total
        FROM lab_head lh
        LEFT OUTER JOIN lab_order lo ON lo.lab_order_number = lh.lab_order_number
        LEFT OUTER JOIN lab_items li ON li.lab_items_code = lo.lab_items_code
        LEFT OUTER JOIN lab_items_group lg ON lg.lab_items_group_code = li.lab_items_group
        WHERE lh.order_date BETWEEN :start AND :end
        GROUP BY lg.lab_items_group_code, lg.lab_items_group_name
        ORDER BY COUNT(DISTINCT lh.hn) DESC
        LIMIT 50
    """

    # Visits (total lab instances) SQL
    visits_sql = """
        SELECT lg.lab_items_group_code AS groupcode,
               COALESCE(lg.lab_items_group_name, 'ไม่ระบุ') AS groupname,
               COUNT(CASE WHEN lh.order_date BETWEEN :s10 AND :e10 THEN lh.lab_order_number END) AS m10,
               COUNT(CASE WHEN lh.order_date BETWEEN :s11 AND :e11 THEN lh.lab_order_number END) AS m11,
               COUNT(CASE WHEN lh.order_date BETWEEN :s12 AND :e12 THEN lh.lab_order_number END) AS m12,
               COUNT(CASE WHEN lh.order_date BETWEEN :s01 AND :e01 THEN lh.lab_order_number END) AS m01,
               COUNT(CASE WHEN lh.order_date BETWEEN :s02 AND :e02 THEN lh.lab_order_number END) AS m02,
               COUNT(CASE WHEN lh.order_date BETWEEN :s03 AND :e03 THEN lh.lab_order_number END) AS m03,
               COUNT(CASE WHEN lh.order_date BETWEEN :s04 AND :e04 THEN lh.lab_order_number END) AS m04,
               COUNT(CASE WHEN lh.order_date BETWEEN :s05 AND :e05 THEN lh.lab_order_number END) AS m05,
               COUNT(CASE WHEN lh.order_date BETWEEN :s06 AND :e06 THEN lh.lab_order_number END) AS m06,
               COUNT(CASE WHEN lh.order_date BETWEEN :s07 AND :e07 THEN lh.lab_order_number END) AS m07,
               COUNT(CASE WHEN lh.order_date BETWEEN :s08 AND :e08 THEN lh.lab_order_number END) AS m08,
               COUNT(CASE WHEN lh.order_date BETWEEN :s09 AND :e09 THEN lh.lab_order_number END) AS m09,
               COUNT(*) AS total
        FROM lab_head lh
        LEFT OUTER JOIN lab_order lo ON lo.lab_order_number = lh.lab_order_number
        LEFT OUTER JOIN lab_items li ON li.lab_items_code = lo.lab_items_code
        LEFT OUTER JOIN lab_items_group lg ON lg.lab_items_group_code = li.lab_items_group
        WHERE lh.order_date BETWEEN :start AND :end
        GROUP BY lg.lab_items_group_code, lg.lab_items_group_name
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


@router.get("/patients", summary="รายชื่อผู้รับบริการชันสูตรรายเดือน", dependencies=[Depends(validate_api_key)])
async def get_lab_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT lh.order_date,
               lh.hn,
               lh.an,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               TIMESTAMPDIFF(YEAR, p.birthday, lh.order_date) AS age,
               COALESCE(pt.name, pt2.name) AS pttypename,
               CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
               li.lab_items_name AS labname,
               lo.lab_order_result AS result
        FROM lab_head lh
        LEFT OUTER JOIN lab_order lo ON lo.lab_order_number = lh.lab_order_number
        LEFT OUTER JOIN lab_items li ON li.lab_items_code = lo.lab_items_code
        LEFT OUTER JOIN patient p ON p.hn = lh.hn
        LEFT OUTER JOIN vn_stat ov ON ov.vn = lh.vn
        LEFT OUTER JOIN pttype pt ON pt.pttype = ov.pttype
        LEFT OUTER JOIN an_stat av ON av.an = lh.an
        LEFT OUTER JOIN pttype pt2 ON pt2.pttype = av.pttype
        LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        WHERE DATE_FORMAT(lh.order_date, '%Y-%m') = :ym
        ORDER BY lh.order_date ASC
        LIMIT 1000
    """
    
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
