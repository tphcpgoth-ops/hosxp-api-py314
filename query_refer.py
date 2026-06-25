from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    res1 = conn.execute(text("SELECT COUNT(*) FROM referin WHERE refer_date = CURDATE()")).scalar()
    res2 = conn.execute(text("SELECT COUNT(*) FROM referout WHERE refer_date = CURDATE()")).scalar()
    print(f"Refer In Today: {res1}")
    print(f"Refer Out Today: {res2}")
