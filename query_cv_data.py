from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    res1 = conn.execute(text("SELECT COUNT(DISTINCT c.hn), COUNT(DISTINCT c.vn) FROM clinic_visit c INNER JOIN ovst o ON o.vn = c.vn WHERE o.vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE() AND c.clinic = '109'")).fetchone()
    res2 = conn.execute(text("SELECT COUNT(DISTINCT c.hn), COUNT(DISTINCT c.vn) FROM clinic_visit c INNER JOIN ovst o ON o.vn = c.vn WHERE o.vstdate BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE() AND c.clinic = '130'")).fetchone()
    print("Psy:", res1)
    print("Drug:", res2)
