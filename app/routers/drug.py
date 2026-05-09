from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date

from app.core.database import get_db
from app.schemas.opd import DrugDispenseItem, rows_to_list

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
