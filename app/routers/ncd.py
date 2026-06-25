from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(prefix="/ncd", tags=["Non-Communicable Diseases"])


async def get_sys_var(db: AsyncSession, name: str, default: str) -> str:
    try:
        res = await db.execute(text("SELECT sys_value FROM sys_var WHERE sys_name = :name"), {"name": name})
        val = res.scalar()
        return val if val else default
    except Exception:
        return default


@router.get("/stats-summary", summary="สรุปข้อมูลผู้ป่วยคลินิกโรคไม่ติดต่อแยกตามประเภทโรค")
async def get_ncd_stats_summary(
    db: AsyncSession = Depends(get_db),
):
    # Fetch configurations from sys_var
    dm_clinic = await get_sys_var(db, "dm_clinic_code", "001")
    ht_clinic = await get_sys_var(db, "ht_clinic_code", "002")
    copd_clinic = "043"  # COPD
    chwpart = await get_sys_var(db, "hos_chwpart", "65")
    amppart = await get_sys_var(db, "hos_amppart", "03")

    sql = """
        SELECT cm.clinic AS clinic, c.name AS ncdname, COUNT(*) AS ptotal
        FROM clinicmember cm
        LEFT OUTER JOIN clinic c ON c.clinic = cm.clinic
        LEFT OUTER JOIN patient p ON p.hn = cm.hn
        WHERE p.death <> 'Y' AND cm.clinic IN (:dm, :ht, :copd)
          AND cm.discharge <> 'Y' AND p.chwpart = :chw AND p.amppart = :amp
        GROUP BY cm.clinic, c.name

        UNION ALL

        SELECT 'cancer' AS clinic, 'มะเร็ง' AS ncdname, COUNT(*) AS ptotal
        FROM patient_cancer_registeration pc
        LEFT OUTER JOIN patient p ON p.hn = pc.hn
        WHERE pc.cancer_person_live_status_id <> '2'
          AND p.chwpart = :chw AND p.amppart = :amp
    """
    
    result = await db.execute(text(sql), {
        "dm": dm_clinic,
        "ht": ht_clinic,
        "copd": copd_clinic,
        "chw": chwpart,
        "amp": amppart
    })
    rows = result.mappings().all()
    return {"data": [dict(r) for r in rows]}


@router.get("/stats-age-breakdown", summary="ตารางร้อยละกลุ่มอายุผู้ป่วยเบาหวานและความดันโลหิตสูง")
async def get_ncd_stats_age_breakdown(
    db: AsyncSession = Depends(get_db),
):
    dm_clinic = await get_sys_var(db, "dm_clinic_code", "001")
    ht_clinic = await get_sys_var(db, "ht_clinic_code", "002")
    chwpart = await get_sys_var(db, "hos_chwpart", "65")
    amppart = await get_sys_var(db, "hos_amppart", "03")

    # DM SQL
    dm_sql = """
        SELECT 'เบาหวาน (DM)' AS clinic_type,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 0 AND 19 THEN 1 ELSE 0 END) AS age_0_19,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 20 AND 34 THEN 1 ELSE 0 END) AS age_20_34,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 35 AND 59 THEN 1 ELSE 0 END) AS age_35_59,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 60 AND 69 THEN 1 ELSE 0 END) AS age_60_69,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 70 AND 79 THEN 1 ELSE 0 END) AS age_70_79,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) >= 80 THEN 1 ELSE 0 END) AS age_80up,
               COUNT(*) AS total
        FROM clinicmember cm
        LEFT OUTER JOIN patient p ON p.hn = cm.hn
        WHERE p.chwpart = :chw AND p.amppart = :amp AND p.death <> 'Y' AND cm.discharge <> 'Y' AND cm.clinic = :dm
    """

    # HT SQL
    ht_sql = """
        SELECT 'ความดันโลหิตสูง (HT)' AS clinic_type,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 0 AND 19 THEN 1 ELSE 0 END) AS age_0_19,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 20 AND 34 THEN 1 ELSE 0 END) AS age_20_34,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 35 AND 59 THEN 1 ELSE 0 END) AS age_35_59,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 60 AND 69 THEN 1 ELSE 0 END) AS age_60_69,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) BETWEEN 70 AND 79 THEN 1 ELSE 0 END) AS age_70_79,
               SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) >= 80 THEN 1 ELSE 0 END) AS age_80up,
               COUNT(*) AS total
        FROM clinicmember cm
        LEFT OUTER JOIN patient p ON p.hn = cm.hn
        WHERE p.chwpart = :chw AND p.amppart = :amp AND p.death <> 'Y' AND cm.discharge <> 'Y' AND cm.clinic = :ht
    """

    dm_res = await db.execute(text(dm_sql), {"chw": chwpart, "amp": amppart, "dm": dm_clinic})
    ht_res = await db.execute(text(ht_sql), {"chw": chwpart, "amp": amppart, "ht": ht_clinic})

    return {
        "dm": dict(dm_res.mappings().first()),
        "ht": dict(ht_res.mappings().first())
    }


@router.get("/patients", summary="รายชื่อผู้รับบริการคลินิกโรคไม่ติดต่อรายปี", dependencies=[Depends(validate_api_key)])
async def get_ncd_patients(
    clinic: str = Query(..., description="ประเภทโรค: dm, ht, copd, cancer"),
    db: AsyncSession = Depends(get_db),
):
    dm_clinic = await get_sys_var(db, "dm_clinic_code", "001")
    ht_clinic = await get_sys_var(db, "ht_clinic_code", "002")
    copd_clinic = "043"
    chwpart = await get_sys_var(db, "hos_chwpart", "65")
    amppart = await get_sys_var(db, "hos_amppart", "03")

    if clinic == "cancer":
        sql = """
            SELECT pc.hn,
                   CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
                   CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
                   TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) AS age,
                   'มะเร็ง' AS disease,
                   pc.register_date AS vstdate
            FROM patient_cancer_registeration pc
            LEFT OUTER JOIN patient p ON p.hn = pc.hn
            LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
            WHERE pc.cancer_person_live_status_id <> '2'
              AND p.chwpart = :chw AND p.amppart = :amp
            ORDER BY pc.register_date DESC
            LIMIT 500
        """
        params = {"chw": chwpart, "amp": amppart}
    else:
        target_clinic = dm_clinic if clinic == "dm" else (ht_clinic if clinic == "ht" else copd_clinic)
        sql = """
            SELECT cm.hn,
                   CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
                   CONCAT(p.addrpart, ' ', p.road, ' ม.', p.moopart, ' ', t.full_name) AS address,
                   TIMESTAMPDIFF(YEAR, p.birthday, CURDATE()) AS age,
                   c.name AS disease,
                   cm.regdate AS vstdate
            FROM clinicmember cm
            LEFT OUTER JOIN clinic c ON c.clinic = cm.clinic
            LEFT OUTER JOIN patient p ON p.hn = cm.hn
            LEFT OUTER JOIN thaiaddress t ON t.addressid = CONCAT(p.chwpart, p.amppart, p.tmbpart)
            WHERE p.death <> 'Y' AND cm.clinic = :clinic
              AND cm.discharge <> 'Y' AND p.chwpart = :chw AND p.amppart = :amp
            ORDER BY cm.regdate DESC
            LIMIT 500
        """
        params = {"clinic": target_clinic, "chw": chwpart, "amp": amppart}

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"clinic": clinic, "data": [dict(r) for r in rows]}
