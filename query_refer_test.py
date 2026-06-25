from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://hosinfov2user:p6rik%3D9trkosbo%23@10.10.10.20:3306/hos')
with engine.connect() as conn:
    sql = """
        SELECT 
            (SELECT COUNT(DISTINCT hn) FROM referin WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) + 
            (SELECT COUNT(DISTINCT hn) FROM referout WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_hn,
            (SELECT COUNT(*) FROM referin WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) + 
            (SELECT COUNT(*) FROM referout WHERE refer_date BETWEEN DATE_FORMAT(NOW(),'%Y-%m-01') AND CURDATE()) AS ptm_refer_vn,
            (SELECT COUNT(*) FROM referin WHERE refer_date = CURDATE()) + 
            (SELECT COUNT(*) FROM referout WHERE refer_date = CURDATE()) AS pt_refer_today
    """
    res = conn.execute(text(sql)).fetchone()
    print("Refer Combined:", res)
