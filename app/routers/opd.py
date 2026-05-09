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
