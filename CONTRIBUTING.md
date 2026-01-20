# コントリビューションガイド

Broadlistening へのコントリビューションに興味を持っていただきありがとうございます。

## 行動規範

このプロジェクトでは、オープンで歓迎的な環境を維持することを約束します。
すべての参加者は、敬意を持って互いに接することが求められます。

## コントリビューションの方法

### バグ報告

バグを発見した場合は、以下の情報を含めて Issue を作成してください：

1. **環境情報**
   - OS（Windows/Linux/macOS）
   - Docker バージョン
   - Docker Compose バージョン

2. **再現手順**
   - バグを再現するための具体的な手順

3. **期待される動作**
   - 本来どのように動作すべきか

4. **実際の動作**
   - 実際に起きた動作（エラーメッセージ、スクリーンショットなど）

### 機能リクエスト

新機能の提案は Issue で受け付けています。以下を含めてください：

- 機能の説明
- ユースケース（なぜその機能が必要か）
- 可能であれば実装案

### プルリクエスト

#### 開発環境のセットアップ

```bash
# リポジトリをフォーク・クローン
git clone https://github.com/YOUR_USERNAME/broadlistening.git
cd broadlistening

# 開発ブランチを作成
git checkout -b feature/your-feature-name

# Python仮想環境（APIサーバー開発時）
python -m venv venv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

#### コーディング規約

**Python**
- PEP 8 に従う
- 型ヒントを使用
- docstring を記述（日本語可）

```python
def process_issue(issue_id: int, content: str) -> dict:
    """
    Issueを処理する

    Args:
        issue_id: IssueのID
        content: Issue本文

    Returns:
        処理結果を含む辞書
    """
    pass
```

**JavaScript**
- ES6+ 構文を使用
- セミコロンを使用
- XSS対策として `escapeHTML` を使用

```javascript
// 良い例
const escapeHTML = (str) => {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
};

element.textContent = userInput;  // 安全
element.innerHTML = escapeHTML(userInput);  // HTMLを使う場合
```

**コミットメッセージ**

```
<type>: <subject>

<body>

<footer>
```

type:
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント
- `style`: フォーマット（コードの変更なし）
- `refactor`: リファクタリング
- `test`: テスト追加・修正
- `chore`: ビルド・ツール関連

例：
```
feat: 週次レポートにPDFエクスポート機能を追加

- WeasyPrintを使用してPDF生成
- レポートページにダウンロードボタンを追加
- 日本語フォントに対応

Closes #123
```

#### プルリクエストの手順

1. **ブランチを最新に更新**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **構文チェック**
   ```bash
   python -m py_compile scripts/*.py api/*.py
   ```

3. **変更をコミット**
   ```bash
   git add .
   git commit -m "feat: 機能の説明"
   ```

4. **フォークにプッシュ**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **プルリクエストを作成**
   - タイトル: 変更内容の要約
   - 本文: 詳細な説明、関連Issue、テスト方法

#### レビュープロセス

1. CI チェックがパス
2. コードレビュー（メンテナーが実施）
3. 必要に応じて修正
4. 承認後マージ

### ドキュメント

ドキュメントの改善も歓迎します：

- 誤字脱字の修正
- 説明の追加・明確化
- 翻訳（英語など）
- チュートリアルの追加

## 開発のヒント

### ローカルでのテスト

```bash
# Docker環境を起動
docker-compose -f docker-compose.cpu.yml up -d

# APIサーバーをローカルで起動（ホットリロード）
cd api && python server.py --debug --port 5001

# Webページをローカルでテスト
cd web && python -m http.server 8001
```

### デバッグ

```bash
# n8nのログ
docker-compose logs -f n8n

# LLMのログ
docker-compose logs -f llm

# Qdrantの状態確認
curl http://localhost:6333/collections
```

### よくある問題

**Q: LLMの応答が遅い**
A: CPU環境では初回のモデルロードに時間がかかります。`docker logs broadlistening-llm` で状態を確認してください。

**Q: Qdrantに接続できない**
A: コンテナが起動しているか確認し、`qdrant_manager.py init` でコレクションを初期化してください。

## 質問・サポート

- GitHub Issues: バグ報告、機能リクエスト
- GitHub Discussions: 質問、議論

## ライセンス

コントリビューションは MIT License の下でライセンスされます。
