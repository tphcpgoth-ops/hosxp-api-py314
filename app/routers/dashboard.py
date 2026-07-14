from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
import time
from typing import Dict, Any

from app.core.database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Simple in-memory cache for HOSxP dashboard statistics
_dashboard_cache: Dict[str, Any] = {}
_disease_stats_cache: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 60

@router.get("/summary", summary="สรุปข้อมูล Dashboard สำหรับหน้าหลัก")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    force_refresh: bool = Query(False, description="บังคับรีเฟรชข้อมูลใหม่จากฐานข้อมูลตรงๆ")
):
    global _dashboard_cache
    now = time.time()
    
    # Check cache validity
    if not force_refresh and "data" in _dashboard_cache:
        elapsed = now - _dashboard_cache["timestamp"]
        if elapsed < CACHE_TTL_SECONDS:
            return _dashboard_cache["data"]
    # 1. OPD Stats
    opd_sql = """
        SELECT 
            COUNT(DISTINCT IF(main_dep = '085',vn,NULL)) AS ptm_pcc_vn,
            COUNT(DISTINCT IF(main_dep = '085',hn,NULL)) AS ptm_pcc_hn,
            COUNT(DISTINCT IF(main_dep = '085' AND vstdate = CURDATE(),vn,NULL)) AS ptm_pcc_today,
            COUNT(DISTINCT hn) AS ptm_opd_hn,
            COUNT(DISTINCT vn) AS ptm_opd_vn,
            COUNT(DISTINCT IF(vstdate = CURDATE(),vn,NULL)) AS pt_opd_today
        FROM ovst
        WHERE vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 2. Physical Therapy
    phy_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_phy_hn,COUNT(DISTINCT vn) AS ptm_phy_vn,
            COUNT(DISTINCT IF(vstdate = CURDATE(),vn,NULL)) AS pt_phy_today
        FROM physic_main
        WHERE vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 3. IPD Stats
    ipd_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_ipd_hn,COUNT(DISTINCT an) AS ptm_ipd_an,
            COUNT(DISTINCT IF(regdate = CURDATE(),an,NULL)) AS pt_ipd_today
        FROM ipt
        WHERE regdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 4. Dental
    dent_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_dent_hn,COUNT(DISTINCT vn) AS ptm_dent_vn,
            COUNT(DISTINCT IF(vstdate = CURDATE(),vn,NULL)) AS pt_dent_today
        FROM dtmain
        WHERE vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 5. Thai Medicine
    ttm_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_ttm_hn,COUNT(*) AS ptm_ttm_vn,
            COUNT(DISTINCT IF(service_date = CURDATE(),vn,NULL)) AS pt_ttm_today
        FROM health_med_service
        WHERE service_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 6. ER (Accident)
    er_sql = """
        SELECT COUNT(DISTINCT o.hn) AS ptm_er_hn,COUNT(DISTINCT o.vn) AS ptm_er_vn,
            COUNT(DISTINCT IF(er.vstdate = CURDATE(),o.vn,NULL)) AS pt_er_today
        FROM er_regist er 
        LEFT OUTER JOIN ovst o ON o.vn = er.vn
        WHERE er.vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
        AND er.er_pt_type IN (SELECT er_pt_type FROM er_pt_type WHERE accident_code = 'Y')
    """
    
    # 7. OR (Surgery)
    or_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_or_hn, COUNT(hn) AS ptm_or_vn,
            COUNT(IF(patient_department = 'OPD',vn,NULL)) AS ptm_or_opd,
            COUNT(IF(patient_department = 'IPD',an,NULL)) AS ptm_or_ipd,
            COUNT(IF(operation_date = CURDATE(),hn,NULL)) AS pt_or_today
        FROM operation_list
        WHERE operation_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 8. X-Ray
    xray_sql = """
        SELECT COUNT(DISTINCT hn) AS ptm_xray_hn,COUNT(vn) AS ptm_xray_vn,
            COUNT(IF(examined_date = CURDATE(),vn,NULL)) AS pt_xray_today
        FROM xray_report
        WHERE examined_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
    """
    
    # 9. IPD Ward Summary
    ward_sum_sql = """
        SELECT COUNT(*) AS wtotal,
            (SELECT SUM(bedcount) FROM ward WHERE ward_active = 'Y')-COUNT(*) AS wblank,
            (SELECT SUM(bedcount) FROM ward WHERE ward_active = 'Y') AS bedcount
        FROM ipt WHERE dchdate IS NULL
    """
    
    ipd_today_sql = """
        SELECT 
            COUNT(IF(regdate = CURDATE(),an,NULL)) AS admittoday,
            (SELECT COUNT(*) FROM ipt WHERE dchdate = CURDATE()) AS dchtoday
        FROM ipt
    """
    
    # 10. Ward List
    wards_sql = """
        SELECT w.ward,w.name,w.bedcount,COUNT(i.an) AS admitnow
        FROM ward w
        LEFT OUTER JOIN ipt i ON i.ward = w.ward AND i.dchdate IS NULL
        WHERE w.ward_active = 'Y'
        GROUP BY w.ward, w.name, w.bedcount
        ORDER BY w.ward ASC
    """

    # 11. Psychiatry (Clinic 109)
    psy_sql = """
        SELECT COUNT(DISTINCT c.hn) AS ptm_psy_hn, COUNT(DISTINCT c.vn) AS ptm_psy_vn,
            COUNT(DISTINCT IF(o.vstdate = CURDATE(),c.vn,NULL)) AS pt_psy_today
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        WHERE o.vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
        AND c.clinic = '109'
    """
    
    # 12. Drug / Narcotic (Clinic 130)
    drug_sql = """
        SELECT COUNT(DISTINCT c.hn) AS ptm_drug_hn, COUNT(DISTINCT c.vn) AS ptm_drug_vn,
            COUNT(DISTINCT IF(o.vstdate = CURDATE(),c.vn,NULL)) AS pt_drug_today
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        WHERE o.vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()
        AND c.clinic = '130'
    """

    # 13. Refer In/Out
    refer_sql = """
        SELECT 
            (SELECT COUNT(DISTINCT hn) FROM referin WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_in_hn,
            (SELECT COUNT(DISTINCT hn) FROM referout WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_out_hn,
            (SELECT COUNT(*) FROM referin WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_in_vn,
            (SELECT COUNT(*) FROM referout WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_out_vn,
            (SELECT COUNT(*) FROM referin WHERE refer_date = CURDATE()) AS pt_refer_in_today,
            (SELECT COUNT(*) FROM referout WHERE refer_date = CURDATE()) AS pt_refer_out_today
    """

    # 14. Top Stats (Appointments, Waiting Service, Waiting Doctor)
    sql_app = "SELECT COUNT(DISTINCT hn) AS total_app, COUNT(DISTINCT IF(hn IN (SELECT hn FROM ovst WHERE vstdate=CURDATE()), hn, NULL)) AS visited_app FROM oapp WHERE nextdate=CURDATE()"
    sql_opd_top = "SELECT COUNT(*) AS total_opd, COUNT(IF(ovstost='99',1,NULL)) AS completed_opd FROM ovst WHERE vstdate=CURDATE()"
    sql_wait = "SELECT COUNT(*) AS total_waiting_doctor, COUNT(IF(cur_dep='011',1,NULL)) AS er_waiting_doctor FROM ovst WHERE vstdate=CURDATE() AND ovstost='00'"

    # Execute all
    opd = (await db.execute(text(opd_sql))).mappings().first()
    phy = (await db.execute(text(phy_sql))).mappings().first()
    ipd = (await db.execute(text(ipd_sql))).mappings().first()
    dent = (await db.execute(text(dent_sql))).mappings().first()
    ttm = (await db.execute(text(ttm_sql))).mappings().first()
    er = (await db.execute(text(er_sql))).mappings().first()
    or_data = (await db.execute(text(or_sql))).mappings().first()
    xray = (await db.execute(text(xray_sql))).mappings().first()
    ward_summary = (await db.execute(text(ward_sum_sql))).mappings().first()
    ipd_today = (await db.execute(text(ipd_today_sql))).mappings().first()
    wards = (await db.execute(text(wards_sql))).mappings().all()
    psy = (await db.execute(text(psy_sql))).mappings().first()
    drug = (await db.execute(text(drug_sql))).mappings().first()
    refer = (await db.execute(text(refer_sql))).mappings().first()

    app_res = (await db.execute(text(sql_app))).mappings().first()
    opd_res = (await db.execute(text(sql_opd_top))).mappings().first()
    wait_res = (await db.execute(text(sql_wait))).mappings().first()

    total_app = app_res["total_app"] or 0 if app_res else 0
    visited_app = app_res["visited_app"] or 0 if app_res else 0
    pending_app = max(0, total_app - visited_app)

    total_opd_top = opd_res["total_opd"] or 0 if opd_res else 0
    completed_opd = opd_res["completed_opd"] or 0 if opd_res else 0
    waiting_service = max(0, total_opd_top - completed_opd)

    total_wait = wait_res["total_waiting_doctor"] or 0 if wait_res else 0
    er_wait = wait_res["er_waiting_doctor"] or 0 if wait_res else 0
    opd_wait = max(0, total_wait - er_wait)

    top_stats = [
        {
            "title": "ผู้ป่วยนัดวันนี้",
            "icon": "tabler:calendar-week",
            "count": str(total_app),
            "isDot": True,
            "isLabel": "วันนี้",
            "details": [
                {"title": "มารับบริการแล้ว", "count": str(visited_app)},
                {"title": "ยังไม่มารับบริการ", "count": str(pending_app)}
            ]
        },
        {
            "title": "ผู้ป่วยรอรับบริการขณะนี้",
            "icon": "tabler:users",
            "count": str(waiting_service),
            "isDot": True,
            "isLabel": "Realtime",
            "details": [
                {"title": "ผู้ป่วยวันนี้ทั้งหมด", "count": str(total_opd_top)},
                {"title": "รับบริการเสร็จสิ้น", "count": str(completed_opd)}
            ]
        },
        {
            "title": "ผู้ป่วยรอตรวจ",
            "icon": "tabler:stethoscope",
            "count": str(total_wait),
            "isDot": True,
            "isLabel": "รอตรวจแพทย์",
            "details": [
                {"title": "ผู้ป่วยนอก (OPD)", "count": str(opd_wait)},
                {"title": "ผู้ป่วยฉุกเฉิน (ER)", "count": str(er_wait)}
            ]
        }
    ]

    result = {
        "stats": {
            "opd": dict(opd) if opd else {},
            "phy": dict(phy) if phy else {},
            "ipd": dict(ipd) if ipd else {},
            "dent": dict(dent) if dent else {},
            "ttm": dict(ttm) if ttm else {},
            "er": dict(er) if er else {},
            "or": dict(or_data) if or_data else {},
            "xray": dict(xray) if xray else {},
            "ward_summary": dict(ward_summary) if ward_summary else {},
            "ipd_today": dict(ipd_today) if ipd_today else {},
            "psy": dict(psy) if psy else {},
            "drug": dict(drug) if drug else {},
            "refer": dict(refer) if refer else {},
        },
        "wards": [dict(w) for w in wards],
        "top_stats": top_stats
    }

    _dashboard_cache = {
        "timestamp": now,
        "data": result
    }

    return result


@router.get("/top-stats", summary="สถิติ 3 การ์ดด้านบน (ผู้ป่วยนัดวันนี้, รอรับบริการ, รอตรวจ)")
async def get_dashboard_top_stats(db: AsyncSession = Depends(get_db)):
    sql_app = "SELECT COUNT(DISTINCT hn) AS total_app, COUNT(DISTINCT IF(hn IN (SELECT hn FROM ovst WHERE vstdate=CURDATE()), hn, NULL)) AS visited_app FROM oapp WHERE nextdate=CURDATE()"
    sql_opd_top = "SELECT COUNT(*) AS total_opd, COUNT(IF(ovstost='99',1,NULL)) AS completed_opd FROM ovst WHERE vstdate=CURDATE()"
    sql_wait = "SELECT COUNT(*) AS total_waiting_doctor, COUNT(IF(cur_dep='011',1,NULL)) AS er_waiting_doctor FROM ovst WHERE vstdate=CURDATE() AND ovstost='00'"

    app_res = (await db.execute(text(sql_app))).mappings().first()
    opd_res = (await db.execute(text(sql_opd_top))).mappings().first()
    wait_res = (await db.execute(text(sql_wait))).mappings().first()

    total_app = app_res["total_app"] or 0 if app_res else 0
    visited_app = app_res["visited_app"] or 0 if app_res else 0
    pending_app = max(0, total_app - visited_app)

    total_opd_top = opd_res["total_opd"] or 0 if opd_res else 0
    completed_opd = opd_res["completed_opd"] or 0 if opd_res else 0
    waiting_service = max(0, total_opd_top - completed_opd)

    total_wait = wait_res["total_waiting_doctor"] or 0 if wait_res else 0
    er_wait = wait_res["er_waiting_doctor"] or 0 if wait_res else 0
    opd_wait = max(0, total_wait - er_wait)

    return [
        {
            "title": "ผู้ป่วยนัดวันนี้",
            "icon": "tabler:calendar-week",
            "count": str(total_app),
            "isDot": True,
            "isLabel": "วันนี้",
            "details": [
                {"title": "มารับบริการแล้ว", "count": str(visited_app)},
                {"title": "ยังไม่มารับบริการ", "count": str(pending_app)}
            ]
        },
        {
            "title": "ผู้ป่วยรอรับบริการขณะนี้",
            "icon": "tabler:users",
            "count": str(waiting_service),
            "isDot": True,
            "isLabel": "Realtime",
            "details": [
                {"title": "ผู้ป่วยวันนี้ทั้งหมด", "count": str(total_opd_top)},
                {"title": "รับบริการเสร็จสิ้น", "count": str(completed_opd)}
            ]
        },
        {
            "title": "ผู้ป่วยรอตรวจ",
            "icon": "tabler:stethoscope",
            "count": str(total_wait),
            "isDot": True,
            "isLabel": "รอตรวจแพทย์",
            "details": [
                {"title": "ผู้ป่วยนอก (OPD)", "count": str(opd_wait)},
                {"title": "ผู้ป่วยฉุกเฉิน (ER)", "count": str(er_wait)}
            ]
        }
    ]


@router.get("/disease-stats", summary="สถิติโรคติดต่อสำหรับหน้าหลัก")
async def get_dashboard_disease_stats(
    db: AsyncSession = Depends(get_db),
    force_refresh: bool = Query(False, description="บังคับรีเฟรชข้อมูลใหม่จากฐานข้อมูลตรงๆ")
):
    global _disease_stats_cache
    now = time.time()
    
    # Check cache validity
    if not force_refresh and "data" in _disease_stats_cache:
        elapsed = now - _disease_stats_cache["timestamp"]
        if elapsed < CACHE_TTL_SECONDS:
            return _disease_stats_cache["data"]

    # 1. Right block: Monthly Ranking
    ranking_sql = """
        SELECT n.code506, COALESCE(p.name, 'ไม่ระบุ') AS namee, COALESCE(n.name, 'ไม่ระบุ') AS namet, COUNT(*) AS count506
        FROM surveil_member s 
        LEFT OUTER JOIN provis_code506 p ON p.code = s.code506
        LEFT OUTER JOIN name506 n ON n.code = s.code506
        WHERE DATE_FORMAT(s.vstdate,'%Y-%m') = DATE_FORMAT(NOW(),'%Y-%m') 
        GROUP BY s.code506, p.name, n.name
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """
    rank_res = await db.execute(text(ranking_sql))
    ranking_rows = [dict(r) for r in rank_res.mappings().all()]

    # Dynamic year calculation: Current year and 5 years back
    current_year_ad = date.today().year
    current_year_be = current_year_ad + 543
    past_5_years = [current_year_be - i for i in range(5, 0, -1)]
    years_list = past_5_years + [current_year_be]
    start_date_str = f"{current_year_ad - 5}-01-01"

    # 2. Left block: Tab 1 Dengue (code506 in 26, 27, 66)
    dengue_sql = """
        SELECT YEAR(vstdate)+543 AS yr, MONTH(vstdate) AS mo, COUNT(*) AS cnt
        FROM surveil_member
        WHERE code506 IN ('26','27','66') AND vstdate >= :start_date
        GROUP BY yr, mo
    """
    dengue_res = await db.execute(text(dengue_sql), {"start_date": start_date_str})
    dengue_data = {}
    for r in dengue_res.mappings().all():
        yr = r["yr"]
        mo = r["mo"]
        cnt = r["cnt"]
        if yr not in dengue_data:
            dengue_data[yr] = [0]*12
        if 1 <= mo <= 12:
            dengue_data[yr][mo-1] = cnt
    
    dengue_series = []
    median_dengue = []
    for m in range(12):
        vals = sorted([dengue_data.get(y, [0]*12)[m] for y in past_5_years])
        median_dengue.append(vals[len(vals)//2])
    dengue_series.append({"name": "Median", "data": median_dengue})
    for y in years_list:
        dengue_series.append({"name": f"ปี {y}", "data": dengue_data.get(y, [0]*12)})

    # 3. Left block: Tab 2 Diarrhea (code506 in 02, 03)
    diarrhea_sql = """
        SELECT YEAR(vstdate)+543 AS yr, MONTH(vstdate) AS mo, COUNT(*) AS cnt
        FROM surveil_member
        WHERE code506 IN ('02','03') AND vstdate >= :start_date
        GROUP BY yr, mo
    """
    diarrhea_res = await db.execute(text(diarrhea_sql), {"start_date": start_date_str})
    diarrhea_data = {}
    for r in diarrhea_res.mappings().all():
        yr = r["yr"]
        mo = r["mo"]
        cnt = r["cnt"]
        if yr not in diarrhea_data:
            diarrhea_data[yr] = [0]*12
        if 1 <= mo <= 12:
            diarrhea_data[yr][mo-1] = cnt
            
    diarrhea_series = []
    median_diarrhea = []
    for m in range(12):
        vals = sorted([diarrhea_data.get(y, [0]*12)[m] for y in past_5_years])
        median_diarrhea.append(vals[len(vals)//2])
    diarrhea_series.append({"name": "Median", "data": median_diarrhea})
    for y in years_list:
        diarrhea_series.append({"name": f"ปี {y}", "data": diarrhea_data.get(y, [0]*12)})

    # 4. Left block: Tab 3 Others (code506 in 15, 71, 31, 18 for current year)
    others_sql = """
        SELECT code506, MONTH(vstdate) AS mo, COUNT(*) AS cnt
        FROM surveil_member
        WHERE code506 IN ('15','71','31','18') AND YEAR(vstdate) = :current_year_ad
        GROUP BY code506, mo
    """
    others_res = await db.execute(text(others_sql), {"current_year_ad": current_year_ad})
    others_data = {"15": [0]*12, "71": [0]*12, "31": [0]*12, "18": [0]*12}
    for r in others_res.mappings().all():
        c = str(r["code506"])
        mo = r["mo"]
        cnt = r["cnt"]
        if c in others_data and 1 <= mo <= 12:
            others_data[c][mo-1] = cnt
            
    others_series = [
        {"name": "ไข้หวัดใหญ่ [15]", "data": others_data["15"]},
        {"name": "โรคมือเท้าปาก [71]", "data": others_data["71"]},
        {"name": "ปอดอักเสบ [31]", "data": others_data["31"]},
        {"name": "สุกใส [18]", "data": others_data["18"]}
    ]

    result = {
        "ranking_this_month": ranking_rows,
        "tab_dengue": {
            "title": "จำนวนผู้ป่วยโรคไข้เลือดออกของประชากร",
            "series": dengue_series
        },
        "tab_diarrhea": {
            "title": "จำนวนผู้ป่วยโรคอุจจาระร่วงเฉียบพลันของประชากร",
            "series": diarrhea_series
        },
        "tab_others": {
            "title": "สถานการณ์โรคติดต่ออื่นๆ ที่ต้องเฝ้าระวัง (ปีปัจจุบัน)",
            "series": others_series
        }
    }
    _disease_stats_cache = {
        "timestamp": now,
        "data": result
    }
    return result

