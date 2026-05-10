from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.schemas.opd import OpdVisitItem, PatientCensusResponse, rows_to_list

router = APIRouter(prefix="/opd", tags=["OPD"])


@router.get("/visits", summary="รายการผู้ป่วย OPD ตามวันที่")
async def get_opd_visits(
    visit_date: date = Query(default=date.today(), description="วันที่รับบริการ YYYY-MM-DD"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    department: Optional[str] = Query(default=None, description="รหัสแผนก"),
    db: AsyncSession = Depends(get_db),
):
    dept_filter = "AND o.depcode = :dept" if department else ""
    offset = (page - 1) * page_size

    sql = f"""
        SELECT
        o.vn, o.hn,o.vstdate,p.pname,p.fname,p.lname,p.birthday
        FROM ovst o
        LEFT JOIN patient p ON o.hn = p.hn
        WHERE o.vstdate = :visit_date {dept_filter}
        ORDER BY o.vstdate
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*) FROM ovst o
        WHERE o.vstdate = :visit_date {dept_filter}
    """

    params: dict = {"visit_date": str(visit_date), "limit": page_size, "offset": offset}
    if department:
        params["dept"] = department

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": rows_to_list(rows, OpdVisitItem),
    }


@router.get("/census", summary="Census ประจำวัน OPD / IPD / ER")
async def get_daily_census(
    report_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT
            (SELECT COUNT(*) FROM ovst       WHERE vstdate = :d) AS opd_count,
            (SELECT COUNT(*) FROM ipt        WHERE regdate = :d) AS ipd_count,
            (SELECT COUNT(*) FROM er_regist  WHERE regdate = :d) AS er_count
    """
    result = await db.execute(text(sql), {"d": str(report_date)})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูล")

    return {
        "report_date": str(report_date),
        "opd_count": row["opd_count"] or 0,
        "ipd_count": row["ipd_count"] or 0,
        "er_count": row["er_count"] or 0,
    }


@router.get("/no-diagnosis", summary="OPD ที่ยังไม่มี ICD-10")
async def get_opd_no_diagnosis(
    visit_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT o.vn, o.hn, o.vstdate, o.vsttime,
               p.fname, p.lname, k.name AS department
        FROM ovst o
        LEFT JOIN patient p       ON o.hn = p.hn
        LEFT JOIN kskdepartment k ON o.depcode = k.depcode
        WHERE o.vstdate = :d
          AND o.vn NOT IN (
              SELECT DISTINCT vn FROM ovstdiag WHERE diagtype = '1'
          )
        ORDER BY o.vsttime
    """
    result = await db.execute(text(sql), {"d": str(visit_date)})
    rows = result.mappings().all()
    data = [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in rows]
    return {"date": str(visit_date), "count": len(data), "data": data}
@router.get("/stats-summary", summary="สรุปสถิติรายเดือนตามปีงบประมาณ")
async def get_opd_stats_summary(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    # Calculate start/end dates for fiscal year (Oct - Sep)
    # fiscal_year is in BE (Buddhist Era)
    year_end = fiscal_year - 543
    year_start = year_end - 1
    
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT t.AMONTH, 
               SUM(t.visitopdhn) - SUM(t.visitipdhn) AS opd_hn,
               SUM(t.visitopd) - SUM(t.visitipd) AS opd_vn,
               SUM(t.visitipdhn) AS ipd_hn,
               SUM(t.visitipd) AS ipd_an,
               t.AY, t.AM 
        FROM (
            SELECT DATE_FORMAT(vstdate,'%Y-%m') AS AMONTH, COUNT(DISTINCT hn) AS visitopdhn, COUNT(*) AS visitopd, 0 AS visitipdhn, 0 AS visitipd,
                   DATE_FORMAT(vstdate,'%Y')+543 AS AY, DATE_FORMAT(vstdate,'%m') AS AM
            FROM vn_stat 
            WHERE vstdate BETWEEN :start AND :end
            GROUP BY DATE_FORMAT(vstdate,'%Y-%m')
            UNION ALL
            SELECT DATE_FORMAT(regdate,'%Y-%m') AS AMONTH, 0 AS visitopdhn, 0 AS visitopd, COUNT(DISTINCT hn) AS visitipdhn, COUNT(*) AS visitipd,
                   DATE_FORMAT(regdate,'%Y')+543 AS AY, DATE_FORMAT(regdate,'%m') AS AM
            FROM an_stat 
            WHERE regdate BETWEEN :start AND :end
            GROUP BY DATE_FORMAT(regdate,'%Y-%m')
        ) AS t
        GROUP BY t.AMONTH
        ORDER BY t.AMONTH
    """
    
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-specialty", summary="สถิติรายแผนกตามปีงบประมาณ")
async def get_opd_stats_specialty(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT t.spclty, t.name, 
               SUM(t.visitopdhn) - SUM(t.visitipdhn) AS opd_hn,
               SUM(t.visitopd) - SUM(t.visitipd) AS opd_vn,
               SUM(t.visitipdhn) AS ipd_hn,
               SUM(t.visitipd) AS ipd_an
        FROM (
            SELECT v.spclty, s.name, COUNT(DISTINCT v.hn) AS visitopdhn, COUNT(*) AS visitopd, 0 AS visitipdhn, 0 AS visitipd
            FROM vn_stat v
            LEFT OUTER JOIN spclty s ON s.spclty = v.spclty
            WHERE v.vstdate BETWEEN :start AND :end
            GROUP BY v.spclty
            UNION ALL
            SELECT a.spclty, s.name, 0 AS visitopdhn, 0 AS visitopd, COUNT(DISTINCT hn) AS visitipdhn, COUNT(*) AS visitipd
            FROM an_stat a
            LEFT OUTER JOIN spclty s ON s.spclty = a.spclty
            WHERE regdate BETWEEN :start AND :end
            GROUP BY a.spclty
        ) AS t
        GROUP BY t.spclty
        ORDER BY t.spclty
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}


@router.get("/stats-inscl", summary="สัดส่วนสิทธิการรักษาตามปีงบประมาณ")
async def get_opd_stats_inscl(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    opd_sql = """
        SELECT h.inscl_name, COUNT(DISTINCT vn) AS count
        FROM ovst v
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE v.vstdate BETWEEN :start AND :end AND an IS NULL
        GROUP BY pt.hipdata_code
        ORDER BY count DESC
    """
    
    ipd_sql = """
        SELECT h.inscl_name, COUNT(DISTINCT vn) AS count
        FROM ovst v
        LEFT OUTER JOIN pttype pt ON pt.pttype = v.pttype
        LEFT OUTER JOIN nhso_inscl_code h ON h.inscl_code = pt.hipdata_code
        WHERE v.vstdate BETWEEN :start AND :end AND an IS NOT NULL
        GROUP BY pt.hipdata_code
        ORDER BY count DESC
    """
    
    opd_res = await db.execute(text(opd_sql), {"start": start_date, "end": end_date})
    ipd_res = await db.execute(text(ipd_sql), {"start": start_date, "end": end_date})
    
    return {
        "fiscal_year": fiscal_year,
        "opd": [dict(r) for r in opd_res.mappings().all()],
        "ipd": [dict(r) for r in ipd_res.mappings().all()]
    }


@router.get("/stats-icd10", summary="50 อันดับโรคตามปีงบประมาณ")
async def get_opd_stats_icd10(
    fiscal_year: int = Query(default=date.today().year + (1 if date.today().month > 9 else 0) + 543),
    db: AsyncSession = Depends(get_db),
):
    year_end = fiscal_year - 543
    year_start = year_end - 1
    start_date = f"{year_start}-10-01"
    end_date = f"{year_end}-09-30"

    sql = """
        SELECT i.pdx, d.name AS diag_name, d.tname AS diag_tname, COUNT(*) AS count,
               SUM(IF(i.sex = '1', 1, 0)) AS male,
               SUM(IF(i.sex = '2', 1, 0)) AS female
        FROM vn_stat i
        LEFT OUTER JOIN icd101 d ON d.code = i.pdx
        WHERE i.vstdate BETWEEN :start AND :end AND pdx <> ''
        GROUP BY i.pdx
        ORDER BY count DESC
        LIMIT 50
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": fiscal_year, "data": [dict(r) for r in rows]}
