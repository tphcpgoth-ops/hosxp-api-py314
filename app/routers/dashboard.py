from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date

from app.core.database import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", summary="สรุปข้อมูล Dashboard สำหรับหน้าหลัก")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
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

    return {
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
        },
        "wards": [dict(w) for w in wards]
    }
