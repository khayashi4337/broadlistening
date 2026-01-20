# Broadlistening

市民・社員の意見をAIでクラスタリング・可視化するブロードリスニング基盤

## 概要

Forgejoのissue機能で意見を収集し、LLMで分類・要約、ベクトルDBでクラスタリングして可視化するシステムです。
安野たかひろ氏（チームみらい）のブロードリスニングシステムを、Docker Composeで簡単に立ち上げられるように再構築しました。

## 特徴

- 完全無料（外部API不要）
- Docker Compose一発起動
- 日本語対応LLM（LFM2.5）
- CPU環境でも動作

## アーキテクチャ

```
[Forgejo] → [n8n] → [LFM2.5] 分類・要約
    │          │
    │          └→ [bge-m3] Embedding
    │                  │
    │                  └→ [Qdrant] 保存
    │
    └→ [Web UI] vis.jsで可視化
```

## 必要環境

- Docker / Docker Compose
- メモリ: 8GB以上推奨
- ストレージ: 10GB以上（モデルダウンロード用）

## クイックスタート

### Windows (PowerShell)

```powershell
# リポジトリをクローン
git clone <repository-url>
cd broadlistening

# セットアップ実行
.\setup.ps1
```

### Linux / WSL

```bash
# 環境設定
cp .env.example .env
# .envを編集してN8N_PASSWORDを変更

# 起動（CPU版）
docker-compose -f docker-compose.cpu.yml up -d

# 起動確認
docker ps
```

## サービス一覧

| サービス | ポート | 説明 |
|---------|--------|------|
| Forgejo | :3000 | Git/Issue管理 |
| n8n | :5678 | ワークフロー自動化 |
| Qdrant | :6333 | ベクトルDB |
| LLM | :8080 | LFM2.5 API |
| Embedding | :8081 | bge-m3 API |
| Web UI | :8000 | 可視化UI |

## 初回セットアップ

### 1. Docker環境起動

```bash
docker-compose -f docker-compose.cpu.yml up -d
```

全サービスが起動するまで5-10分待ちます（初回はモデルダウンロードで更に時間がかかります）。

### 2. Qdrantコレクション初期化

```bash
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init
```

### 3. Forgejoセットアップ

1. http://localhost:3000 にアクセス
2. 管理者アカウント作成
3. 意見収集用リポジトリ作成（例: `broadlistening-opinions`）

### 4. n8nワークフロー設定

1. http://localhost:5678 にログイン（admin / changeme）
2. `n8n_workflows/issue_pipeline.json` をインポート
3. ワークフローをActivate

### 5. Forgejo Webhook設定

詳細は [docs/forgejo-webhook-setup.md](docs/forgejo-webhook-setup.md) を参照。

1. リポジトリの「設定」→「Webhooks」
2. URL: `http://n8n:5678/webhook/forgejo-issue`
3. Events: `Issues`（のみ）

### 6. 動作確認

1. Forgejoで新しいIssue作成
2. n8nのExecutionsで実行成功を確認
3. http://localhost:8000 でグラフ表示を確認

詳細なテスト手順: [docs/stage-1.2-testing.md](docs/stage-1.2-testing.md)

## Stage 1.2 実装内容

現在のバージョンでは以下の機能が実装されています:

- ✅ Forgejo Webhook連携
- ✅ Embedding生成（bge-m3）
- ✅ Qdrant保存・類似検索
- ✅ issues.json自動更新
- ✅ Web UIでの可視化

### Pythonスクリプト

#### Embedding生成

```bash
docker exec broadlistening-n8n python3 /scripts/generate_embedding.py "テキスト"
```

#### Qdrant管理

```bash
# コレクション初期化
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init

# ヘルスチェック
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py health

# 全ポイント取得
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py get-all
```

#### JSON生成

```bash
docker exec broadlistening-n8n python3 /scripts/export_issues_json.py
```

## API エンドポイント

### LLM API (LFM2.5)

```bash
# ヘルスチェック
curl http://localhost:8080/health

# テキスト分類（Stage 1.3で実装予定）
curl -X POST http://localhost:8080/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "消費税が高すぎます"}'

# テーマ抽出（Stage 1.3で実装予定）
curl -X POST http://localhost:8080/extract_themes \
  -H "Content-Type: application/json" \
  -d '{"text": "教育費の無償化を希望します", "num_themes": 3}'
```

### Embedding API (bge-m3)

```bash
curl -X POST http://localhost:8081/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs": "テスト文章"}'
```

## 停止・再起動

```bash
# 停止
docker-compose -f docker-compose.cpu.yml down

# 再起動
docker-compose -f docker-compose.cpu.yml up -d

# ログ確認
docker-compose -f docker-compose.cpu.yml logs -f llm
```

## トラブルシューティング

### LLMが起動しない
初回起動時はHuggingFaceからモデルをダウンロードするため、5-10分かかります。

```bash
docker logs broadlistening-llm
```

### メモリ不足
docker-compose.cpu.ymlの`deploy.resources.limits.memory`を調整してください。

## ライセンス

MIT License

## 参考

- [Talk to the City](https://github.com/AIObjectives/talk-to-the-city-reports)
- [広聴AI](https://github.com/digitaldemocracy2030/kouchou-ai)
- [LFM2.5](https://huggingface.co/LiquidAI/LFM2.5-1.2B-JP)
