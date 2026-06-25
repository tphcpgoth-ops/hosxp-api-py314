from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    res = conn.execute(text("SHOW TABLES LIKE '%clinic%'")).fetchall()
    print("clinic tables:", [r[0] for r in res])
