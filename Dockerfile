# ใช้ Python 3.12-slim (เสถียรและขนาดเล็ก) 
# หากต้องการทดสอบ 3.14 ในอนาคตสามารถเปลี่ยนเป็น python:3.14-rc-slim
FROM python:3.12-slim

# ตั้งค่า Working Directory
WORKDIR /app

# ตั้งค่าพื้นฐานสำหรับ Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Bangkok

# ติดตั้ง system dependencies และตั้งค่า timezone
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ติดตั้ง Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# คัดลอกเฉพาะ Source Code (ไม่รวม .env เพราะอยู่ใน .dockerignore)
COPY . .

# แจ้ง Port ที่ Container จะใช้งาน (Default: 8800)
# หมายเหตุ: ใน aaPanel คุณควร Map port 8800 ของ Container ไปยัง Port ที่ต้องการบน Host
EXPOSE 8800

# คำสั่งรัน (Uvicorn จะอ่านค่า .env ที่เรา Mount เข้าไปใน /app/.env โดยอัตโนมัติผ่านโค้ด FastAPI)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8889"]
