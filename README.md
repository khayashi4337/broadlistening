# Broadlistening

市民・社員の意見をAIでクラスタリング・可視化するブロードリスニング基盤

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 概要

Forgejoのissue機能で意見を収集し、LLMで分類・要約、ベクトルDBでクラスタリングして可視化するシステムです。
安野たかひろ氏（チームみらい）のブロードリスニングシステムを、Docker Composeで簡単に立ち上げられるように再構築しました。

**親和図法（KJ法）のデジタル・自動化版** として、大量の意見を効率的に整理・分析できます。

## 特徴

- **完全無料** - 外部API不要、ローカルLLM使用
- **Docker Compose一発起動** - 複雑な設定不要
- **日本語対応LLM** - LFM2.5で高品質な分類・要約
- **CPU環境でも動作** - GPUなしでもOK
- **マルチソース入力** - Forgejo、Slack、Webフォーム、CSV対応
- **REST API** - 外部システム連携可能
- **認証機能** - APIキー、LDAP、OIDC対応

## デモ画面

### 意見マップ（vis.js）
クラスタリングされた意見をネットワークグラフで可視化

### 公開ダッシュボード
外部公開用の読み取り専用ダッシュボード

### 投票分析
合意度・分断度のスコアリングと可視化

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    Broadlistening 構成図                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   入力ソース                                                 │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│   │ Forgejo │  │  Slack  │  │Webフォーム│  │   CSV   │       │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│        │            │            │            │             │
│        └────────────┴─────┬──────┴────────────┘             │
│                           ▼                                 │
│                    ┌──────────┐                             │
│                    │   n8n    │ ワークフロー自動化           │
│                    └────┬─────┘                             │
│                         │                                   │
│           ┌─────────────┼─────────────┐                     │
│           ▼             ▼             ▼                     │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│    │  LFM2.5  │  │  bge-m3  │  │  Qdrant  │                │
│    │ 分類・要約 │  │Embedding │  │ベクトルDB │                │
│    └──────────┘  └──────────┘  └──────────┘                │
│                         │                                   │
│                         ▼                                   │
│              ┌─────────────────────┐                        │
│              │      Web UI         │                        │
│              │  vis.js グラフ表示   │                        │
│              └─────────────────────┘                        │
│                         │                                   │
│                         ▼                                   │
│              ┌─────────────────────┐                        │
│              │     REST API        │                        │
│              │   外部システム連携    │                        │
│              └─────────────────────┘                        │
│                                                             │
│   外部API: なし / 月額コスト: ¥0（電気代のみ）               │
└─────────────────────────────────────────────────────────────┘
```

## 必要環境

- Docker / Docker Compose v2.0+
- メモリ: 8GB以上推奨（16GB推奨）
- ストレージ: 10GB以上（モデルダウンロード用）
- OS: Windows 10/11、Linux、macOS

## クイックスタート

### 1. リポジトリをクローン

```bash
git clone https://github.com/your-org/broadlistening.git
cd broadlistening
```

### 2. 環境設定

```bash
cp .env.example .env
# .envを編集して必要な設定を変更
```

### 3. 起動

```bash
# CPU版（GPUなし環境）
docker-compose -f docker-compose.cpu.yml up -d

# GPU版（NVIDIA GPU環境）
docker-compose up -d
```

### 4. 初期設定

```bash
# Qdrantコレクション初期化
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init
```

### 5. アクセス

| サービス | URL | 説明 |
|---------|-----|------|
| Web UI | http://localhost:8000 | 意見マップ可視化 |
| 公開ダッシュボード | http://localhost:8000/public/ | 外部公開用 |
| Forgejo | http://localhost:3000 | Git/Issue管理 |
| n8n | http://localhost:5678 | ワークフロー管理 |
| REST API | http://localhost:5000 | API エンドポイント |
| Qdrant | http://localhost:6333 | ベクトルDB管理画面 |

## 機能一覧

### Phase 1: 基盤構築
- ✅ Docker環境構築
- ✅ Forgejo Webhook連携
- ✅ Embedding生成（bge-m3）
- ✅ Qdrant保存・類似検索
- ✅ LLM分類（問題提起/提案/質問）
- ✅ テーマ抽出
- ✅ vis.js可視化

### Phase 2: 分析強化
- ✅ バッチクラスタリング（K-means）
- ✅ クラスタ要約生成
- ✅ 投票分析・合意度スコア
- ✅ 週次レポート生成
- ✅ テーマトレンド分析

### Phase 3: 拡張・スケール
- ✅ マルチソース入力（Slack、Webフォーム、CSV）
- ✅ ソース統合・正規化
- ✅ 公開ダッシュボード
- ✅ REST API
- ✅ 認証連携（APIキー、LDAP、OIDC）
- ✅ モデレーション・フィルタ

## ディレクトリ構成

```
broadlistening/
├── docker-compose.yml          # GPU版構成
├── docker-compose.cpu.yml      # CPU版構成
├── .env.example                # 環境変数テンプレート
├── api/                        # REST API
│   ├── server.py              # Flask APIサーバー
│   ├── auth.py                # 認証モジュール
│   └── moderation.py          # モデレーション
├── scripts/                    # ユーティリティスクリプト
│   ├── generate_embedding.py  # Embedding生成
│   ├── qdrant_manager.py      # Qdrant管理
│   ├── classify_opinion.py    # 意見分類
│   ├── extract_themes.py      # テーマ抽出
│   ├── batch_clustering.py    # バッチクラスタリング
│   ├── weekly_summary.py      # 週次レポート
│   ├── csv_import.py          # CSVインポート
│   └── source_normalizer.py   # ソース正規化
├── n8n_workflows/              # n8nワークフロー定義
│   ├── issue_pipeline.json    # Forgejo連携
│   ├── slack_to_issue.json    # Slack連携
│   └── webform_to_issue.json  # Webフォーム連携
├── prompts/                    # LLMプロンプト
│   ├── classify_opinion.txt   # 分類用
│   ├── extract_themes.txt     # テーマ抽出用
│   └── weekly_summary.txt     # 週次レポート用
├── web/                        # フロントエンド
│   ├── index.html             # 意見マップ
│   ├── clusters.html          # クラスタ要約
│   ├── voting.html            # 投票分析
│   ├── reports.html           # 週次レポート
│   ├── submit.html            # 意見投稿フォーム
│   ├── public/                # 公開ダッシュボード
│   │   └── dashboard.html
│   └── data/                  # JSONデータ
├── templates/                  # テンプレート
│   └── import_template.csv    # CSVインポート用
└── docs/                       # ドキュメント
    ├── api-reference.md       # API リファレンス
    ├── deployment-guide.md    # デプロイガイド
    └── configuration.md       # 設定ガイド
```

## REST API

### エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/v1/issues` | 意見一覧取得 |
| GET | `/api/v1/issues/:id` | 意見詳細取得 |
| GET | `/api/v1/clusters` | クラスタ一覧取得 |
| GET | `/api/v1/clusters/:id` | クラスタ詳細取得 |
| GET | `/api/v1/voting` | 投票データ取得 |
| GET | `/api/v1/reports` | レポート一覧取得 |
| GET | `/api/v1/reports/latest` | 最新レポート取得 |
| GET | `/api/v1/statistics` | 統計情報取得 |
| GET | `/api/v1/search?q=` | 意見検索 |

### 認証

```bash
# APIキー認証（Bearer）
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/v1/issues

# APIキー認証（クエリパラメータ）
curl "http://localhost:5000/api/v1/issues?api_key=YOUR_API_KEY"
```

詳細は [docs/api-reference.md](docs/api-reference.md) を参照。

## 設定

### 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `BROADLISTENING_API_KEY` | (空) | API認証キー（空の場合は認証不要） |
| `AUTH_METHOD` | `apikey` | 認証方式（apikey/ldap/oidc） |
| `MODERATION_ENABLED` | `false` | モデレーション有効化 |
| `API_RATE_LIMIT` | `60` | 1分あたりのリクエスト制限 |

詳細は [docs/configuration.md](docs/configuration.md) を参照。

## 運用

### バッチ処理

```bash
# 週次クラスタリング
docker exec broadlistening-n8n python3 /scripts/batch_clustering.py

# 週次レポート生成
docker exec broadlistening-n8n python3 /scripts/weekly_summary.py

# CSVインポート
docker exec broadlistening-n8n python3 /scripts/csv_import.py /data/import.csv
```

### ログ確認

```bash
# 全サービスのログ
docker-compose logs -f

# 特定サービスのログ
docker-compose logs -f llm
docker-compose logs -f n8n
```

### バックアップ

```bash
# Qdrantデータのバックアップ
docker exec broadlistening-qdrant qdrant-backup create backup-$(date +%Y%m%d)

# Forgejoデータのバックアップ
docker exec broadlistening-forgejo gitea dump
```

## トラブルシューティング

### LLMが起動しない

初回起動時はHuggingFaceからモデルをダウンロードするため、5-10分かかります。

```bash
docker logs broadlistening-llm
```

### メモリ不足

`docker-compose.cpu.yml`の`deploy.resources.limits.memory`を調整してください。

### Qdrant接続エラー

```bash
# Qdrantの状態確認
curl http://localhost:6333/collections

# コレクション再初期化
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init
```

### n8nワークフローが動作しない

1. n8n管理画面でワークフローがActivateされているか確認
2. Credentialsが正しく設定されているか確認
3. Execution履歴でエラーメッセージを確認

## 開発

### ローカル開発環境

```bash
# Python仮想環境
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows

# 依存関係インストール
pip install -r requirements.txt

# APIサーバー起動（開発モード）
cd api && python server.py --debug
```

### テスト

```bash
# 構文チェック
python -m py_compile scripts/*.py api/*.py

# ユニットテスト（将来実装予定）
pytest tests/
```

## コントリビューション

プルリクエストを歓迎します。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照。

## 謝辞

このプロジェクトは以下のプロジェクトに影響を受けています：

- [Talk to the City](https://github.com/AIObjectives/talk-to-the-city-reports) - AIObjectives
- [広聴AI](https://github.com/digitaldemocracy2030/kouchou-ai) - デジタルデモクラシー2030
- [LFM2.5](https://huggingface.co/LiquidAI/LFM2.5-1.2B-JP) - Liquid AI

## 関連リンク

- [安野たかひろ（チームみらい）](https://teammirai.co.jp/)
- [vTaiwan](https://vtaiwan.tw/)
- [Polis](https://pol.is/)
