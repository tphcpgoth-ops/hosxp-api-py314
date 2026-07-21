from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db

router = APIRouter(prefix="/ipd", tags=["IPD"])

@router.get("/stats-summary", summary="สรุปสถิติผู้ป่วยในรายเดือนตามปีงบประมาณ")
async def get_ipd_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT DATE_FORMAT(regdate,'%Y-%m') AS AMONTH, COUNT(an) AS count,
               DATE_FORMAT(regdate,'%m') AS AM
        FROM ipt
        WHERE regdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(regdate,'%Y-%m')
        ORDER BY DATE_FORMAT(regdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-occupancy", summary="อัตราการครองเตียงตามปีงบประมาณ")
async def get_ipd_stats_occupancy(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    # Note: 115 is total beds, 30 is days. This is an approximation from the legacy code.
    sql = """
        SELECT DATE_FORMAT(dchdate,'%Y-%m') AS AMONTH, 
               (SUM(i.admdate)*100)/(115*30) AS admsum,
               DATE_FORMAT(dchdate,'%m') AS AM
        FROM an_stat i
        WHERE i.dchdate BETWEEN :start AND :end
        GROUP BY DATE_FORMAT(dchdate,'%Y-%m')
        ORDER BY DATE_FORMAT(dchdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-gender", summary="สัดส่วนเพศผู้ป่วยในตามปีงบประมาณ")
async def get_ipd_stats_gender(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT s.name, COUNT(*) AS count 
        FROM an_stat i
        LEFT OUTER JOIN sex s ON s.code = i.sex
        WHERE i.regdate BETWEEN :start AND :end
        GROUP BY i.sex
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-icd10", summary="20 อันดับโรคผู้ป่วยในตามปีงบประมาณ")
async def get_ipd_stats_icd10(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT i.pdx, d.name AS diag, d.tname, COUNT(*) AS count,
               SUM(IF(i.sex = '1',1,0)) AS male,
               SUM(IF(i.sex = '2',1,0)) AS female
        FROM an_stat i
        LEFT OUTER JOIN icd101 d ON d.code = i.pdx
        WHERE i.regdate BETWEEN :start AND :end AND pdx <> ''
        GROUP BY i.pdx
        ORDER BY count DESC
        LIMIT 20
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-ward-monthly", summary="สรุปผู้ป่วยในรายเดือนแยกตามหอผู้ป่วย (ตึก)")
async def get_ipd_stats_ward_monthly(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT 
            w.ward, 
            w.name AS ward_name,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '10', 1, 0)) AS m10,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '11', 1, 0)) AS m11,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '12', 1, 0)) AS m12,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '01', 1, 0)) AS m01,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '02', 1, 0)) AS m02,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '03', 1, 0)) AS m03,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '04', 1, 0)) AS m04,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '05', 1, 0)) AS m05,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '06', 1, 0)) AS m06,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '07', 1, 0)) AS m07,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '08', 1, 0)) AS m08,
            SUM(IF(DATE_FORMAT(i.regdate, '%m') = '09', 1, 0)) AS m09,
            COUNT(i.an) AS total
        FROM ward w
        LEFT JOIN ipt i ON i.ward = w.ward AND i.regdate BETWEEN :start AND :end
        WHERE w.ward_active = 'Y'
        GROUP BY w.ward, w.name
        ORDER BY w.ward ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/stats-ward-occupancy", summary="อัตราการครองเตียงแยกตามหอผู้ป่วย (ตึก)")
async def get_ipd_stats_ward_occupancy(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT 
            w.ward, 
            w.name AS ward_name,
            COALESCE(w.bedcount, 0) AS bedcount,
            COUNT(i.an) AS patient_count,
            COALESCE(SUM(i.admdate), 0) AS total_admdate,
            IF(COUNT(i.an) > 0, SUM(i.admdate) / COUNT(i.an), 0) AS avg_admdate,
            IF(w.bedcount > 0, (SUM(i.admdate) * 100) / (w.bedcount * 365), 0) AS occupancy_rate
        FROM ward w
        LEFT JOIN an_stat i ON i.ward = w.ward AND i.dchdate BETWEEN :start AND :end
        WHERE w.ward_active = 'Y'
        GROUP BY w.ward, w.name, w.bedcount
        ORDER BY w.ward ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}

@router.get("/summary-today", summary="สรุปข้อมูลผู้ป่วยใน วันนี้")
async def get_ipd_summary_today(
    db: AsyncSession = Depends(get_db),
):
    sql_beds = "SELECT COALESCE(SUM(bedcount), 0) AS total_beds FROM ward WHERE ward_active = 'Y'"
    r_beds = await db.execute(text(sql_beds))
    total_beds = int(r_beds.scalar() or 0)

    sql_today = """
        SELECT 
            SUM(IF(regdate = CURDATE(), 1, 0)) AS new_admit_today,
            SUM(IF(dchdate = CURDATE(), 1, 0)) AS discharge_today,
            SUM(IF(dchdate IS NULL, 1, 0)) AS current_admit
        FROM ipt
    """
    r_today = await db.execute(text(sql_today))
    t_row = r_today.mappings().first() or {}

    new_admit_today = int(t_row.get("new_admit_today") or 0)
    discharge_today = int(t_row.get("discharge_today") or 0)
    current_admit = int(t_row.get("current_admit") or 0)
    available_beds = max(0, total_beds - current_admit)

    occupancy_rate = round((current_admit * 100.0) / total_beds, 2) if total_beds > 0 else 0.0

    sql_rights = """
        SELECT 
            SUM(IF(p.hipdata_code IN ('OFC','SSS','LGO'), 1, 0)) AS pttype_pay,
            SUM(IF(p.hipdata_code = 'UCS', 1, 0)) AS pttype_uc,
            SUM(IF(p.hipdata_code NOT IN ('OFC','SSS','LGO','UCS') OR p.hipdata_code IS NULL, 1, 0)) AS pttype_other
        FROM ipt i
        LEFT JOIN pttype p ON p.pttype = i.pttype
        WHERE i.dchdate IS NULL
    """
    r_rights = await db.execute(text(sql_rights))
    r_row = r_rights.mappings().first() or {}

    return {
        "total_beds": total_beds,
        "new_admit_today": new_admit_today,
        "discharge_today": discharge_today,
        "current_admit": current_admit,
        "available_beds": available_beds,
        "transfer_today": 0,
        "occupancy_rate": occupancy_rate,
        "pttype_pay": int(r_row.get("pttype_pay") or 0),
        "pttype_uc": int(r_row.get("pttype_uc") or 0),
        "pttype_other": int(r_row.get("pttype_other") or 0),
    }

@router.get("/income-summary", summary="สรุปค่าใช้จ่ายผู้ป่วยในรวม")
async def get_ipd_income_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql_income = """
        SELECT 
            i.income AS income_code,
            i.name AS income_name,
            COALESCE(SUM(o.sum_price), 0) AS total_amount
        FROM income i
        LEFT JOIN opitemrece o ON o.income = i.income 
                               AND o.an IS NOT NULL 
                               AND o.vstdate BETWEEN :start AND :end
        GROUP BY i.income, i.name
        ORDER BY i.income ASC
    """
    result = await db.execute(text(sql_income), {"start": start_date, "end": end_date})
    rows = result.mappings().all()

    income_dict = {r["income_code"]: float(r["total_amount"]) for r in rows}
    total_income = sum(income_dict.values())

    # Map to standard MoPH/HOSxP report income categories matching user's image
    categories_map = [
        {"code": "01", "name": "ค่าตรวจวินิจฉัยทางเทคนิคการแพทย์และพยาธิวิทยา,ค่าบริการโลหิตและส่วนประกอบของโลหิต", "amount": income_dict.get("06", 0.0) + income_dict.get("05", 0.0)},
        {"code": "04", "name": "ค่าตรวจวินิจฉัยและรักษาทางรังสีวิทยา", "amount": income_dict.get("07", 0.0)},
        {"code": "05", "name": "ค่าตรวจวินิจฉัยโดยวิธีพิเศษอื่นๆ,ค่าบริการทางการพยาบาล,ค่าใบรับรองแพทย์", "amount": income_dict.get("11", 0.0) + income_dict.get("10", 0.0) + income_dict.get("18", 0.0)},
        {"code": "06", "name": "ค่าผ่าตัด ทำคลอด ทำหัตถการและบริการวิสัญญี", "amount": income_dict.get("09", 0.0)},
        {"code": "07", "name": "ค่าบริการฝังเข็ม การบำบัดของผู้ประกอบโรคศิลปะอื่นๆ", "amount": income_dict.get("14", 0.0)},
        {"code": "08", "name": "ค่าอวัยวะเทียม อุปกรณ์ในการบำบัดรักษา", "amount": income_dict.get("02", 0.0)},
        {"code": "09", "name": "ค่าเวชภัณฑ์ที่ไม่ใช่ยา,ค่าอุปกรณ์เครื่องใช้และเครื่องมือทางการแพทย์", "amount": income_dict.get("04", 0.0) + income_dict.get("08", 0.0)},
        {"code": "11", "name": "ค่าบริการทางทันตกรรม", "amount": income_dict.get("12", 0.0)},
        {"code": "12", "name": "ค่ายาที่นำไปใช้ต่อที่บ้าน,ค่ายานอกบัญชียาหลักแห่งชาติ,ค่ายาในบัญชียาหลัก", "amount": income_dict.get("19", 0.0) + income_dict.get("80", 0.0) + income_dict.get("03", 0.0)},
        {"code": "13", "name": "ค่าบริการทางกายภาพบำบัด", "amount": income_dict.get("13", 0.0)},
        {"code": "14", "name": "ค่าบริการอื่นที่ไม่เกี่ยวข้องกับการรักษาพยาบาล", "amount": income_dict.get("16", 0.0)},
        {"code": "16", "name": "ค่าอาหาร,ค่าห้อง", "amount": income_dict.get("01", 0.0) + income_dict.get("00", 0.0)},
        {"code": "17", "name": "ค่าธรรมเนียมบัตรทอง 30 บาท,บริการอื่นๆและส่งเสริมป้องกัน", "amount": income_dict.get("17", 0.0) + income_dict.get("20", 0.0)},
    ]

    return {
        "fiscal_year": fiscal_year,
        "total_income": total_income,
        "items": categories_map
    }

