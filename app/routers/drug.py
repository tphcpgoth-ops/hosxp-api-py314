from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date
from typing import Optional

from app.core.database import get_db
from app.core.security import validate_api_key
from app.schemas.opd import DrugDispenseItem, rows_to_list
from app.routers.cd import get_date_range

router = APIRouter(prefix="/drug", tags=["Drug"])


@router.get("/dispensing", summary="รายการจ่ายยาประจำวัน")
async def get_drug_dispensing(
    dispense_date: date = Query(default=date.today()),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT
            o.vn, o.hn, o.vstdate,
            r.icode,
            d.name AS drug_name,
            r.amount, r.unit, r.unitprice,
            (r.amount * r.unitprice) AS total_price
        FROM opitemrece r
        JOIN ovst o       ON r.vn = o.vn
        LEFT JOIN drugitems d ON r.icode = d.icode
        WHERE o.vstdate = :d
          AND r.icode IN (SELECT icode FROM drugitems)
        ORDER BY o.vn
    """
    result = await db.execute(text(sql), {"d": str(dispense_date)})
    rows = result.mappings().all()
    data = rows_to_list(rows, DrugDispenseItem)
    total_cost = sum(float(r.get("total_price") or 0) for r in data)

    return {
        "date": str(dispense_date),
        "total_items": len(data),
        "total_cost": round(total_cost, 2),
        "data": data,
    }


@router.get("/top-usage", summary="ยาที่ใช้บ่อย Top N")
async def get_top_drug_usage(
    start_date: date = Query(..., description="วันเริ่มต้น YYYY-MM-DD"),
    end_date: date = Query(..., description="วันสิ้นสุด YYYY-MM-DD"),
    top: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT
            r.icode,
            d.name  AS drug_name,
            d.units,
            SUM(r.amount)                   AS total_qty,
            SUM(r.amount * r.unitprice)     AS total_cost,
            COUNT(DISTINCT o.vn)            AS visit_count
        FROM opitemrece r
        JOIN ovst o           ON r.vn = o.vn
        LEFT JOIN drugitems d ON r.icode = d.icode
        WHERE o.vstdate BETWEEN :s AND :e
          AND r.icode IN (SELECT icode FROM drugitems)
        GROUP BY r.icode, d.name, d.units
        ORDER BY total_qty DESC
        LIMIT :top
    """
    result = await db.execute(text(sql), {"s": str(start_date), "e": str(end_date), "top": top})
    rows = result.mappings().all()
    data = [{k: (float(v) if hasattr(v, "__float__") and not isinstance(v, (str, int)) else v)
             for k, v in r.items()} for r in rows]
    return {"start_date": str(start_date), "end_date": str(end_date), "data": data}


@router.get("/stats-summary", summary="สรุปสถิติคลินิกยาเสพติดรายเดือนตามปีงบประมาณ")
async def get_drug_stats_summary(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT DATE_FORMAT(o.vstdate,'%Y-%m') AS AMONTH,
               COUNT(DISTINCT c.hn) AS hn_count,
               COUNT(DISTINCT c.vn) AS total,
               DATE_FORMAT(o.vstdate,'%Y')+543 AS AY, DATE_FORMAT(o.vstdate,'%m') AS AM
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '130'
        GROUP BY DATE_FORMAT(o.vstdate,'%Y-%m')
        ORDER BY DATE_FORMAT(o.vstdate,'%Y-%m') ASC
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    return {"fiscal_year": res_year, "year": res_year, "data": [dict(r) for r in rows]}


@router.get("/stats-diseases", summary="สถิติโรคในคลินิกยาเสพติดตามปีงบประมาณ")
async def get_drug_stats_diseases(
    fiscal_year: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start_date, end_date, res_year = get_date_range(fiscal_year, year)
    sql = """
        SELECT od.icd10 AS code,
               COALESCE(i.name, 'ไม่ระบุ') AS name,
               COUNT(*) AS count
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        INNER JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
        LEFT JOIN icd101 i ON i.code = od.icd10
        WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '130'
        GROUP BY od.icd10, i.name
        ORDER BY count DESC
        LIMIT 30
    """
    result = await db.execute(text(sql), {"start": start_date, "end": end_date})
    rows = result.mappings().all()
    
    data = []
    for r in rows:
        item = dict(r)
        msql = """
            SELECT DATE_FORMAT(o.vstdate,'%m') AS m, COUNT(*) AS cnt
            FROM clinic_visit c
            INNER JOIN ovst o ON o.vn = c.vn
            INNER JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
            WHERE o.vstdate BETWEEN :start AND :end AND c.clinic = '130' AND od.icd10 = :code
            GROUP BY DATE_FORMAT(o.vstdate,'%m')
        """
        mres = await db.execute(text(msql), {"start": start_date, "end": end_date, "code": item["code"]})
        mrows = mres.mappings().all()
        item["months"] = {mr["m"]: mr["cnt"] for mr in mrows}
        data.append(item)
        
    return {"fiscal_year": res_year, "year": res_year, "data": data}


@router.get("/patients", summary="รายชื่อผู้รับบริการคลินิกยาเสพติดตามเดือน", dependencies=[Depends(validate_api_key)])
async def get_drug_patients(
    ym: str = Query(..., description="ปี-เดือน ค.ศ. เช่น 2026-05"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT o.vstdate,
               o.hn,
               CONCAT(p.pname, p.fname, ' ', p.lname) AS ptname,
               od.icd10 AS pdx,
               COALESCE(i.name, 'ไม่ระบุ') AS dxname
        FROM clinic_visit c
        INNER JOIN ovst o ON o.vn = c.vn
        LEFT JOIN patient p ON p.hn = o.hn
        LEFT JOIN ovstdiag od ON od.vn = c.vn AND od.diagtype = '1'
        LEFT JOIN icd101 i ON i.code = od.icd10
        WHERE DATE_FORMAT(o.vstdate, '%Y-%m') = :ym AND c.clinic = '130'
        ORDER BY o.vstdate ASC
        LIMIT 500
    """
    result = await db.execute(text(sql), {"ym": ym})
    rows = result.mappings().all()
    return {"ym": ym, "data": [dict(r) for r in rows]}
