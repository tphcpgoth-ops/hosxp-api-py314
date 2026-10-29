from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import date, datetime
import re

from app.core.database import get_db

router = APIRouter(prefix="/enrichment", tags=["Enrichment"])


class LookupItem(BaseModel):
    hn: str
    vstdate: Optional[str] = None
    row_id: Optional[Any] = None


class BatchLookupRequest(BaseModel):
    items: List[LookupItem] = Field(..., max_length=1000)
    auto_pad_hn: bool = True
    hn_length: int = 9
    fallback_to_latest_if_date_not_found: bool = False


THAI_MONTHS = {
    "ม.ค.": 1, "มกราคม": 1, "ก.พ.": 2, "กุมภาพันธ์": 2,
    "มี.ค.": 3, "มีนาคม": 3, "เม.ย.": 4, "เมษายน": 4,
    "พ.ค.": 5, "พฤษภาคม": 5, "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7, "กรกฎาคม": 7, "ส.ค.": 8, "สิงหาคม": 8,
    "ก.ย.": 9, "กันยายน": 9, "ต.ค.": 10, "ตุลาคม": 10,
    "พ.ย.": 11, "พฤศจิกายน": 11, "ธ.ค.": 12, "ธันวาคม": 12,
}


def normalize_hn(hn: str, auto_pad: bool = True, length: int = 9) -> str:
    cleaned = str(hn).strip()
    if auto_pad and cleaned.isdigit() and len(cleaned) < length:
        return cleaned.zfill(length)
    return cleaned


def parse_vstdate(val: Optional[Any]) -> Optional[str]:
    """
    แปลงวันที่หลากหลายรูปแบบเป็น YYYY-MM-DD (ค.ศ.)
    รองรับ:
    - Excel Serial Number (เช่น 45580, 45580.0)
    - วันที่แบบ พ.ศ. / ค.ศ. (เช่น 15/10/2567, 15/10/2024, 2567-10-15)
    - วันที่คั่นด้วย -, /, . (เช่น 15.10.2567, 1-10-2567)
    - ปี พ.ศ. 2 หลัก (เช่น 15/10/67, 15/10/24)
    - YYYYMMDD 8 หลัก (เช่น 25671015, 20241015)
    - ชื่อเดือนภาษาไทย (เช่น 15 ต.ค. 2567, 15 ตุลาคม 2567)
    - ISO datetime / timestamp (เช่น 2024-10-15T08:30:00, 2024-10-15 08:30:00)
    """
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None

    # ตัด T หรือ ช่องว่างเพื่อเอาเฉพาะส่วนวันที่ (ถ้ามีเวลาติดมา)
    val_str = val_str.replace("T", " ")
    date_part = val_str.split(" ")[0].strip()

    # 1. เช็ค Excel Serial Number (เช่น 45580 หรือ 45580.354)
    try:
        f_val = float(date_part)
        # Excel date serial 20000 (1954) ถึง 90000 (2146)
        if 20000 <= f_val <= 90000:
            d = datetime(1899, 12, 30) + timedelta(days=int(f_val))
            return d.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # แทนที่ separator ต่างๆ ด้วย '-'
    cleaned = date_part.replace("/", "-").replace(".", "-")

    # 2. รูปแบบ YYYY-MM-DD (อาจเป็น ค.ศ. หรือ พ.ศ.)
    m_ymd = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if m_ymd:
        y, m, d = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
        if y > 2400:  # พ.ศ.
            y -= 543
        try:
            return date(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 3. รูปแบบ DD-MM-YYYY (หรือ MM-DD-YYYY ถ้าเดือน > 12)
    m_dmy = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", cleaned)
    if m_dmy:
        d, m, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        if m > 12 and d <= 12:
            d, m = m, d
        if y > 2400:
            y -= 543
        try:
            return date(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 4. รูปแบบปี 2 หลัก เช่น DD-MM-YY (15-10-67 หรือ 15-10-24)
    m_dmy2 = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{2})$", cleaned)
    if m_dmy2:
        d, m, y_short = int(m_dmy2.group(1)), int(m_dmy2.group(2)), int(m_dmy2.group(3))
        if m > 12 and d <= 12:
            d, m = m, d
        if y_short >= 50:  # เช่น 67 -> 2567 -> 2024
            y = (2500 + y_short) - 543
        else:  # เช่น 24 -> 2024
            y = 2000 + y_short
        try:
            return date(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 5. รูปแบบ 8 หลัก YYYYMMDD
    m_8 = re.match(r"^(\d{4})(\d{2})(\d{2})$", cleaned)
    if m_8:
        y, m, d = int(m_8.group(1)), int(m_8.group(2)), int(m_8.group(3))
        if y > 2400:
            y -= 543
        try:
            return date(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 6. รูปแบบชื่อเดือนภาษาไทย เช่น '15 ต.ค. 2567', '15 ตุลาคม 2567', '15 ต.ค. 67'
    for th_month, m_num in THAI_MONTHS.items():
        if th_month in val_str:
            parts = re.findall(r"\d+", val_str)
            if len(parts) >= 2:
                d = int(parts[0])
                y_raw = int(parts[1])
                if y_raw > 2400:
                    y = y_raw - 543
                elif 50 <= y_raw < 100:
                    y = (2500 + y_raw) - 543
                elif y_raw < 50:
                    y = 2000 + y_raw
                else:
                    y = y_raw
                try:
                    return date(y, m_num, d).strftime("%Y-%m-%d")
                except ValueError:
                    pass

    return None


def calculate_age(bday: Optional[date], at_date: Optional[date] = None) -> Optional[int]:
    if not bday:
        return None
    ref = at_date or date.today()
    age = ref.year - bday.year
    if (ref.month, ref.day) < (bday.month, bday.day):
        age -= 1
    return max(0, age)


@router.post("/batch-lookup", summary="ดึงข้อมูลผู้ป่วยและ Visit แบบกลุ่มจาก HOSxP")
async def batch_lookup(
    payload: BatchLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    if not payload.items:
        return {"total_requested": 0, "total_matched": 0, "total_not_found": 0, "results": []}

    # แปลงและจัดกลุ่มข้อมูล Input
    normalized_items = []
    hn_set = set()
    vstdate_queries = []  # items with specific vstdate
    latest_hn_set = set() # items needing latest visit

    for item in payload.items:
        norm_hn = normalize_hn(item.hn, payload.auto_pad_hn, payload.hn_length)
        norm_date = parse_vstdate(item.vstdate)
        
        normalized_items.append({
            "original_hn": item.hn,
            "original_vstdate": item.vstdate,
            "row_id": item.row_id,
            "hn": norm_hn,
            "vstdate": norm_date,
        })
        hn_set.add(norm_hn)
        if norm_date:
            vstdate_queries.append((norm_hn, norm_date))
            if payload.fallback_to_latest_if_date_not_found:
                latest_hn_set.add(norm_hn)
        else:
            latest_hn_set.add(norm_hn)

    hn_list = list(hn_set)
    if not hn_list:
        return {"total_requested": len(payload.items), "total_matched": 0, "total_not_found": len(payload.items), "results": []}

    # ─────────────────────────────────────────────────────────────
    # 1. ดึงข้อมูลผู้ป่วย (patient + thaiaddress)
    # ─────────────────────────────────────────────────────────────
    patient_sql = text("""
        SELECT 
            p.hn, p.cid, p.pname, p.fname, p.lname, p.sex, p.birthday, p.bloodgrp, p.drugallergy,
            p.addrpart, p.moopart, p.tmbpart, p.amppart, p.chwpart, p.hometel, p.informtel,
            ta.full_name AS address_full
        FROM patient p
        LEFT JOIN thaiaddress ta ON ta.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
        WHERE p.hn IN :hns
    """)

    patient_res = await db.execute(patient_sql, {"hns": hn_list})
    patient_rows = patient_res.mappings().all()
    patient_map: Dict[str, dict] = {}

    for row in patient_rows:
        r = dict(row)
        sex_text = "ชาย" if r.get("sex") == "1" else ("หญิง" if r.get("sex") == "2" else "")
        bday = r.get("birthday")
        bday_str = bday.isoformat() if hasattr(bday, "isoformat") else (str(bday) if bday else "")
        
        # ประกอบที่อยู่เต็ม
        addr_parts = []
        if r.get("addrpart"):
            addr_parts.append(f"บ้านเลขที่ {r['addrpart']}")
        if r.get("moopart") and str(r["moopart"]).strip() not in ("", "0"):
            addr_parts.append(f"หมู่ {r['moopart']}")
        if r.get("address_full"):
            addr_parts.append(r["address_full"])
        full_addr = " ".join(addr_parts)

        patient_map[r["hn"]] = {
            "hn": r["hn"],
            "cid": r.get("cid") or "",
            "pname": r.get("pname") or "",
            "fname": r.get("fname") or "",
            "lname": r.get("lname") or "",
            "fullname": f"{r.get('pname','')}{r.get('fname','')} {r.get('lname','')}".strip(),
            "sex": sex_text,
            "birthday": bday_str,
            "age_now": calculate_age(bday) if bday else None,
            "bloodgrp": r.get("bloodgrp") or "",
            "drugallergy": r.get("drugallergy") or "",
            "hometel": r.get("hometel") or "",
            "informtel": r.get("informtel") or "",
            "addrpart": r.get("addrpart") or "",
            "moopart": r.get("moopart") or "",
            "tmbpart": r.get("tmbpart") or "",
            "amppart": r.get("amppart") or "",
            "chwpart": r.get("chwpart") or "",
            "address": full_addr,
        }

    # ─────────────────────────────────────────────────────────────
    # 2. ดึงข้อมูล Visit ตามวันที่ระบุ (hn + vstdate)
    # ─────────────────────────────────────────────────────────────
    visit_by_date_map: Dict[tuple, dict] = {}
    if vstdate_queries:
        dates_set = list(set([d for _, d in vstdate_queries]))
        hns_with_dates = list(set([h for h, _ in vstdate_queries]))

        visit_sql = text("""
            SELECT 
                o.hn, o.vstdate, o.vn, o.an, o.vsttime,
                d.department AS department_name, doc.name AS doctor_name, pt.name AS pttype_name,
                v.age_y, v.pdx, icd.name AS pdx_name, v.dx0, v.dx1, v.dx2, v.dx3, v.dx4, v.dx5,
                v.income, v.paid_money,
                s.bps, s.bpd, s.pulse, s.rr, s.temperature, s.bw, s.height, s.bmi, s.cc
            FROM ovst o
            LEFT JOIN vn_stat v ON v.vn = o.vn
            LEFT JOIN opdscreen s ON s.vn = o.vn
            LEFT JOIN kskdepartment d ON d.depcode = o.main_dep
            LEFT JOIN doctor doc ON doc.code = o.doctor
            LEFT JOIN pttype pt ON pt.pttype = o.pttype
            LEFT JOIN icd101 icd ON icd.code = v.pdx
            WHERE o.hn IN :hns AND o.vstdate IN :dates
            ORDER BY o.vn DESC
        """)

        v_res = await db.execute(visit_sql, {"hns": hns_with_dates, "dates": dates_set})
        for row in v_res.mappings().all():
            vr = dict(row)
            vdate_str = vr["vstdate"].isoformat() if hasattr(vr["vstdate"], "isoformat") else str(vr["vstdate"])
            key = (vr["hn"], vdate_str)
            # ถ้ามีหลาย visit ในวันเดียวกัน ให้เก็บ visit ล่าสุด (vn มากสุด)
            if key not in visit_by_date_map:
                bp_str = f"{int(vr['bps'])}/{int(vr['bpd'])}" if vr.get("bps") and vr.get("bpd") else ""
                visit_by_date_map[key] = {
                    "vn": vr.get("vn") or "",
                    "an": vr.get("an") or "",
                    "vstdate": vdate_str,
                    "vsttime": str(vr.get("vsttime") or ""),
                    "department_name": vr.get("department_name") or "",
                    "doctor_name": vr.get("doctor_name") or "",
                    "pttype_name": vr.get("pttype_name") or "",
                    "age_at_visit": vr.get("age_y"),
                    "pdx": vr.get("pdx") or "",
                    "pdx_name": vr.get("pdx_name") or "",
                    "dx0": vr.get("dx0") or "",
                    "dx1": vr.get("dx1") or "",
                    "dx2": vr.get("dx2") or "",
                    "dx3": vr.get("dx3") or "",
                    "dx4": vr.get("dx4") or "",
                    "dx5": vr.get("dx5") or "",
                    "income": float(vr["income"]) if vr.get("income") is not None else None,
                    "paid_money": float(vr["paid_money"]) if vr.get("paid_money") is not None else None,
                    "bps": vr.get("bps"),
                    "bpd": vr.get("bpd"),
                    "bp": bp_str,
                    "pulse": vr.get("pulse"),
                    "rr": vr.get("rr"),
                    "temperature": vr.get("temperature"),
                    "bw": vr.get("bw"),
                    "height": vr.get("height"),
                    "bmi": round(float(vr["bmi"]), 2) if vr.get("bmi") is not None else None,
                    "cc": (vr.get("cc") or "").strip(),
                }

    # ─────────────────────────────────────────────────────────────
    # 3. ดึงข้อมูล Visit ล่าสุด สำหรับ HN ที่ไม่มี vstdate หรือหาตามวันไม่เจอ
    # ─────────────────────────────────────────────────────────────
    latest_visit_map: Dict[str, dict] = {}
    if latest_hn_set:
        latest_sql = text("""
            SELECT 
                o.hn, o.vstdate, o.vn, o.an, o.vsttime,
                d.department AS department_name, doc.name AS doctor_name, pt.name AS pttype_name,
                v.age_y, v.pdx, icd.name AS pdx_name, v.dx0, v.dx1, v.dx2, v.dx3, v.dx4, v.dx5,
                v.income, v.paid_money,
                s.bps, s.bpd, s.pulse, s.rr, s.temperature, s.bw, s.height, s.bmi, s.cc
            FROM ovst o
            INNER JOIN (
                SELECT hn, MAX(vn) AS max_vn FROM ovst WHERE hn IN :hns GROUP BY hn
            ) latest ON latest.max_vn = o.vn
            LEFT JOIN vn_stat v ON v.vn = o.vn
            LEFT JOIN opdscreen s ON s.vn = o.vn
            LEFT JOIN kskdepartment d ON d.depcode = o.main_dep
            LEFT JOIN doctor doc ON doc.code = o.doctor
            LEFT JOIN pttype pt ON pt.pttype = o.pttype
            LEFT JOIN icd101 icd ON icd.code = v.pdx
        """)

        lv_res = await db.execute(latest_sql, {"hns": list(latest_hn_set)})
        for row in lv_res.mappings().all():
            vr = dict(row)
            vdate_str = vr["vstdate"].isoformat() if hasattr(vr["vstdate"], "isoformat") else str(vr["vstdate"])
            bp_str = f"{int(vr['bps'])}/{int(vr['bpd'])}" if vr.get("bps") and vr.get("bpd") else ""
            latest_visit_map[vr["hn"]] = {
                "vn": vr.get("vn") or "",
                "an": vr.get("an") or "",
                "vstdate": vdate_str,
                "vsttime": str(vr.get("vsttime") or ""),
                "department_name": vr.get("department_name") or "",
                "doctor_name": vr.get("doctor_name") or "",
                "pttype_name": vr.get("pttype_name") or "",
                "age_at_visit": vr.get("age_y"),
                "pdx": vr.get("pdx") or "",
                "pdx_name": vr.get("pdx_name") or "",
                "dx0": vr.get("dx0") or "",
                "dx1": vr.get("dx1") or "",
                "dx2": vr.get("dx2") or "",
                "dx3": vr.get("dx3") or "",
                "dx4": vr.get("dx4") or "",
                "dx5": vr.get("dx5") or "",
                "income": float(vr["income"]) if vr.get("income") is not None else None,
                "paid_money": float(vr["paid_money"]) if vr.get("paid_money") is not None else None,
                "bps": vr.get("bps"),
                "bpd": vr.get("bpd"),
                "bp": bp_str,
                "pulse": vr.get("pulse"),
                "rr": vr.get("rr"),
                "temperature": vr.get("temperature"),
                "bw": vr.get("bw"),
                "height": vr.get("height"),
                "bmi": round(float(vr["bmi"]), 2) if vr.get("bmi") is not None else None,
                "cc": (vr.get("cc") or "").strip(),
            }

    # ─────────────────────────────────────────────────────────────
    # 4. ประกอบผลลัพธ์คืนตามลำดับของ Input
    # ─────────────────────────────────────────────────────────────
    results = []
    matched_count = 0

    for item in normalized_items:
        hn = item["hn"]
        vdate = item["vstdate"]
        patient = patient_map.get(hn)
        visit = None
        match_type = "not_found"

        if patient:
            matched_count += 1
            if vdate:
                # ผู้ใช้ระบุวันที่ค้นหา: ต้องตรงกับวันที่ตรวจจริง
                if (hn, vdate) in visit_by_date_map:
                    visit = visit_by_date_map[(hn, vdate)]
                    match_type = "exact_visit"
                elif payload.fallback_to_latest_if_date_not_found and hn in latest_visit_map:
                    visit = latest_visit_map[hn]
                    match_type = "fallback_latest_visit"
                else:
                    visit = None
                    match_type = "date_not_found"
            else:
                # ผู้ใช้ไม่ได้ระบุวันที่: ดึง visit ล่าสุด
                if hn in latest_visit_map:
                    visit = latest_visit_map[hn]
                    match_type = "latest_visit"
                else:
                    match_type = "patient_only"

        results.append({
            "row_id": item["row_id"],
            "original_hn": item["original_hn"],
            "original_vstdate": item["original_vstdate"],
            "query_hn": hn,
            "query_vstdate": vdate,
            "matched": patient is not None,
            "match_type": match_type,
            "patient": patient,
            "visit": visit,
            "latest_visit": latest_visit_map.get(hn),
        })

    return {
        "total_requested": len(payload.items),
        "total_matched": matched_count,
        "total_not_found": len(payload.items) - matched_count,
        "results": results,
    }
