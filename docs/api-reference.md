# API リファレンス

Broadlistening REST API の詳細リファレンスです。

## 概要

- **ベースURL**: `http://localhost:5000`
- **データ形式**: JSON
- **文字エンコーディング**: UTF-8
- **レート制限**: 60リクエスト/分（デフォルト）

## 認証

### APIキー認証

APIキーが設定されている場合（`BROADLISTENING_API_KEY`環境変数）、以下の方法で認証が必要です。

#### Bearer トークン（推奨）

```http
Authorization: Bearer YOUR_API_KEY
```

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/v1/issues
```

#### クエリパラメータ

```http
GET /api/v1/issues?api_key=YOUR_API_KEY
```

### JWT認証

LDAP/OIDCで認証後、JWTトークンを使用：

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 認証なし

`BROADLISTENING_API_KEY`が空の場合、認証は不要です。

## エンドポイント

### ヘルスチェック

#### GET /api/health

サーバーの稼働状態を確認します。

**レスポンス**

```json
{
  "status": "ok",
  "timestamp": "2025-01-21T12:00:00.000000"
}
```

---

### 意見（Issues）

#### GET /api/v1/issues

意見一覧を取得します。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `page` | int | 1 | ページ番号 |
| `per_page` | int | 50 | 1ページあたりの件数（最大100） |
| `type` | string | - | 意見タイプでフィルタ（問題提起/提案/質問/その他） |
| `theme` | string | - | テーマでフィルタ |

**レスポンス**

```json
{
  "data": [
    {
      "id": 1,
      "title": "消費税が高すぎます",
      "body": "消費税10%は家計を圧迫しています...",
      "opinion_type": "問題提起",
      "themes": ["税金", "生活"],
      "reactions": {
        "positive": 15,
        "negative": 3
      },
      "created_at": "2025-01-20T10:30:00Z",
      "url": "http://localhost:3000/repo/issues/1"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

#### GET /api/v1/issues/:id

特定の意見を取得します。

**パスパラメータ**

| パラメータ | 型 | 説明 |
|-----------|------|------|
| `id` | int | Issue ID |

**レスポンス**

```json
{
  "data": {
    "id": 1,
    "title": "消費税が高すぎます",
    "body": "消費税10%は家計を圧迫しています...",
    "opinion_type": "問題提起",
    "themes": ["税金", "生活"],
    "reactions": {
      "positive": 15,
      "negative": 3
    },
    "created_at": "2025-01-20T10:30:00Z",
    "url": "http://localhost:3000/repo/issues/1"
  }
}
```

**エラーレスポンス**

```json
{
  "error": "Not Found",
  "message": "Issue not found"
}
```

---

### クラスタ（Clusters）

#### GET /api/v1/clusters

クラスタ一覧を取得します。

**レスポンス**

```json
{
  "data": [
    {
      "id": 0,
      "label": "税金・財政",
      "summary": "消費税や所得税に関する意見が集まっています...",
      "issue_count": 25,
      "top_themes": ["税金", "財政", "生活"],
      "representative_issues": [1, 5, 12]
    }
  ],
  "total_issues": 150,
  "num_clusters": 8
}
```

#### GET /api/v1/clusters/:id

特定のクラスタを取得します。

**レスポンス**

```json
{
  "data": {
    "id": 0,
    "label": "税金・財政",
    "summary": "消費税や所得税に関する意見が集まっています...",
    "issue_count": 25,
    "top_themes": ["税金", "財政", "生活"],
    "issues": [
      {
        "id": 1,
        "title": "消費税が高すぎます",
        "similarity": 0.95
      }
    ]
  }
}
```

---

### 投票分析（Voting）

#### GET /api/v1/voting

投票データと分析結果を取得します。

**レスポンス**

```json
{
  "summary": {
    "total_issues": 150,
    "total_positive": 1200,
    "total_negative": 450,
    "overall_approval_rate": 0.727,
    "overall_consensus": 0.65,
    "overall_division": 0.35,
    "confidence": 0.8
  },
  "cluster_trends": [
    {
      "cluster_id": 0,
      "label": "税金・財政",
      "issue_count": 25,
      "total_votes": 180,
      "avg_approval_rate": 0.72
    }
  ],
  "updated_at": "2025-01-21T12:00:00Z"
}
```

---

### レポート（Reports）

#### GET /api/v1/reports

週次レポート一覧を取得します。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `limit` | int | 5 | 取得件数（最大10） |

**レスポンス**

```json
{
  "data": [
    {
      "week": "2025-W03",
      "period": {
        "start": "2025-01-13",
        "end": "2025-01-19"
      },
      "summary": {
        "new_issues": 45,
        "total_issues": 150,
        "new_clusters": 2,
        "highlights": "今週は税金に関する意見が増加しました..."
      },
      "action_items": [
        {
          "title": "消費税軽減措置の検討",
          "priority": "high",
          "related_cluster": "税金・財政"
        }
      ]
    }
  ],
  "updated_at": "2025-01-21T00:00:00Z"
}
```

#### GET /api/v1/reports/latest

最新のレポートを取得します。

**レスポンス**

```json
{
  "data": {
    "week": "2025-W03",
    "period": { ... },
    "summary": { ... },
    "action_items": [ ... ]
  }
}
```

---

### 統計情報（Statistics）

#### GET /api/v1/statistics

全体の統計情報を取得します。

**レスポンス**

```json
{
  "total_issues": 150,
  "total_clusters": 8,
  "total_votes": 1650,
  "by_type": {
    "問題提起": 65,
    "提案": 50,
    "質問": 25,
    "その他": 10
  },
  "top_themes": [
    ["税金", 45],
    ["教育", 38],
    ["医療", 32]
  ],
  "consensus_score": 0.65
}
```

---

### 検索（Search）

#### GET /api/v1/search

意見を検索します。

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `q` | string | Yes | 検索クエリ（2文字以上） |

**レスポンス**

```json
{
  "data": [
    {
      "id": 1,
      "title": "消費税が高すぎます",
      "body": "消費税10%は家計を圧迫しています...",
      "opinion_type": "問題提起",
      "themes": ["税金", "生活"]
    }
  ],
  "total": 15,
  "query": "消費税"
}
```

**エラーレスポンス**

```json
{
  "error": "Bad Request",
  "message": "Search query must be at least 2 characters"
}
```

---

## エラーレスポンス

すべてのエラーは以下の形式で返されます：

```json
{
  "error": "Error Type",
  "message": "Detailed error message"
}
```

### HTTPステータスコード

| コード | 説明 |
|--------|------|
| 200 | 成功 |
| 400 | リクエストエラー（パラメータ不正など） |
| 401 | 認証エラー（APIキー不正など） |
| 404 | リソースが見つからない |
| 429 | レート制限超過 |
| 500 | サーバー内部エラー |

---

## レート制限

- デフォルト: 60リクエスト/分/IPアドレス
- 制限超過時: `429 Too Many Requests`
- 環境変数 `API_RATE_LIMIT` で変更可能

**レート制限エラー**

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded"
}
```

---

## CORS

すべての `/api/*` エンドポイントは CORS 有効です。

```
Access-Control-Allow-Origin: *
```

---

## サンプルコード

### Python

```python
import requests

BASE_URL = "http://localhost:5000"
API_KEY = "your-api-key"  # オプション

headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

# 意見一覧取得
response = requests.get(f"{BASE_URL}/api/v1/issues", headers=headers)
issues = response.json()

# 検索
response = requests.get(
    f"{BASE_URL}/api/v1/search",
    params={"q": "消費税"},
    headers=headers
)
results = response.json()
```

### JavaScript

```javascript
const BASE_URL = 'http://localhost:5000';
const API_KEY = 'your-api-key'; // オプション

const headers = API_KEY ? { 'Authorization': `Bearer ${API_KEY}` } : {};

// 意見一覧取得
const response = await fetch(`${BASE_URL}/api/v1/issues`, { headers });
const data = await response.json();

// 検索
const searchResponse = await fetch(
  `${BASE_URL}/api/v1/search?q=${encodeURIComponent('消費税')}`,
  { headers }
);
const results = await searchResponse.json();
```

### curl

```bash
# 意見一覧
curl http://localhost:5000/api/v1/issues

# 認証付き
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/v1/issues

# 検索
curl "http://localhost:5000/api/v1/search?q=消費税"

# 統計
curl http://localhost:5000/api/v1/statistics
```
