"""
schemas/opd.py
ใช้ msgspec.Struct แทน pydantic.BaseModel
— เร็วกว่า pydantic v1 และเป็น pure Python (ไม่มี Rust)
"""
import msgspec
from typing import Optional
from datetime import date


class OpdVisitItem(msgspec.Struct):
    vn: str
    hn: str
    vstdate: Optional[str] = None
    vsttime: Optional[str] = None
    pid: Optional[str] = None
    pname: Optional[str] = None
    fname: Optional[str] = None
    lname: Optional[str] = None
    age_y: Optional[int] = None
    sex: Optional[str] = None
    department: Optional[str] = None
    icd10: Optional[str] = None
    dx_name: Optional[str] = None


class OpdListResponse(msgspec.Struct):
    total: int
    page: int
    page_size: int
    data: list[OpdVisitItem]


class PatientCensusResponse(msgspec.Struct):
    report_date: str
    opd_count: int
    ipd_count: int
    er_count: int


class DrugDispenseItem(msgspec.Struct):
    vn: str
    hn: str
    vstdate: Optional[str] = None
    icode: Optional[str] = None
    drug_name: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None
    unitprice: Optional[float] = None
    total_price: Optional[float] = None


def struct_to_dict(obj) -> dict:
    """แปลง msgspec.Struct → dict สำหรับ return ใน FastAPI"""
    return {f: getattr(obj, f) for f in obj.__struct_fields__}


def rows_to_list(rows, struct_cls) -> list[dict]:
    """แปลง SQLAlchemy rows → list of dict ผ่าน msgspec.Struct"""
    result = []
    for row in rows:
        d = dict(row)
        # แปลง date/datetime → string
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        obj = struct_cls(**{f: d.get(f) for f in struct_cls.__struct_fields__})
        result.append(struct_to_dict(obj))
    return result
