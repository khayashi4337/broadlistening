# 設定ガイド

Broadlistening の各種設定方法を説明します。

## 目次

1. [環境変数](#環境変数)
2. [認証設定](#認証設定)
3. [モデレーション設定](#モデレーション設定)
4. [LLM設定](#llm設定)
5. [Qdrant設定](#qdrant設定)
6. [n8nワークフロー設定](#n8nワークフロー設定)

## 環境変数

`.env` ファイルで設定します。

### 基本設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `NODE_ENV` | `development` | 環境（development/production） |
| `LOG_LEVEL` | `INFO` | ログレベル（DEBUG/INFO/WARNING/ERROR） |

### API設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `BROADLISTENING_API_KEY` | (空) | API認証キー（空=認証不要） |
| `API_RATE_LIMIT` | `60` | 1分あたりのリクエスト制限 |
| `JWT_SECRET` | `change-me...` | JWTトークン署名シークレット |
| `JWT_EXPIRY` | `3600` | JWTトークン有効期限（秒） |

### 認証設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `AUTH_METHOD` | `apikey` | 認証方式（apikey/ldap/oidc） |

#### LDAP設定

| 変数名 | 説明 |
|--------|------|
| `LDAP_SERVER` | LDAPサーバーURL（例: `ldap://ldap.example.com`） |
| `LDAP_BASE_DN` | ベースDN（例: `dc=example,dc=com`） |
| `LDAP_USER_DN_TEMPLATE` | ユーザーDNテンプレート（例: `uid={username},ou=users`） |
| `LDAP_BIND_DN` | バインドDN（検索用） |
| `LDAP_BIND_PASSWORD` | バインドパスワード |

#### OIDC設定

| 変数名 | 説明 |
|--------|------|
| `OIDC_ISSUER` | OIDCプロバイダーURL |
| `OIDC_CLIENT_ID` | クライアントID |
| `OIDC_CLIENT_SECRET` | クライアントシークレット |
| `OIDC_REDIRECT_URI` | コールバックURL |

### モデレーション設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `MODERATION_ENABLED` | `false` | モデレーション有効化 |
| `BANNED_WORDS_FILE` | (空) | 禁止語句ファイルパス |
| `SPAM_THRESHOLD` | `0.7` | スパム判定閾値（0.0-1.0） |
| `AUTO_APPROVE` | `true` | 自動承認有効化 |

### サービス設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `LLM_API_URL` | `http://llm:8080` | LLM APIエンドポイント |
| `EMBEDDING_API_URL` | `http://embedding:8081` | Embedding APIエンドポイント |
| `QDRANT_HOST` | `qdrant` | Qdrantホスト |
| `QDRANT_PORT` | `6333` | Qdrantポート |
| `FORGEJO_URL` | `http://forgejo:3000` | Forgejo URL |

### n8n設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `N8N_BASIC_AUTH_ACTIVE` | `true` | Basic認証有効化 |
| `N8N_BASIC_AUTH_USER` | `admin` | n8nユーザー名 |
| `N8N_BASIC_AUTH_PASSWORD` | `changeme` | n8nパスワード |
| `N8N_WEBHOOK_URL` | `http://localhost:5678` | Webhook URL |

## 認証設定

### APIキー認証（デフォルト）

最もシンプルな認証方式です。

```bash
# .env
AUTH_METHOD=apikey
BROADLISTENING_API_KEY=your-secret-api-key-here
```

APIキーが空の場合、認証は不要になります（開発環境向け）。

使用方法：
```bash
# Bearer トークン
curl -H "Authorization: Bearer your-secret-api-key-here" \
  http://localhost:5000/api/v1/issues

# クエリパラメータ
curl "http://localhost:5000/api/v1/issues?api_key=your-secret-api-key-here"
```

### LDAP認証

企業のActive DirectoryやOpenLDAPと連携します。

```bash
# .env
AUTH_METHOD=ldap
LDAP_SERVER=ldap://ldap.example.com
LDAP_BASE_DN=dc=example,dc=com
LDAP_USER_DN_TEMPLATE=uid={username},ou=users
```

使用方法：
```bash
# Basic認証
curl -u username:password http://localhost:5000/api/v1/issues
```

必要なPythonライブラリ：
```bash
pip install ldap3
```

### OIDC認証

Google、Azure AD、Keycloakなどと連携します。

```bash
# .env
AUTH_METHOD=oidc
OIDC_ISSUER=https://accounts.google.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=http://localhost:5000/api/auth/callback
```

フロー：
1. `/api/auth/login` にリダイレクト
2. OIDCプロバイダーで認証
3. コールバックでJWTトークン取得
4. JWTトークンでAPI認証

## モデレーション設定

### 基本設定

```bash
# .env
MODERATION_ENABLED=true
AUTO_APPROVE=true
SPAM_THRESHOLD=0.7
```

### 禁止語句ファイル

`banned_words.txt`:
```
# コメント行
禁止語1
禁止語2
不適切な表現
```

```bash
# .env
BANNED_WORDS_FILE=/data/banned_words.txt
```

### モデレーションフロー

```
投稿
  │
  ▼
┌─────────────┐
│ 禁止語チェック │ → 違反 → 拒否
└──────┬──────┘
       │ OK
       ▼
┌─────────────┐
│ スパムチェック │ → スパム → フラグ付け
└──────┬──────┘
       │ OK
       ▼
┌─────────────┐
│ 品質チェック  │ → 低品質 → 警告
└──────┬──────┘
       │ OK
       ▼
┌─────────────┐
│ 重複チェック  │ → 重複 → フラグ付け
└──────┬──────┘
       │ OK
       ▼
   承認（AUTO_APPROVE=true）
   または
   保留（AUTO_APPROVE=false）
```

## LLM設定

### LFM2.5設定

`docker-compose.cpu.yml`:

```yaml
services:
  llm:
    environment:
      - MODEL_PATH=/models/lfm-2.5-3b-q4_k_m.gguf
      - N_CTX=4096          # コンテキスト長
      - N_THREADS=4         # 使用スレッド数
      - N_GPU_LAYERS=0      # GPU使用レイヤー（CPU版は0）
```

### プロンプト設定

`prompts/` ディレクトリ内のテキストファイルを編集：

- `classify_opinion.txt`: 意見分類プロンプト
- `extract_themes.txt`: テーマ抽出プロンプト
- `cluster_summary.txt`: クラスタ要約プロンプト
- `weekly_summary.txt`: 週次レポートプロンプト

### カスタム分類ラベル

`prompts/classify_opinion.txt`:

```
以下の意見を分類してください。

カテゴリ:
- 問題提起: 問題点の指摘
- 提案: 解決策や改善案
- 質問: 疑問や問い合わせ
- 要望: 具体的な要求
- 感謝: ポジティブなフィードバック
- その他: 上記に該当しない

意見:
{text}

分類結果（JSON形式で出力）:
```

## Qdrant設定

### コレクション設定

`scripts/qdrant_manager.py`:

```python
COLLECTION_NAME = "broadlistening"
VECTOR_SIZE = 1024  # bge-m3のベクトルサイズ
DISTANCE = "Cosine"
```

### 類似検索設定

```python
# 類似Issue検索時のパラメータ
SIMILARITY_LIMIT = 5        # 取得件数
SIMILARITY_THRESHOLD = 0.7  # 類似度閾値
```

### クラスタリング設定

`scripts/batch_clustering.py`:

```python
# K-meansクラスタリング設定
MIN_CLUSTERS = 3
MAX_CLUSTERS = 15
OPTIMAL_CLUSTER_SIZE = 20  # 1クラスタあたりの目標Issue数
```

## n8nワークフロー設定

### Forgejo Webhook

1. n8nで `issue_pipeline.json` をインポート
2. Credentialsを設定：
   - Forgejo API Token
   - LLM API URL
   - Embedding API URL
   - Qdrant API URL

3. ワークフローをActivate

### Slack連携

1. Slack Appを作成
2. Event Subscriptions を有効化
3. n8nで `slack_to_issue.json` をインポート
4. Slack Bot Token を設定

### Webフォーム連携

1. n8nで `webform_to_issue.json` をインポート
2. Webhook URLをメモ
3. `web/submit.html` の送信先をWebhook URLに設定

## 設定例

### 開発環境

```bash
# .env
NODE_ENV=development
LOG_LEVEL=DEBUG
BROADLISTENING_API_KEY=
MODERATION_ENABLED=false
```

### 本番環境（小規模）

```bash
# .env
NODE_ENV=production
LOG_LEVEL=INFO
BROADLISTENING_API_KEY=abc123xyz789
AUTH_METHOD=apikey
MODERATION_ENABLED=true
AUTO_APPROVE=true
API_RATE_LIMIT=60
```

### 本番環境（企業向け）

```bash
# .env
NODE_ENV=production
LOG_LEVEL=WARNING
AUTH_METHOD=ldap
LDAP_SERVER=ldap://ad.example.com
LDAP_BASE_DN=dc=example,dc=com
LDAP_USER_DN_TEMPLATE=cn={username},ou=Users
MODERATION_ENABLED=true
AUTO_APPROVE=false
BANNED_WORDS_FILE=/data/banned_words.txt
API_RATE_LIMIT=120
```

## 設定の検証

```bash
# 環境変数確認
docker compose exec api env | grep -E "^(AUTH|MODERATION|API)"

# API接続テスト
curl http://localhost:5000/api/health

# 認証テスト
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/v1/statistics
```
