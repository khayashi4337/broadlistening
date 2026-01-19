#!/bin/bash

# ===========================================
# Broadlistening セットアップスクリプト
# ===========================================

set -e

echo "🚀 Broadlistening セットアップを開始します..."

# ディレクトリ作成
echo "📁 ディレクトリ作成..."
mkdir -p models
mkdir -p web/data

# LFM2.5モデルのダウンロード
MODEL_PATH="models/lfm-2.5-3b-q4_k_m.gguf"
if [ ! -f "$MODEL_PATH" ]; then
    echo "📥 LFM2.5モデルをダウンロード中..."
    echo "   （約2GB、数分かかります）"
    wget -q --show-progress -O "$MODEL_PATH" \
        "https://huggingface.co/liquidai/lfm-2.5-3b-gguf/resolve/main/lfm-2.5-3b-q4_k_m.gguf"
else
    echo "✅ LFM2.5モデルは既に存在します"
fi

# 初期データ作成
echo "📝 初期データファイル作成..."
cat > web/data/issues.json << 'EOF'
{
  "clusters": [],
  "issues": [],
  "updated_at": null
}
EOF

# Docker Compose起動
echo "🐳 Docker Compose起動..."
docker-compose up -d

# 起動待ち
echo "⏳ サービス起動を待機中..."
sleep 10

# ヘルスチェック
echo "🔍 ヘルスチェック..."

check_service() {
    local name=$1
    local url=$2
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
        echo "  ✅ $name: OK"
        return 0
    else
        echo "  ❌ $name: FAILED"
        return 1
    fi
}

check_service "Forgejo" "http://localhost:3000"
check_service "n8n" "http://localhost:5678"
check_service "Qdrant" "http://localhost:6333"
check_service "Web UI" "http://localhost:8000"

# LLMとEmbeddingは起動に時間がかかる
echo "  ⏳ LLM (LFM2.5): 起動中..."
echo "  ⏳ Embedding (bge-m3): 初回起動時はモデルDL中..."

echo ""
echo "=========================================="
echo "🎉 セットアップ完了！"
echo "=========================================="
echo ""
echo "📍 アクセス先:"
echo "   Forgejo:    http://localhost:3000"
echo "   n8n:        http://localhost:5678  (admin/changeme)"
echo "   Qdrant:     http://localhost:6333"
echo "   LLM API:    http://localhost:8080"
echo "   Embedding:  http://localhost:8081"
echo "   Web UI:     http://localhost:8000"
echo ""
echo "📖 次のステップ:"
echo "   1. Forgejoで管理者アカウント作成"
echo "   2. リポジトリ作成"
echo "   3. n8nでWebhookワークフロー設定"
echo "   4. Issueを投稿してテスト"
echo ""
