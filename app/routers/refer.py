from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from datetime import date
import logging

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(
    prefix="/refer",
    tags=["Referral"],
    dependencies=[Depends(validate_api_key)]
)

logger = logging.getLogger(__name__)

def get_fiscal_dates(fiscal_year: int):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"
    return start_date, end_date

@router.get("/summary", summary="สรุปตัวชี้วัดสำคัญการรับ-ส่งต่อ (Refer KPI Summary)")
async def get_refer_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    sql = """
        SELECT 
            (SELECT COUNT(*) FROM referout WHERE refer_date BETWEEN :start AND :end) AS total_referout,
            (SELECT COUNT(*) FROM referin WHERE refer_date BETWEEN :start AND :end) AS total_referin,
            (SELECT COUNT(*) FROM referout WHERE refer_date BETWEEN :start AND :end AND referout_emergency_type_id IN (1, 2)) AS emergency_cases
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    row = result.mappings().first() or {}

    total_out = int(row.get("total_referout") or 0)
    total_in = int(row.get("total_referin") or 0)
    emergency_cases = int(row.get("emergency_cases") or 0)

    return {
        "fiscal_year": fiscal_year,
        "total_refer": total_out + total_in,
        "total_referout": total_out,
        "total_referin": total_in,
        "emergency_cases": emergency_cases
    }

@router.get("/trends", summary="แนวโน้มการรับ-ส่งต่อ (รายเดือน / รายสัปดาห์ / รายช่วงเวลาหนาแน่น)")
async def get_refer_trends(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    mode: str = Query(default="monthly", description="monthly | weekly | hourly"),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    if mode == "weekly":
        sql_out = """
            SELECT DAYOFWEEK(refer_date) AS day_num, COUNT(*) AS count
            FROM referout
            WHERE refer_date BETWEEN :start AND :end AND refer_date > '2000-01-01'
            GROUP BY DAYOFWEEK(refer_date)
        """
        sql_in = """
            SELECT DAYOFWEEK(refer_date) AS day_num, COUNT(*) AS count
            FROM referin
            WHERE refer_date BETWEEN :start AND :end AND refer_date > '2000-01-01'
            GROUP BY DAYOFWEEK(refer_date)
        """
        res_out = await db.execute(text(sql_out), {"start": start_date, "end": end_date})
        res_in = await db.execute(text(sql_in), {"start": start_date, "end": end_date})

        dict_out = {r["day_num"]: r["count"] for r in res_out.mappings().all() if r["day_num"] is not None}
        dict_in = {r["day_num"]: r["count"] for r in res_in.mappings().all() if r["day_num"] is not None}

        days_map = [
            {"day": "จันทร์", "day_num": 2},
            {"day": "อังคาร", "day_num": 3},
            {"day": "พุธ", "day_num": 4},
            {"day": "พฤหัสบดี", "day_num": 5},
            {"day": "ศุกร์", "day_num": 6},
            {"day": "เสาร์", "day_num": 7},
            {"day": "อาทิตย์", "day_num": 1},
        ]
        data = [
            {
                "label": d["day"],
                "refer_out": int(dict_out.get(d["day_num"], 0)),
                "refer_in": int(dict_in.get(d["day_num"], 0))
            }
            for d in days_map
        ]
    elif mode == "hourly":
        sql_out = """
            SELECT CAST(SUBSTRING(refer_time, 1, 2) AS UNSIGNED) AS hr, COUNT(*) AS count
            FROM referout
            WHERE refer_date BETWEEN :start AND :end AND refer_time IS NOT NULL AND refer_time <> ''
            GROUP BY CAST(SUBSTRING(refer_time, 1, 2) AS UNSIGNED)
        """
        sql_in = """
            SELECT CAST(SUBSTRING(refer_time, 1, 2) AS UNSIGNED) AS hr, COUNT(*) AS count
            FROM referin
            WHERE refer_date BETWEEN :start AND :end AND refer_time IS NOT NULL AND refer_time <> ''
            GROUP BY CAST(SUBSTRING(refer_time, 1, 2) AS UNSIGNED)
        """
        res_out = await db.execute(text(sql_out), {"start": start_date, "end": end_date})
        res_in = await db.execute(text(sql_in), {"start": start_date, "end": end_date})

        dict_out = {r["hr"]: r["count"] for r in res_out.mappings().all() if r["hr"] is not None}
        dict_in = {r["hr"]: r["count"] for r in res_in.mappings().all() if r["hr"] is not None}

        data = [
            {
                "label": f"{h:02d}:00",
                "refer_out": int(dict_out.get(h, 0)),
                "refer_in": int(dict_in.get(h, 0))
            }
            for h in range(24)
        ]
    else: # monthly
        sql_out = """
            SELECT MONTH(refer_date) AS m, COUNT(*) AS count
            FROM referout
            WHERE refer_date BETWEEN :start AND :end
            GROUP BY MONTH(refer_date)
        """
        sql_in = """
            SELECT MONTH(refer_date) AS m, COUNT(*) AS count
            FROM referin
            WHERE refer_date BETWEEN :start AND :end
            GROUP BY MONTH(refer_date)
        """
        res_out = await db.execute(text(sql_out), {"start": start_date, "end": end_date})
        res_in = await db.execute(text(sql_in), {"start": start_date, "end": end_date})

        dict_out = {r["m"]: r["count"] for r in res_out.mappings().all() if r["m"] is not None}
        dict_in = {r["m"]: r["count"] for r in res_in.mappings().all() if r["m"] is not None}

        fiscal_months = [
            (10, "ต.ค."), (11, "พ.ย."), (12, "ธ.ค."),
            (1, "ม.ค."), (2, "ก.พ."), (3, "มี.ค."),
            (4, "เม.ย."), (5, "พ.ค."), (6, "มิ.ย."),
            (7, "ก.ค."), (8, "ส.ค."), (9, "ก.ย.")
        ]
        data = [
            {
                "label": label,
                "refer_out": int(dict_out.get(m, 0)),
                "refer_in": int(dict_in.get(m, 0))
            }
            for m, label in fiscal_months
        ]

    return {
        "fiscal_year": fiscal_year,
        "mode": mode,
        "data": data
    }

@router.get("/hospitals", summary="สัดส่วนโรงพยาบาลปลายทางส่งออก และโรงพยาบาลต้นทางรับเข้า")
async def get_refer_hospitals(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    # Fast Refer Out Hospitals
    sql_out = """
        SELECT hospcode, COUNT(*) AS count
        FROM referout
        WHERE refer_date BETWEEN :start AND :end AND hospcode IS NOT NULL AND hospcode <> ''
        GROUP BY hospcode
        ORDER BY count DESC
        LIMIT 8
    """
    res_out = await db.execute(text(sql_out), {"start": start_date, "end": end_date})
    out_rows = res_out.mappings().all()

    # Fast Refer In Hospitals
    sql_in = """
        SELECT hospcode, COUNT(*) AS count
        FROM referin
        WHERE refer_date BETWEEN :start AND :end AND hospcode IS NOT NULL AND hospcode <> ''
        GROUP BY hospcode
        ORDER BY count DESC
        LIMIT 8
    """
    res_in = await db.execute(text(sql_in), {"start": start_date, "end": end_date})
    in_rows = res_in.mappings().all()

    # Batch lookup hospcode names
    h_codes = list(set([r["hospcode"] for r in out_rows] + [r["hospcode"] for r in in_rows]))
    h_map = {}
    if h_codes:
        sql_names = "SELECT hospcode, name FROM hospcode WHERE hospcode IN :codes"
        res_names = await db.execute(text(sql_names), {"codes": tuple(h_codes)})
        h_map = {r["hospcode"]: r["name"] for r in res_names.mappings().all() if r["name"]}

    refer_out_hospitals = [
        {"hospcode": r["hospcode"], "name": h_map.get(r["hospcode"], r["hospcode"]), "count": int(r["count"])}
        for r in out_rows
    ]
    refer_in_hospitals = [
        {"hospcode": r["hospcode"], "name": h_map.get(r["hospcode"], r["hospcode"]), "count": int(r["count"])}
        for r in in_rows
    ]

    return {
        "fiscal_year": fiscal_year,
        "refer_out": refer_out_hospitals,
        "refer_in": refer_in_hospitals
    }

@router.get("/causes-icd10", summary="อันดับกลุ่มโรค Top 10 ICD-10 และสาเหตุการส่งต่อ")
async def get_refer_causes_and_icd10(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    # Top 10 ICD-10
    sql_icd10 = """
        SELECT 
            r.pdx,
            COALESCE(i.name, r.pdx) AS diag,
            COALESCE(i.tname, '') AS tname,
            COUNT(*) AS count
        FROM referout r
        LEFT JOIN icd101 i ON i.code = r.pdx
        WHERE r.refer_date BETWEEN :start AND :end AND r.pdx IS NOT NULL AND r.pdx <> ''
        GROUP BY r.pdx, i.name, i.tname
        ORDER BY count DESC
        LIMIT 10
    """
    res_icd10 = await db.execute(text(sql_icd10), {"start": start_date, "end": end_date})
    top_icd10 = [
        {
            "pdx": r["pdx"],
            "diag": r["diag"],
            "tname": (r["tname"] or "").strip(),
            "count": int(r["count"])
        }
        for r in res_icd10.mappings().all()
    ]

    # Refer Causes
    sql_causes = """
        SELECT 
            r.rfrcs,
            COALESCE(cs.name, 'ไม่ระบุสาเหตุ') AS cause_name,
            COUNT(*) AS count
        FROM referout r
        LEFT JOIN rfrcs cs ON cs.rfrcs = r.rfrcs
        WHERE r.refer_date BETWEEN :start AND :end
        GROUP BY r.rfrcs, cs.name
        ORDER BY count DESC
        LIMIT 8
    """
    res_causes = await db.execute(text(sql_causes), {"start": start_date, "end": end_date})
    refer_causes = [
        {"code": r["rfrcs"] or "-", "name": r["cause_name"], "count": int(r["count"])}
        for r in res_causes.mappings().all()
    ]

    return {
        "fiscal_year": fiscal_year,
        "top_icd10": top_icd10,
        "refer_causes": refer_causes
    }

@router.get("/triage-levels", summary="ระดับความเร่งด่วนของการส่งต่อ (Triage / Emergency Levels)")
async def get_refer_triage_levels(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    sql = """
        SELECT 
            r.referout_emergency_type_id AS type_id,
            COALESCE(e.referout_emergency_type_name, 'ทั่วไป / ไม่ระบุ') AS type_name,
            COUNT(*) AS count
        FROM referout r
        LEFT JOIN referout_emergency_type e ON e.referout_emergency_type_id = r.referout_emergency_type_id
        WHERE r.refer_date BETWEEN :start AND :end
        GROUP BY r.referout_emergency_type_id, e.referout_emergency_type_name
        ORDER BY 
            CASE 
                WHEN r.referout_emergency_type_id = 1 THEN 1
                WHEN r.referout_emergency_type_id = 2 THEN 2
                WHEN r.referout_emergency_type_id = 3 THEN 3
                WHEN r.referout_emergency_type_id = 4 THEN 4
                WHEN r.referout_emergency_type_id = 5 THEN 5
                ELSE 6
            END ASC
    """
    res = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = res.mappings().all()

    color_map = {
        1: "#d9534f", # Life threatening - Red
        2: "#f0ad4e", # Emergency - Orange
        3: "#ffd15c", # Urgent - Yellow
        4: "#5cb85c", # Acute - Green
        5: "#0275d8", # Non acute - Blue
    }

    triage_data = [
        {
            "type_id": r["type_id"],
            "type_name": r["type_name"],
            "count": int(r["count"]),
            "color": color_map.get(r["type_id"], "#6c757d")
        }
        for r in rows
    ]

    return {
        "fiscal_year": fiscal_year,
        "triage_levels": triage_data
    }

@router.get("/referout-list", summary="รายชื่อเคสส่งต่อ (Refer Out Cases List)")
async def get_referout_list(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date = get_fiscal_dates(fiscal_year)

    # 1. Fetch top 50 recent referout cases
    sql = """
        SELECT 
            r.referout_id,
            DATE_FORMAT(r.refer_date, '%Y-%m-%d') AS refer_date,
            COALESCE(r.refer_time, '-') AS refer_time,
            r.hn,
            r.hospcode,
            r.pdx,
            r.rfrcs,
            r.referout_emergency_type_id
        FROM referout r
        WHERE r.refer_date BETWEEN :start AND :end
        ORDER BY r.refer_date DESC, r.referout_id DESC
        LIMIT 50
    """
    res = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = res.mappings().all()

    if not rows:
        return {"fiscal_year": fiscal_year, "data": []}

    # 2. Extract keys for batch lookup
    hn_list = tuple(set(r["hn"] for r in rows if r["hn"]))
    hosp_list = tuple(set(r["hospcode"] for r in rows if r["hospcode"]))
    pdx_list = tuple(set(r["pdx"] for r in rows if r["pdx"]))
    rfrcs_list = tuple(set(r["rfrcs"] for r in rows if r["rfrcs"]))
    em_list = tuple(set(r["referout_emergency_type_id"] for r in rows if r["referout_emergency_type_id"]))

    pt_map = {}
    if hn_list:
        res_pt = await db.execute(text("SELECT hn, CONCAT(COALESCE(pname,''), fname, ' ', lname) as name FROM patient WHERE hn IN :hns"), {"hns": hn_list})
        pt_map = {r["hn"]: r["name"] for r in res_pt.mappings().all()}

    hosp_map = {}
    if hosp_list:
        res_hosp = await db.execute(text("SELECT hospcode, name FROM hospcode WHERE hospcode IN :codes"), {"codes": hosp_list})
        hosp_map = {r["hospcode"]: r["name"] for r in res_hosp.mappings().all() if r["name"]}

    diag_map = {}
    if pdx_list:
        res_diag = await db.execute(text("SELECT code, name FROM icd101 WHERE code IN :codes"), {"codes": pdx_list})
        diag_map = {r["code"]: r["name"] for r in res_diag.mappings().all()}

    cause_map = {}
    if rfrcs_list:
        res_cause = await db.execute(text("SELECT rfrcs, name FROM rfrcs WHERE rfrcs IN :codes"), {"codes": rfrcs_list})
        cause_map = {r["rfrcs"]: r["name"] for r in res_cause.mappings().all()}

    em_map = {}
    if em_list:
        res_em = await db.execute(text("SELECT referout_emergency_type_id, referout_emergency_type_name FROM referout_emergency_type WHERE referout_emergency_type_id IN :codes"), {"codes": em_list})
        em_map = {r["referout_emergency_type_id"]: r["referout_emergency_type_name"] for r in res_em.mappings().all()}

    result_data = [
        {
            "referout_id": r["referout_id"],
            "refer_date": r["refer_date"],
            "refer_time": r["refer_time"],
            "hn": r["hn"],
            "pt_name": pt_map.get(r["hn"], "-"),
            "dest_hospname": hosp_map.get(r["hospcode"], r["hospcode"] or "-"),
            "pdx": r["pdx"] or "-",
            "diag": diag_map.get(r["pdx"], "-"),
            "cause_name": cause_map.get(r["rfrcs"], "ไม่ระบุ"),
            "emergency_name": em_map.get(r["referout_emergency_type_id"], "ทั่วไป")
        }
        for r in rows
    ]

    return {
        "fiscal_year": fiscal_year,
        "data": result_data
    }
