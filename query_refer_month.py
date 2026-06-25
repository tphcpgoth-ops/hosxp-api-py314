from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    res1 = conn.execute(text("SELECT COUNT(DISTINCT hn) AS hn, COUNT(*) AS vn FROM referin WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()")).fetchone()
    res2 = conn.execute(text("SELECT COUNT(DISTINCT hn) AS hn, COUNT(*) AS vn FROM referout WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()")).fetchone()
    print(f"Refer In Month: {res1}")
    print(f"Refer Out Month: {res2}")
