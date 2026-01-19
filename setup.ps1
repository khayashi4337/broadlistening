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

# index.htmlをwebディレクトリにコピー（存在しない場合）
if (Test-Path "index.html" -and -not (Test-Path "web\index.html")) {
    Copy-Item "index.html" "web\index.html"
    Write-Host "  index.html を web/ にコピーしました" -ForegroundColor Green
}

# 初期データファイル作成
$IssuesJson = @'
{
  "clusters": [],
  "issues": [],
  "updated_at": null
}
'@
$IssuesJson | Out-File -FilePath "web\data\issues.json" -Encoding UTF8
Write-Host "  初期データファイルを作成しました" -ForegroundColor Green

# LFM2.5モデルの確認
$ModelPath = "models\lfm-2.5-3b-q4_k_m.gguf"
$ModelUrl = "https://huggingface.co/liquidai/lfm-2.5-3b-gguf/resolve/main/lfm-2.5-3b-q4_k_m.gguf"

if (-not (Test-Path $ModelPath)) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "LFM2.5モデルが見つかりません" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "以下のいずれかの方法でダウンロードしてください:" -ForegroundColor White
    Write-Host ""
    Write-Host "方法1: ブラウザで直接ダウンロード" -ForegroundColor Cyan
    Write-Host "  URL: $ModelUrl"
    Write-Host "  保存先: $ProjectRoot\$ModelPath"
    Write-Host ""
    Write-Host "方法2: curl コマンド（約2GB、数分かかります）" -ForegroundColor Cyan
    Write-Host "  curl -L -o `"$ModelPath`" `"$ModelUrl`""
    Write-Host ""
    Write-Host "方法3: PowerShellでダウンロード（時間がかかります）" -ForegroundColor Cyan
    Write-Host "  Invoke-WebRequest -Uri `"$ModelUrl`" -OutFile `"$ModelPath`""
    Write-Host ""

    $download = Read-Host "今すぐダウンロードしますか？ (y/N)"
    if ($download -eq "y" -or $download -eq "Y") {
        Write-Host "ダウンロード中...（約2GB）" -ForegroundColor Yellow
        try {
            # curlを優先（Invoke-WebRequestより高速）
            & curl -L -o $ModelPath $ModelUrl
            Write-Host "ダウンロード完了" -ForegroundColor Green
        } catch {
            Write-Host "curlが失敗しました。Invoke-WebRequestで再試行..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath
        }
    } else {
        Write-Host "モデルなしで続行します（llmサービスは起動失敗します）" -ForegroundColor Yellow
    }
} else {
    Write-Host "LFM2.5モデル: 存在確認OK" -ForegroundColor Green
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
    Write-Host "Docker Desktopをインストールしてください:" -ForegroundColor Yellow
    Write-Host "  https://www.docker.com/products/docker-desktop/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "インストール後、Docker Desktopを起動してから再実行してください。" -ForegroundColor Yellow
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

if ($hasGpu) {
    Write-Host "  GPU版で起動します" -ForegroundColor Green
    docker-compose up -d
} else {
    Write-Host "  CPU版で起動します" -ForegroundColor Yellow
    docker-compose -f docker-compose.cpu.yml up -d
}

# 起動待ち
Write-Host ""
Write-Host "サービス起動を待機中（15秒）..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

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

Write-Host "  [..] LLM (LFM2.5): 起動に時間がかかります" -ForegroundColor Cyan
Write-Host "  [..] Embedding (bge-m3): 初回はモデルダウンロード中" -ForegroundColor Cyan

# 完了メッセージ
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "セットアップ完了！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "アクセス先:" -ForegroundColor White
Write-Host "  Forgejo:    http://localhost:3000" -ForegroundColor Cyan
Write-Host "  n8n:        http://localhost:5678  (admin/changeme)" -ForegroundColor Cyan
Write-Host "  Qdrant:     http://localhost:6333/dashboard" -ForegroundColor Cyan
Write-Host "  LLM API:    http://localhost:8080" -ForegroundColor Cyan
Write-Host "  Embedding:  http://localhost:8081" -ForegroundColor Cyan
Write-Host "  Web UI:     http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor White
Write-Host "  1. Forgejoで管理者アカウント作成" -ForegroundColor Yellow
Write-Host "  2. リポジトリ作成" -ForegroundColor Yellow
Write-Host "  3. n8nでWebhookワークフロー設定" -ForegroundColor Yellow
Write-Host "  4. Issueを投稿してテスト" -ForegroundColor Yellow
Write-Host ""
Write-Host "コンテナ状態確認: docker ps" -ForegroundColor Gray
Write-Host "ログ確認: docker-compose logs -f [service]" -ForegroundColor Gray
Write-Host ""
