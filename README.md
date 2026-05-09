# HOSxP API — Python 3.14 Edition

REST API สำหรับดึงข้อมูลจากฐานข้อมูล HOSxP  
รองรับทั้ง **MySQL** และ **PostgreSQL** — ใช้ได้กับ **Python 3.14**

## ทำไมถึง Python 3.14 ได้?

| Package | เหตุผล |
|---------|--------|
| `msgspec` | แทน pydantic v2 — pure Python ไม่มี Rust |
| `aiomysql` | MySQL async driver — pure Python ✅ |
| `psycopg[binary]` | PostgreSQL driver (ถ้าใช้ PG) — pre-built wheel |
| `python-dotenv` | อ่าน .env โดยตรง ไม่ต้องใช้ pydantic-settings |

---

## การติดตั้ง

```bash
# 1. สร้าง Virtual Environment ด้วย Python 3.14
python3.14 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 2. ติดตั้ง dependencies
pip install -r requirements.txt

# 3. ตั้งค่า .env
cp .env.example .env
nano .env    # แก้ DB_HOST, DB_NAME, DB_USER, DB_PASS

# 4. รัน
python run.py
```

## ถ้าใช้ PostgreSQL

แก้ไข `requirements.txt` เพิ่มบรรทัดนี้:
```
psycopg[binary]==3.2.3
```
แล้วแก้ `.env`:
```env
DB_TYPE=postgresql
DB_PORT=5432
```

---

## Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| GET | `/` | ข้อมูล API |
| GET | `/health` | ตรวจสอบ DB connection |
| GET | `/api/v1/opd/visits` | รายการผู้ป่วย OPD |
| GET | `/api/v1/opd/census` | Census OPD/IPD/ER ประจำวัน |
| GET | `/api/v1/opd/no-diagnosis` | OPD ที่ยังไม่มี ICD-10 |
| GET | `/api/v1/drug/dispensing` | รายการจ่ายยาประจำวัน |
| GET | `/api/v1/drug/top-usage` | ยาที่ใช้บ่อย Top N |

**Swagger UI:** http://localhost:8000/docs

---

## โครงสร้างโปรเจ็ค

```
hosxp-api/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py       # อ่าน .env ด้วย python-dotenv
│   │   └── database.py     # Async engine MySQL/PostgreSQL
│   ├── routers/
│   │   ├── opd.py          # OPD endpoints
│   │   └── drug.py         # Drug endpoints
│   ├── schemas/
│   │   └── opd.py          # msgspec.Struct (แทน pydantic)
│   └── queries/
│       └── sql_compat.py   # MySQL ↔ PostgreSQL syntax helper
├── run.py
├── requirements.txt
└── .env.example
```
