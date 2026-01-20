# ===========================================
# Broadlistening セットアップスクリプト (Windows PowerShell)
# ===========================================

$ErrorActionPreference = "Stop"

Write-Host "Broadlistening セットアップを開始します..." -ForegroundColor Cyan

# 作業ディレクトリ
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# ディレクトリ作成
Write-Host "ディレクトリ作成中..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "models" | Out-Null
New-Item -ItemType Directory -Force -Path "web\data" | Out-Null

# 初期データファイル作成
if (-not (Test-Path "web\data\issues.json")) {
    $IssuesJson = @'
{
  "clusters": [],
  "issues": [],
  "updated_at": null
}
'@
    $IssuesJson | Out-File -FilePath "web\data\issues.json" -Encoding UTF8
    Write-Host "  初期データファイルを作成しました" -ForegroundColor Green
}

# .envファイル確認
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  .envファイルを作成しました（.env.exampleからコピー）" -ForegroundColor Green
        Write-Host "  重要: .envファイルのN8N_PASSWORDを変更してください" -ForegroundColor Yellow
    }
}

# Docker確認
Write-Host ""
Write-Host "Docker確認中..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Dockerが見つかりません！" -ForegroundColor Red
    Write-Host ""
    Write-Host "以下のいずれかをインストールしてください:" -ForegroundColor Yellow
    Write-Host "  - Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Cyan
    Write-Host "  - WSL + Docker Engine" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# NVIDIA GPU確認
Write-Host ""
Write-Host "GPU確認中..." -ForegroundColor Yellow
$hasGpu = $false
try {
    $nvidiaSmi = nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
    if ($nvidiaSmi) {
        Write-Host "  NVIDIA GPU検出: $nvidiaSmi" -ForegroundColor Green
        $hasGpu = $true
    }
} catch {
    Write-Host "  NVIDIA GPUが検出されませんでした（CPU版を使用）" -ForegroundColor Yellow
}

# Docker Compose起動
Write-Host ""
Write-Host "Docker Compose起動中..." -ForegroundColor Yellow
Write-Host "  注意: 初回起動時はモデルのダウンロードに時間がかかります（約5GB）" -ForegroundColor Yellow

if ($hasGpu) {
    Write-Host "  GPU版で起動します" -ForegroundColor Green
    docker-compose up -d
} else {
    Write-Host "  CPU版で起動します" -ForegroundColor Yellow
    docker-compose -f docker-compose.cpu.yml up -d
}

# 起動待ち
Write-Host ""
Write-Host "サービス起動を待機中（20秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# ヘルスチェック
Write-Host ""
Write-Host "ヘルスチェック..." -ForegroundColor Yellow

function Test-Service {
    param (
        [string]$Name,
        [string]$Url
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 301 -or $response.StatusCode -eq 302) {
            Write-Host "  [OK] $Name" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "  [--] $Name (起動中または失敗)" -ForegroundColor Yellow
        return $false
    }
    return $false
}

Test-Service "Forgejo" "http://localhost:3000"
Test-Service "n8n" "http://localhost:5678"
Test-Service "Qdrant" "http://localhost:6333"
Test-Service "Web UI" "http://localhost:8000"

Write-Host "  [..] LLM (LFM2.5): モデルダウンロード中の可能性あり（5-10分）" -ForegroundColor Cyan
Write-Host "  [..] Embedding (bge-m3): 初回はモデルダウンロード中（3-5分）" -ForegroundColor Cyan

# 完了メッセージ
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "セットアップ完了！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "アクセス先:" -ForegroundColor White
Write-Host "  Forgejo:    http://localhost:3000" -ForegroundColor Cyan
Write-Host "  n8n:        http://localhost:5678  (admin / .envで設定)" -ForegroundColor Cyan
Write-Host "  Qdrant:     http://localhost:6333/dashboard" -ForegroundColor Cyan
Write-Host "  LLM API:    http://localhost:8080/health" -ForegroundColor Cyan
Write-Host "  Embedding:  http://localhost:8081" -ForegroundColor Cyan
Write-Host "  Web UI:     http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor White
Write-Host "  1. Forgejoで管理者アカウント作成" -ForegroundColor Yellow
Write-Host "  2. リポジトリ作成" -ForegroundColor Yellow
Write-Host "  3. n8nでWebhookワークフロー設定" -ForegroundColor Yellow
Write-Host "  4. Issueを投稿してテスト" -ForegroundColor Yellow
Write-Host ""
Write-Host "便利なコマンド:" -ForegroundColor Gray
Write-Host "  コンテナ状態確認: docker ps" -ForegroundColor Gray
Write-Host "  ログ確認: docker-compose -f docker-compose.cpu.yml logs -f [service]" -ForegroundColor Gray
Write-Host "  LLMヘルスチェック: curl http://localhost:8080/health" -ForegroundColor Gray
Write-Host "  停止: docker-compose -f docker-compose.cpu.yml down" -ForegroundColor Gray
Write-Host ""
