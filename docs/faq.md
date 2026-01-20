# FAQ（よくある質問）

Broadlistening に関するよくある質問と回答です。

## 目次

1. [導入・セットアップ](#導入セットアップ)
2. [動作環境](#動作環境)
3. [機能・使い方](#機能使い方)
4. [トラブルシューティング](#トラブルシューティング)
5. [運用・メンテナンス](#運用メンテナンス)
6. [セキュリティ](#セキュリティ)
7. [拡張・カスタマイズ](#拡張カスタマイズ)

---

## 導入・セットアップ

### Q: 導入にはどのくらいの知識が必要ですか？

**A:** Docker/Docker Composeの基本操作ができれば導入可能です。

必要なスキル:
- コマンドライン操作（cd, git clone, docker compose up）
- テキストファイルの編集（.env設定）
- Webブラウザでの管理画面操作

不要なスキル:
- プログラミング
- サーバー構築経験
- AI/機械学習の知識

### Q: 導入コストはいくらですか？

**A:** ソフトウェアは完全無料です。

| 項目 | コスト |
|------|--------|
| ソフトウェア | ¥0（OSS） |
| 外部API | ¥0（不要） |
| サーバー | 既存PC or VPS |

**サーバーコスト例:**
- 既存PC利用: ¥0
- さくらVPS 8GB: ¥4,000/月
- AWS t3.xlarge: 約¥12,000/月

### Q: クラウドとオンプレミス、どちらが良いですか？

**A:** 用途によります。

| 観点 | オンプレミス | クラウド |
|------|-------------|---------|
| 初期コスト | 高（PC購入） | 低 |
| 運用コスト | 低（電気代） | 中〜高 |
| スケーラビリティ | 限定的 | 高 |
| データ管理 | 完全自社 | 契約次第 |
| メンテナンス | 自社対応 | 一部自動 |

**推奨:**
- 試験導入: 既存PCでオンプレミス
- 小規模運用: 国内VPS
- 大規模・高可用性: AWS/GCP

### Q: Windows、Mac、Linuxのどれでも動きますか？

**A:** はい、Docker対応環境であればすべて動作します。

| OS | 対応状況 | 備考 |
|----|---------|------|
| Windows 10/11 | ○ | Docker Desktop + WSL2推奨 |
| macOS 12+ | ○ | Docker Desktop |
| Ubuntu 20.04+ | ○ | Docker Engine |
| その他Linux | △ | Docker対応なら可 |

---

## 動作環境

### Q: GPUは必須ですか？

**A:** いいえ、CPUのみでも動作します。ただし処理速度に差があります。

| 環境 | 100件処理 | 1000件処理 |
|------|----------|-----------|
| CPU（4コア/16GB） | 約30分 | 約5時間 |
| GPU（RTX 3060） | 約3分 | 約30分 |

**推奨:**
- 1日100件未満: CPUで十分
- 1日100件以上: GPU推奨
- リアルタイム処理: GPU必須

### Q: メモリはどのくらい必要ですか？

**A:** 最小8GB、推奨16GB以上です。

| メモリ | 同時処理件数 | 用途 |
|-------|------------|------|
| 8GB | 〜50件 | 開発・テスト |
| 16GB | 〜200件 | 小規模運用 |
| 32GB | 〜500件 | 中規模運用 |
| 64GB+ | 500件+ | 大規模運用 |

### Q: ディスク容量はどのくらい必要ですか？

**A:** 最小10GB、運用規模により増加します。

内訳:
- Dockerイメージ: 約5GB
- LLMモデル: 約3GB
- Embeddingモデル: 約2GB
- データ: 1000件あたり約100MB

### Q: 事前に環境をチェックする方法はありますか？

**A:** はい、診断ツールを用意しています。

```bash
# 環境チェック（Docker起動前でもOK）
python scripts/check_requirements.py

# ベンチマーク（Docker起動後）
python scripts/benchmark.py --quick
```

詳細は [hardware-guide.md](hardware-guide.md) を参照してください。

---

## 機能・使い方

### Q: どのような意見収集方法がありますか？

**A:** 4つの入力ソースに対応しています。

1. **Forgejo Issue**: Gitリポジトリ形式で管理
2. **Slack**: チャンネル投稿を自動収集
3. **Webフォーム**: 匿名投稿フォーム
4. **CSV**: 既存データの一括インポート

### Q: 意見はどのように分類されますか？

**A:** LLMが自動的に以下のカテゴリに分類します。

- **問題提起**: 課題や問題点の指摘
- **提案**: 解決策やアイデア
- **質問**: 疑問や問い合わせ
- **要望**: 具体的な要求
- **感謝**: ポジティブなフィードバック
- **その他**: 上記に該当しない

カテゴリは `prompts/classify_opinion.txt` で変更可能です。

### Q: クラスタリングはどのように行われますか？

**A:** K-means法による自動クラスタリングです。

1. 各意見をEmbeddingベクトルに変換
2. ベクトル空間上で類似意見をグループ化
3. 各クラスタにLLMがラベルを自動生成

クラスタ数は意見数に応じて自動調整されます（目安: 20件/クラスタ）。

### Q: 類似意見の検索はできますか？

**A:** はい、ベクトル検索で類似意見を高速に見つけられます。

```bash
# API経由
curl "http://localhost:5000/api/v1/search?q=駐車場が足りない"

# Web UI
意見マップで任意のノードをクリック → 類似意見を表示
```

### Q: 投票機能とは何ですか？

**A:** 意見に対する賛否を集計し、合意度を可視化する機能です。

- 各意見に賛成/反対/中立の投票が可能
- 合意度スコア: 意見の支持集中度（0-1）
- 分断度スコア: 意見対立の度合い（0-1）

### Q: レポートはどのように生成されますか？

**A:** 週次バッチで自動生成、または手動実行できます。

```bash
# 手動実行
docker exec broadlistening-n8n python3 /scripts/weekly_summary.py
```

レポート内容:
- 期間内の意見数、分類別内訳
- 主要クラスタと代表意見
- トレンド分析（テーマの増減）
- 要対応事項のハイライト

---

## トラブルシューティング

### Q: 起動時にエラーが出ます

**A:** よくあるエラーと対処法:

**1. ポートが使用中**
```
Error: port 3000 is already in use
```
→ 他のサービスを停止するか、`.env`でポート変更

**2. メモリ不足**
```
Killed / OOM
```
→ Docker Desktop のメモリ割り当てを増加（Settings → Resources）

**3. モデルダウンロード失敗**
```
Connection timeout
```
→ ネットワーク確認後、再起動（初回は5-10分かかる）

### Q: LLMの応答が遅いです

**A:** 以下を確認してください。

1. **CPU版を使用している場合**: GPU版への移行を検討
2. **メモリ不足**: `docker stats` で確認、スワップ追加
3. **同時リクエスト過多**: レート制限設定を見直し

```bash
# リソース使用状況確認
docker stats

# ベンチマークで処理時間測定
python scripts/benchmark.py --quick
```

### Q: 分類精度が低いです

**A:** プロンプトのカスタマイズを検討してください。

`prompts/classify_opinion.txt` を編集:
- 業界固有の用語を追加
- 分類例を具体的に記載
- カテゴリ定義を明確化

### Q: 日本語が文字化けします

**A:** UTF-8エンコーディングを確認してください。

- CSVインポート: BOM付きUTF-8で保存
- データベース: UTF-8設定を確認
- ターミナル: `chcp 65001`（Windows）

---

## 運用・メンテナンス

### Q: バックアップはどうすれば良いですか？

**A:** 定期バックアップスクリプトを用意しています。

```bash
# 手動バックアップ
./backup.sh

# cron設定例（毎日3時）
0 3 * * * /opt/broadlistening/backup.sh
```

バックアップ対象:
- Qdrant: ベクトルデータ
- Forgejo: Issue、ユーザーデータ
- n8n: ワークフロー設定
- Web: JSONデータ

### Q: アップデートはどうすれば良いですか？

**A:** 以下の手順でアップデートします。

```bash
# 1. バックアップ
./backup.sh

# 2. 最新版取得
git pull origin main

# 3. コンテナ再構築
docker compose down
docker compose pull
docker compose up -d

# 4. 動作確認
curl http://localhost:5000/api/health
```

### Q: ログはどこに保存されますか？

**A:** 各コンテナのログとして保存されます。

```bash
# 全サービスのログ
docker compose logs -f

# 特定サービス
docker compose logs -f llm

# ログファイル場所
docker inspect --format='{{.LogPath}}' broadlistening-llm
```

### Q: 古いデータを削除するには？

**A:** Qdrant APIまたは管理スクリプトで削除できます。

```bash
# 特定期間より古いデータを削除
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py \
  cleanup --older-than 365

# 特定クラスタを削除
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py \
  delete-cluster --id cluster_123
```

---

## セキュリティ

### Q: データは外部に送信されますか？

**A:** いいえ、すべてローカルで処理されます。

- LLM: ローカル実行（LFM2.5）
- Embedding: ローカル実行（bge-m3）
- 外部API: 一切不使用

インターネット通信が発生するのは:
- 初回のモデルダウンロード時のみ
- 明示的に外部連携を設定した場合のみ

### Q: 認証はどのように設定しますか？

**A:** 3つの認証方式に対応しています。

1. **APIキー認証**（デフォルト）
   ```bash
   # .env
   AUTH_METHOD=apikey
   BROADLISTENING_API_KEY=your-secret-key
   ```

2. **LDAP認証**（Active Directory連携）
   ```bash
   AUTH_METHOD=ldap
   LDAP_SERVER=ldap://ad.example.com
   ```

3. **OIDC認証**（Google、Azure AD等）
   ```bash
   AUTH_METHOD=oidc
   OIDC_ISSUER=https://accounts.google.com
   ```

詳細は [configuration.md](configuration.md) を参照。

### Q: 個人情報の取り扱いは？

**A:** システム側での個人情報保護機能:

- **匿名化**: 投稿者名をハッシュ化（オプション）
- **モデレーション**: 不適切投稿の自動フィルタ
- **アクセス制御**: 認証必須設定可能
- **ログ管理**: 個人情報を含むログの自動削除

運用上の注意:
- 収集目的の明示と同意取得
- データ保持期間の設定
- 削除リクエストへの対応手順の整備

---

## 拡張・カスタマイズ

### Q: 分類カテゴリを変更できますか？

**A:** はい、プロンプトファイルを編集します。

`prompts/classify_opinion.txt`:
```
以下の意見を分類してください。

カテゴリ:
- 製品改善: 製品機能への要望
- サポート: サポート対応への意見
- 価格: 価格に関する意見
- その他: 上記に該当しない

意見:
{text}
```

### Q: 別のLLMを使用できますか？

**A:** llama.cpp対応モデルであれば変更可能です。

`docker-compose.yml`:
```yaml
services:
  llm:
    environment:
      - MODEL_PATH=/models/your-model.gguf
```

推奨モデル:
- LFM2.5（デフォルト）: 日本語品質重視
- Llama 3: 多言語、高速
- Mistral: バランス型

### Q: 他システムと連携できますか？

**A:** REST APIで連携可能です。

連携例:
- BIツール: 統計APIからデータ取得
- チャットボット: 検索APIで類似意見提示
- CRM: Issue作成APIで意見登録

```bash
# 意見登録
curl -X POST http://localhost:5000/api/v1/issues \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"title":"要望","body":"〜してほしい"}'
```

### Q: 可視化UIをカスタマイズできますか？

**A:** はい、`web/` ディレクトリのHTML/JS/CSSを編集します。

- `index.html`: 意見マップ
- `graph.js`: vis.js設定
- `style.css`: スタイル

変更後、ブラウザをリロードで反映されます。

---

## その他

### Q: 商用利用は可能ですか？

**A:** はい、MITライセンスのため商用利用可能です。

- 社内システムへの組み込み: ○
- サービスとしての提供: ○
- 改変・再配布: ○（ライセンス表記必要）

### Q: サポートはありますか？

**A:** コミュニティサポートです。

- GitHub Issues: バグ報告、機能要望
- Discussions: 質問、情報交換

有償サポートが必要な場合はIssueでご相談ください。

### Q: コントリビュートするには？

**A:** [CONTRIBUTING.md](../CONTRIBUTING.md) を参照してください。

歓迎する貢献:
- バグ修正
- ドキュメント改善
- 翻訳
- 機能追加（事前にIssueで相談推奨）

---

## 関連ドキュメント

- [クイックスタート](quickstart.md)
- [ユーザーズマニュアル](user-manual.md)
- [設定ガイド](configuration.md)
- [APIリファレンス](api-reference.md)
- [用語集](glossary.md)
