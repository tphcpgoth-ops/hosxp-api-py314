from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import validate_api_key

router = APIRouter(
    prefix="/ward",
    tags=["Ward"],
    responses={404: {"description": "Not found"}},
)

@router.get("/active-wards", summary="รายชื่อตึกผู้ป่วยใน")
async def get_active_wards(
    db: AsyncSession = Depends(get_db)
):
    sql = "SELECT ward, name FROM ward WHERE ward_active = 'Y' ORDER BY name ASC"
    result = await db.execute(text(sql))
    rows = result.mappings().all()
    return {"data": [dict(r) for r in rows]}

@router.get("/{ward_id}/summary", summary="สรุปข้อมูลตึกผู้ป่วยใน", dependencies=[Depends(validate_api_key)])
async def get_ward_summary(
    ward_id: str,
    db: AsyncSession = Depends(get_db)
):
    import asyncio
    
    # query 1: wtotal, bedcount, wblank, wardn, wardnb
    sql1 = """
        SELECT COUNT(*) AS wtotal,
        (SELECT SUM(bedcount) FROM ward WHERE ward = :ward) AS bedcount,
        (SELECT SUM(bedcount) FROM ward WHERE ward = :ward)-COUNT(*) AS wblank,
        SUM(IF(ward = :ward,1,0)) AS wardn,
        (SELECT SUM(bedcount) FROM ward WHERE ward = :ward)-SUM(IF(ward = :ward,1,0)) AS wardnb
        FROM ipt WHERE dchdate IS NULL 
    """
    
    # query 2: admittoday
    sql2 = "SELECT COUNT(*) AS admittoday FROM ipt WHERE regdate = CURRENT_DATE() AND ward = :ward"
    
    # query 3: dchtoday
    sql3 = "SELECT COUNT(*) AS dchtoday FROM ipt WHERE dchdate = CURRENT_DATE() AND ward = :ward"
    
    # query 4: movetoday
    sql4 = "SELECT COUNT(*) AS movetoday FROM iptbedmove WHERE movedate = CURRENT_DATE() AND (nward = :ward OR oward = :ward)"
    
    # query 5: sumincome & incs
    sql5 = """
        SELECT SUM(inc05) AS inc05, SUM(inc09) AS inc09, SUM(inc12) AS inc12, SUM(income) AS sumincome
        FROM an_stat WHERE dchdate IS NULL AND ward = :ward
    """
    
    # execute concurrently
    async def fetch_one(sql, params):
        res = await db.execute(text(sql), params)
        return dict(res.mappings().first() or {})

    params = {"ward": ward_id}
    res1 = await fetch_one(sql1, params)
    res2 = await fetch_one(sql2, params)
    res3 = await fetch_one(sql3, params)
    res4 = await fetch_one(sql4, params)
    res5 = await fetch_one(sql5, params)
    
    # combine results
    summary = {**res1, **res2, **res3, **res4, **res5}
    # default None to 0
    for k, v in summary.items():
        if v is None:
            summary[k] = 0
            
    return {"data": summary}


@router.get("/{ward_id}/patients", summary="รายชื่อผู้ป่วยในตึก", dependencies=[Depends(validate_api_key)])
async def get_ward_patients(
    ward_id: str,
    db: AsyncSession = Depends(get_db)
):
    sql = """
        SELECT i.an, i.hn, i.regdate, i.dchdate, i.pttype, i.ward, i.admdoctor,
               a.bedno, p.pname, p.fname, p.lname, p.sex, p.drugallergy,
               s.income, s.age_y, s.admdate,
               pt.name AS pttypename, pm.image, d.name AS doctorname
        FROM ipt i 
        LEFT OUTER JOIN an_stat s ON s.an = i.an
        LEFT OUTER JOIN iptadm a ON a.an = i.an
        LEFT OUTER JOIN patient p ON p.hn = i.hn
        LEFT OUTER JOIN pttype pt ON pt.pttype = i.pttype
        LEFT OUTER JOIN patient_image pm ON pm.hn = i.hn
        LEFT OUTER JOIN doctor d ON d.code = i.admdoctor
        WHERE i.dchdate IS NULL AND i.ward = :ward
        ORDER BY a.bedno ASC 
    """
    result = await db.execute(text(sql), {"ward": ward_id})
    rows = result.mappings().all()
    
    # format data
    data = []
    for row in rows:
        d = dict(row)
        # Handle binary image
        if d.get("image"):
            import base64
            d["image"] = base64.b64encode(d["image"]).decode('utf-8')
        else:
            d["image"] = None
            
        data.append(d)
        
    return {"data": data}
