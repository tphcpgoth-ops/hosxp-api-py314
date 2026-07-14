from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date, datetime
import calendar
from typing import Optional

from app.core.database import get_db

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/calendar", summary="จำนวนผู้ป่วยนัดหมายแต่ละวัน (ปฏิทิน)")
async def get_appointment_calendar(
    start_date: Optional[str] = Query(default=None, description="วันที่เริ่มต้น YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="วันที่สิ้นสุด YYYY-MM-DD"),
    year: Optional[int] = Query(default=None, description="ปี ค.ศ. (เช่น 2026)"),
    month: Optional[int] = Query(default=None, description="เดือน (1-12)"),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month

    if not start_date or not end_date:
        _, last_day = calendar.monthrange(target_year, target_month)
        start_date = f"{target_year:04d}-{target_month:02d}-01"
        end_date = f"{target_year:04d}-{target_month:02d}-{last_day:02d}"

    sql = """
        SELECT 
            DATE_FORMAT(o.nextdate, '%Y-%m-%d') AS appointment_date,
            COUNT(*) AS total_appointments,
            COUNT(DISTINCT o.hn) AS total_patients
        FROM oapp o
        WHERE o.nextdate BETWEEN :start_date AND :end_date
        GROUP BY DATE_FORMAT(o.nextdate, '%Y-%m-%d')
        ORDER BY appointment_date ASC
    """
    result = await db.execute(text(sql), {"start_date": start_date, "end_date": end_date})
    rows = result.mappings().all()

    data = []
    for r in rows:
        data.append({
            "date": r["appointment_date"],
            "total_appointments": int(r["total_appointments"] or 0),
            "total_patients": int(r["total_patients"] or 0),
        })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "data": data
    }


@router.get("/by-department", summary="จำนวนผู้ป่วยนัดหมายแยกตามแผนก/คลินิกในแต่ละวัน")
async def get_appointments_by_department(
    date: str = Query(..., description="วันที่นัดหมาย YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT 
            COALESCE(c.name, k.department, 'ไม่ระบุคลินิก/แผนก') AS department_name,
            COALESCE(o.clinic, o.depcode, '-') AS department_code,
            COUNT(*) AS total_appointments,
            COUNT(DISTINCT o.hn) AS total_patients
        FROM oapp o
        LEFT JOIN clinic c ON o.clinic = c.clinic
        LEFT JOIN kskdepartment k ON o.depcode = k.depcode
        WHERE o.nextdate = :date
        GROUP BY department_name, department_code
        ORDER BY total_appointments DESC
    """
    result = await db.execute(text(sql), {"date": date})
    rows = result.mappings().all()

    departments = []
    total_appointments = 0
    total_patients = 0

    for r in rows:
        app_cnt = int(r["total_appointments"] or 0)
        pat_cnt = int(r["total_patients"] or 0)
        total_appointments += app_cnt
        total_patients += pat_cnt
        departments.append({
            "department_name": r["department_name"],
            "department_code": r["department_code"],
            "total_appointments": app_cnt,
            "total_patients": pat_cnt,
        })

    return {
        "date": date,
        "total_appointments": total_appointments,
        "total_patients": total_patients,
        "total_departments": len(departments),
        "departments": departments
    }
