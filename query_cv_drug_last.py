from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    res = conn.execute(text("SELECT o.vstdate FROM clinic_visit c INNER JOIN ovst o ON o.vn=c.vn WHERE c.clinic='130' ORDER BY o.vstdate DESC LIMIT 1")).fetchone()
    print("Last drug visit:", res)
