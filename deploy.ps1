$IMAGE_NAME = "amedake01x/hosxp-api"
$TAG = "latest"

Write-Host "--- 1. Building Docker Image ---" -ForegroundColor Cyan
# ใช้ ${} ครอบชื่อตัวแปรเพื่อป้องกันความสับสนกับเครื่องหมาย :
docker build -t "${IMAGE_NAME}:${TAG}" .

Write-Host "--- 2. Pushing to Docker Hub ---" -ForegroundColor Cyan
docker push "${IMAGE_NAME}:${TAG}"

Write-Host "--- Done! Please pull on aaPanel ---" -ForegroundColor Green