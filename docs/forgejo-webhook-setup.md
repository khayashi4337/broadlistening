# Forgejo Webhook設定手順

## 概要
Forgejoで新しいIssueが作成されたときに、n8nワークフローを自動発火させるためのWebhook設定手順です。

## 前提条件
- Forgejoが起動している（http://localhost:3000）
- n8nが起動している（http://localhost:5678）
- n8nで「issue_pipeline」ワークフローがインポート済み

## 1. n8nでWebhook URLを確認

1. n8nにログイン: http://localhost:5678
   - ユーザー: admin（デフォルト）
   - パスワード: changeme（デフォルト）

2. 「issue_pipeline」ワークフローを開く

3. 「Webhook」ノードをクリック

4. Webhook URLをコピー
   - 形式: `http://localhost:5678/webhook/forgejo-issue`
   - または: `http://n8n:5678/webhook/forgejo-issue`（Docker内部通信の場合）

## 2. Forgejoでリポジトリ作成

1. Forgejoにログイン: http://localhost:3000

2. 新規リポジトリ作成
   - 名前: `broadlistening-opinions`（例）
   - 説明: ブロードリスニング用の意見収集リポジトリ
   - 公開/非公開: 任意
   - Issueを有効化: ✅ チェック

## 3. Webhook設定

1. リポジトリの「設定」→「Webhooks」に移動

2. 「Webhookを追加」をクリック

3. 以下の設定を入力:

   | 項目 | 設定値 |
   |------|--------|
   | ペイロードURL | `http://n8n:5678/webhook/forgejo-issue` |
   | HTTPメソッド | POST |
   | POST Content Type | application/json |
   | Secret | （空欄でOK。本番環境では設定推奨） |
   | トリガーイベント | ✅ Issues（Issueのみ選択） |
   | アクティブ | ✅ チェック |

4. 「Webhookを追加」ボタンで保存

## 4. 動作確認

### テストIssue作成

1. リポジトリの「Issues」タブに移動

2. 「New Issue」をクリック

3. 以下のように入力:
   - タイトル: `テスト: 駅前に自転車置き場が欲しい`
   - 本文:
     ```
     駅前に自転車置き場が不足しています。
     朝の通勤時間帯は特に混雑しており、路上駐輪が増えています。
     新しい自転車置き場の設置を検討してほしいです。
     ```

4. 「Create Issue」をクリック

### n8nで処理確認

1. n8nの「Executions」タブを開く

2. 最新の実行ログを確認
   - ステータスが「Success」になっていればOK
   - エラーの場合は、各ノードをクリックしてログを確認

3. 期待される処理フロー:
   - Webhook受信 → Embedding生成 → Qdrant保存 → 類似Issue検索 → JSON更新

### Web UIで確認

1. ブラウザで http://localhost:8000 を開く

2. グラフ上に新しいノードが表示されることを確認

3. ノードをクリックして詳細情報を確認

## トラブルシューティング

### Webhookが発火しない

**原因**: n8nのWebhook URLが間違っている

**対処**:
- Forgejo設定画面で「テスト配信」ボタンを押す
- レスポンスコードが200番台であることを確認
- n8nのログで受信を確認

### n8nワークフローがエラー

**原因1**: Embeddingサービスが起動していない

```bash
docker-compose -f docker-compose.cpu.yml logs embedding
```

**原因2**: Qdrantが起動していない

```bash
docker-compose -f docker-compose.cpu.yml logs qdrant
```

**対処**: サービスを再起動
```bash
docker-compose -f docker-compose.cpu.yml restart embedding qdrant
```

### 類似Issue検索が空

**原因**: まだIssueが1件しかない

**対処**: 2件目以降のIssueを作成すると、類似度計算が動作します

## セキュリティ強化（本番環境）

### Webhook Secret設定

1. ランダムな文字列を生成:
   ```bash
   openssl rand -hex 32
   ```

2. Forgejo Webhook設定の「Secret」に貼り付け

3. n8nワークフローの「Webhook」ノードで検証ロジック追加:
   ```javascript
   // Header Authノードで検証
   const receivedSignature = $node["Webhook"].context["headers"]["x-forgejo-signature"];
   const expectedSignature = crypto.createHmac('sha256', 'YOUR_SECRET').update(JSON.stringify($json)).digest('hex');

   if (receivedSignature !== expectedSignature) {
     throw new Error('Invalid signature');
   }
   ```

### HTTPS化（Nginxリバースプロキシ）

本番環境ではLet's EncryptでSSL証明書を取得し、HTTPSでWebhookを受信することを推奨します。

## 次のステップ

- [ ] 複数のIssueを作成してクラスタリング動作を確認
- [ ] LFM2.5による分類・テーマ抽出を確認（Stage 1.3）
- [ ] Web UIでのグラフ操作を習得
