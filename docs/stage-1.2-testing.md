# Stage 1.2 統合テスト手順

## 概要
Stage 1.2で実装した以下の機能を統合テストします。

- Forgejo Webhook → n8n連携
- Embedding生成（bge-m3）
- Qdrant保存・検索
- JSON自動更新

## 前提条件

### Docker環境起動

```bash
cd /f/prj/broadlistening
docker-compose -f docker-compose.cpu.yml up -d
```

### サービス稼働確認

全サービスが起動するまで5-10分かかります（初回はモデルダウンロードで更に時間がかかります）。

```bash
# 全サービスのステータス確認
docker-compose -f docker-compose.cpu.yml ps

# ログ確認
docker-compose -f docker-compose.cpu.yml logs -f
```

期待される状態:
- `broadlistening-forgejo`: Up
- `broadlistening-qdrant`: Up
- `broadlistening-llm`: Up（ヘルスチェック通過まで時間がかかる）
- `broadlistening-embedding`: Up
- `broadlistening-n8n`: Up
- `broadlistening-web`: Up

### ヘルスチェック

各サービスの疎通確認:

```bash
# Forgejo（Web UIアクセス可能か）
curl -I http://localhost:3000

# Qdrant
curl http://localhost:6333/healthz

# Embedding（bge-m3）
curl -X POST http://localhost:8081/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs": "テスト"}'

# LLM（LFM2.5）- ヘルスチェック通過を待つ
curl http://localhost:8080/health

# n8n（Basic認証あり）
curl -u admin:changeme http://localhost:5678/healthz

# Web UI
curl -I http://localhost:8000
```

## テスト1: Pythonスクリプト単体テスト

### 1.1 Embedding生成テスト

```bash
# Docker内でテスト実行
docker exec broadlistening-n8n python3 /scripts/generate_embedding.py --health

# 実際のテキストでテスト
docker exec broadlistening-n8n python3 /scripts/generate_embedding.py "駅前に自転車置き場が欲しい"
```

期待される出力:
```json
{
  "embedding": [0.123, 0.456, ...],  // 1024次元
  "dimension": 1024,
  "text_length": 18
}
```

### 1.2 Qdrantコレクション作成テスト

```bash
# コレクション初期化
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init

# ヘルスチェック
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py health
```

期待される出力:
```
コレクション作成成功: broadlistening_issues
OK: Qdrantは正常に動作しています
```

### 1.3 Qdrant保存・検索テスト

```bash
# テストデータ保存
cat <<EOF | docker exec -i broadlistening-n8n python3 /scripts/qdrant_manager.py upsert
{
  "issue_id": 999,
  "embedding": $(docker exec broadlistening-n8n python3 /scripts/generate_embedding.py "テストIssue" | jq '.embedding'),
  "metadata": {
    "title": "テストIssue",
    "body": "これはテストです",
    "created_at": "2025-01-20T10:00:00Z",
    "url": "http://localhost:3000/test/issues/999",
    "user": "testuser",
    "labels": []
  }
}
EOF

# 類似検索テスト
cat <<EOF | docker exec -i broadlistening-n8n python3 /scripts/qdrant_manager.py search
{
  "embedding": $(docker exec broadlistening-n8n python3 /scripts/generate_embedding.py "テスト" | jq '.embedding'),
  "limit": 5
}
EOF
```

期待される出力:
```json
{
  "results": [
    {
      "issue_id": 999,
      "score": 0.95,
      "title": "テストIssue",
      ...
    }
  ]
}
```

### 1.4 JSONエクスポートテスト

```bash
# web/data/ディレクトリ作成
docker exec broadlistening-web mkdir -p /usr/share/nginx/html/data

# JSON生成（ローカル実行版）
docker exec broadlistening-n8n python3 /scripts/export_issues_json.py

# 生成されたJSONの確認
curl http://localhost:8000/data/issues.json
```

期待される出力:
```json
{
  "nodes": [
    {
      "id": 999,
      "label": "テストIssue",
      "x": 123.45,
      "y": -67.89,
      ...
    }
  ],
  "edges": [],
  "count": 1,
  "generated_at": "2025-01-20T10:30:00"
}
```

## テスト2: n8nワークフロー設定

### 2.1 ワークフローインポート

1. n8nにアクセス: http://localhost:5678
   - ユーザー: `admin`
   - パスワード: `changeme`

2. 左メニュー「Workflows」→「Import from File」

3. `n8n_workflows/issue_pipeline.json` を選択

4. インポート成功を確認

### 2.2 ワークフロー修正（必要に応じて）

n8nのExecute Commandノードは実際の環境では動作しない可能性があるため、HTTP Requestノードに置き換えるか、Pythonスクリプトを直接実行できる環境を用意します。

**代替案**: Docker内でPythonスクリプトを実行するための専用APIサーバーを作成

### 2.3 Webhook URL確認

1. ワークフロー内の「Webhook - Forgejo」ノードをクリック

2. Webhook URLをコピー
   - 例: `http://localhost:5678/webhook/forgejo-issue`

3. ワークフローを「Activate」

## テスト3: Forgejo Webhook設定

[docs/forgejo-webhook-setup.md](./forgejo-webhook-setup.md) の手順に従ってWebhookを設定します。

### 簡易手順

1. Forgejoにアクセス: http://localhost:3000

2. 初期設定（初回のみ）
   - 管理者アカウント作成
   - リポジトリ作成: `broadlistening-opinions`

3. リポジトリ設定 → Webhooks → Add Webhook

4. 設定値:
   - URL: `http://n8n:5678/webhook/forgejo-issue`
   - Content Type: `application/json`
   - Events: `Issues`（Issuesのみチェック）

5. 「Test Delivery」で疎通確認

## テスト4: エンドツーエンドテスト

### 4.1 Issue作成

1. Forgejoで新しいIssue作成

   **タイトル**: テスト: 駅前に自転車置き場が欲しい

   **本文**:
   ```
   駅前に自転車置き場が不足しています。
   朝の通勤時間帯は特に混雑しており、路上駐輪が増えています。
   新しい自転車置き場の設置を検討してほしいです。
   ```

2. 「Create Issue」をクリック

### 4.2 n8n実行ログ確認

1. n8nの「Executions」タブを開く

2. 最新の実行を確認
   - ステータス: Success
   - 各ノードが緑色になっていることを確認

3. エラーの場合
   - 各ノードをクリックして詳細ログを確認
   - Embedding生成、Qdrant保存、検索のどこで失敗したか特定

### 4.3 Qdrantデータ確認

```bash
# 全ポイント取得
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py get-all
```

作成したIssueのデータが含まれていることを確認。

### 4.4 Web UI確認

1. ブラウザで http://localhost:8000 を開く

2. グラフ上にノードが表示されることを確認

3. ノードをクリックして詳細表示

### 4.5 複数Issue作成

類似検索の動作確認のため、追加のIssueを作成:

**Issue 2**:
- タイトル: 駅前の駐輪場を増やしてほしい
- 本文: 駅周辺の自転車駐車場が満車で困っています...

**Issue 3**:
- タイトル: 図書館の開館時間を延長してほしい
- 本文: 仕事帰りに図書館に寄りたいが、閉まっている...

**Issue 4**:
- タイトル: 公園に遊具を増設してほしい
- 本文: 子どもが遊べる遊具が少ない...

### 4.6 類似度検証

n8nログまたはQdrantの検索結果で、Issue 1とIssue 2が高い類似度スコア（0.7以上）を持つことを確認。

Issue 3やIssue 4は異なるテーマなので、類似度が低いことを確認。

## トラブルシューティング

### エラー1: Embedding APIがタイムアウト

**原因**: bge-m3のモデルロードに時間がかかっている

**対処**:
```bash
# Embeddingコンテナのログ確認
docker-compose -f docker-compose.cpu.yml logs embedding

# 再起動
docker-compose -f docker-compose.cpu.yml restart embedding
```

### エラー2: Qdrantに接続できない

**原因**: Qdrantがまだ起動していない

**対処**:
```bash
docker-compose -f docker-compose.cpu.yml restart qdrant

# 起動待ち
sleep 10

# ヘルスチェック
curl http://localhost:6333/healthz
```

### エラー3: n8nでPythonスクリプトが実行できない

**原因**: n8nコンテナにPython環境が不足

**対処1**: n8nコンテナにPythonとrequestsをインストール
```bash
docker exec -u root broadlistening-n8n apk add python3 py3-pip
docker exec -u root broadlistening-n8n pip3 install requests numpy
```

**対処2**: 別途API Gatewayコンテナを作成し、HTTP Requestノードから呼び出す

### エラー4: JSONファイルが更新されない

**原因**: web/data/ディレクトリが存在しない

**対処**:
```bash
docker exec broadlistening-web mkdir -p /usr/share/nginx/html/data
docker exec broadlistening-web chmod 755 /usr/share/nginx/html/data
```

## 成功基準

以下の条件を全て満たせばStage 1.2完了:

- [ ] Forgejoで作成したIssueがn8nワークフローをトリガー
- [ ] Embeddingが正常に生成される（1024次元）
- [ ] QdrantにIssueデータが保存される
- [ ] 類似Issueの検索結果が返る
- [ ] issues.jsonが自動更新される
- [ ] Web UIでグラフが表示される
- [ ] 複数Issueの類似度が適切に計算される

## 次のステップ

Stage 1.2が完了したら、Stage 1.3に進みます:

- LFM2.5による意見タイプ分類（問題提起/提案/質問）
- テーマ抽出
- Web UIのインタラクティブ機能強化
