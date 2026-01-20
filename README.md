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

1. **Forgejo管理者作成**: http://localhost:3000 にアクセスし、管理者アカウントを作成
2. **リポジトリ作成**: 意見収集用のリポジトリを作成
3. **n8nワークフロー設定**: http://localhost:5678 でWebhookを設定
4. **動作確認**: Issueを投稿してパイプラインが動作することを確認

## API エンドポイント

### LLM API (LFM2.5)

```bash
# ヘルスチェック
curl http://localhost:8080/health

# テキスト分類
curl -X POST http://localhost:8080/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "消費税が高すぎます"}'

# テーマ抽出
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
