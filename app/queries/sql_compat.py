"""
sql_compat.py — แปลง SQL syntax ระหว่าง MySQL และ PostgreSQL
เรียกใช้ใน router โดยไม่ต้องสนใจว่าใช้ DB อะไร
"""
from app.core.config import settings


def date_format(column: str, fmt: str = "%Y-%m-%d") -> str:
    """Format วันที่"""
    if settings.DB_TYPE == "mysql":
        return f"DATE_FORMAT({column}, '{fmt}')"
    else:
        pg = fmt.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")
        return f"TO_CHAR({column}, '{pg}')"


def year_func(column: str) -> str:
    if settings.DB_TYPE == "mysql":
        return f"YEAR({column})"
    return f"EXTRACT(YEAR FROM {column})"


def month_func(column: str) -> str:
    if settings.DB_TYPE == "mysql":
        return f"MONTH({column})"
    return f"EXTRACT(MONTH FROM {column})"


def now_func() -> str:
    return "NOW()" if settings.DB_TYPE == "mysql" else "CURRENT_TIMESTAMP"


def concat(*args: str) -> str:
    if settings.DB_TYPE == "mysql":
        return f"CONCAT({', '.join(args)})"
    return " || ".join(args)
