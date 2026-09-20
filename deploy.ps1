$IMAGE_NAME = "amedake01x/hosxp-api"
$TAG = "latest"
$WEBHOOK_URL = "https://10.10.8.132:65411/hook?access_key=SjYL027c7FnBzyFUz4aOMMDti6KDoghtfoE5eme4qoItcuP2" 

Write-Host "--- 1. Building Docker Image ---" -ForegroundColor Cyan
docker build --platform linux/amd64 -t "${IMAGE_NAME}:${TAG}" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker Build ล้มเหลว! ยกเลิกการ Push" -ForegroundColor Red
    exit 1
}

Write-Host "--- 2. Pushing to Docker Hub ---" -ForegroundColor Cyan
docker push "${IMAGE_NAME}:${TAG}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker Push ล้มเหลว!" -ForegroundColor Red
    exit 1
}

Write-Host "--- 3. Triggering Deployment on aaPanel ---" -ForegroundColor Cyan
# ใช้ curl.exe -k เพื่อข้ามการเช็ค SSL Certificate บน aaPanel
curl.exe -k -X POST $WEBHOOK_URL

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ สั่ง Deploy บน aaPanel สำเร็จ!" -ForegroundColor Green
} else {
    Write-Host "`n❌ ไม่สามารถติดต่อ aaPanel Webhook ได้!" -ForegroundColor Red
    exit 1
}

Write-Host "--- 🎉 Deployment Pipeline Completed! ---" -ForegroundColor Green