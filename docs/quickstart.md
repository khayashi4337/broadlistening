# クイックスタートガイド

Broadlistening を最速で立ち上げるためのステップバイステップガイドです。

## 目次

1. [事前準備（5分）](#事前準備5分)
2. [環境チェック（2分）](#環境チェック2分)
3. [インストール（10分）](#インストール10分)
4. [初期設定（5分）](#初期設定5分)
5. [動作確認（5分）](#動作確認5分)
6. [最初の意見を登録（3分）](#最初の意見を登録3分)
7. [次のステップ](#次のステップ)

---

## 事前準備（5分）

### 必要なソフトウェア

以下がインストールされていることを確認してください。

| ソフトウェア | 確認コマンド | インストール |
|-------------|-------------|-------------|
| Git | `git --version` | [git-scm.com](https://git-scm.com/) |
| Docker | `docker --version` | [docker.com](https://www.docker.com/) |
| Docker Compose | `docker compose version` | Docker Desktop に含まれる |
| Python 3.8+ | `python --version` | [python.org](https://www.python.org/) |

### Windows の場合

1. **Docker Desktop をインストール**
   - [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) をダウンロード
   - インストール後、WSL2 バックエンドを有効化

2. **WSL2 の確認**
   ```powershell
   wsl --version
   ```

3. **Docker Desktop の設定**
   - Settings → Resources → Memory: 8GB以上を割り当て
   - Settings → Resources → WSL Integration: 有効化

### macOS の場合

1. **Docker Desktop をインストール**
   - [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) をダウンロード
   - Apple Silicon (M1/M2) と Intel 両対応

2. **メモリ割り当て**
   - Preferences → Resources → Memory: 8GB以上

### Linux の場合

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git python3

# Docker サービス起動
sudo systemctl enable docker
sudo systemctl start docker

# ユーザーを docker グループに追加（再ログイン必要）
sudo usermod -aG docker $USER
```

---

## 環境チェック（2分）

インストール前に、お使いの環境が要件を満たしているか確認します。

### 1. リポジトリをクローン

```bash
git clone https://github.com/your-org/broadlistening.git
cd broadlistening
```

### 2. 環境診断ツールを実行

```bash
python scripts/check_requirements.py
```

**出力例（正常）:**
```
=== Broadlistening システム要件チェック ===

[CPU] 8コア                          ... OK
[メモリ] 16.0GB / 32.0GB             ... OK
[GPU] NVIDIA GeForce RTX 3060        ... OK
[ディスク] 空き: 150.0GB             ... OK
[Docker] Docker version 24.0.5       ... OK

=== 判定 ===
本番環境として推奨スペックを満たしています
```

**警告が出た場合:**
- メモリ不足 → Docker Desktop のメモリ割り当てを増やす
- ディスク不足 → 不要ファイルを削除
- Docker未検出 → Docker Desktop を起動

詳細は [hardware-guide.md](hardware-guide.md) を参照。

---

## インストール（10分）

### 1. 環境変数を設定

```bash
# テンプレートをコピー
cp .env.example .env
```

`.env` を開いて、最低限以下を確認・変更:

```bash
# 開発環境ならそのままでOK
NODE_ENV=development

# 本番環境なら変更推奨
N8N_BASIC_AUTH_PASSWORD=your-secure-password
BROADLISTENING_API_KEY=your-api-key
```

### 2. Docker コンテナを起動

**CPU版（GPUなし環境）:**
```bash
docker compose -f docker-compose.cpu.yml up -d
```

**GPU版（NVIDIA GPU環境）:**
```bash
docker compose up -d
```

### 3. 起動を待つ

初回起動時はモデルのダウンロードがあるため、5-10分かかります。

```bash
# 起動状況を確認
docker compose ps

# ログを監視（Ctrl+C で終了）
docker compose logs -f
```

**全サービスが `healthy` または `running` になればOK:**
```
NAME                    STATUS
broadlistening-forgejo  Up (healthy)
broadlistening-n8n      Up (healthy)
broadlistening-qdrant   Up (healthy)
broadlistening-llm      Up (healthy)
broadlistening-embed    Up (healthy)
broadlistening-web      Up (healthy)
```

---

## 初期設定（5分）

### 1. Qdrant コレクションを初期化

```bash
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init
```

**出力:**
```
Collection 'broadlistening' created successfully.
```

### 2. Forgejo 管理者アカウントを作成

ブラウザで http://localhost:3000 にアクセス。

初回アクセス時に設定画面が表示されます:

1. **データベース設定**: SQLite（デフォルトのまま）
2. **一般設定**:
   - サイトタイトル: `Broadlistening`
   - 管理者アカウント: ユーザー名、メール、パスワードを入力
3. **「Forgejo をインストール」** をクリック

### 3. n8n ワークフローを有効化

ブラウザで http://localhost:5678 にアクセス。

1. ログイン（.env で設定した認証情報）
2. 左メニュー「Workflows」
3. `issue_pipeline` を開く
4. 右上の「Active」トグルをONに

---

## 動作確認（5分）

### 1. 各サービスにアクセス

| サービス | URL | 確認内容 |
|---------|-----|---------|
| Web UI | http://localhost:8000 | 意見マップが表示される |
| Forgejo | http://localhost:3000 | ログインできる |
| n8n | http://localhost:5678 | ワークフローが表示される |
| Qdrant | http://localhost:6333/dashboard | コレクションが存在する |
| API | http://localhost:5000/api/health | `{"status":"healthy"}` |

### 2. API ヘルスチェック

```bash
curl http://localhost:5000/api/health
```

**期待する応答:**
```json
{
  "status": "healthy",
  "services": {
    "qdrant": "connected",
    "llm": "available",
    "embedding": "available"
  }
}
```

### 3. ベンチマーク（オプション）

実際の処理速度を測定:

```bash
pip install requests  # 初回のみ
python scripts/benchmark.py --quick
```

---

## 最初の意見を登録（3分）

### 方法1: Forgejo Issue から登録

1. http://localhost:3000 にログイン
2. リポジトリを作成（例: `opinions`）
3. 「Issues」→「新しいIssue」
4. タイトルと本文を入力して作成

Webhook が自動で処理し、数秒後に Web UI に反映されます。

### 方法2: Web フォームから登録

1. http://localhost:8000/submit.html にアクセス
2. 意見を入力して送信

### 方法3: API から登録

```bash
curl -X POST http://localhost:5000/api/v1/issues \
  -H "Content-Type: application/json" \
  -d '{
    "title": "テスト意見",
    "body": "駅前の駐輪場が狭くて困っています。朝は停める場所がありません。",
    "source": "api"
  }'
```

### 登録結果を確認

1. **Web UI** (http://localhost:8000)
   - 意見マップにノードが追加される
   - ノードをクリックすると詳細表示

2. **API**
   ```bash
   curl http://localhost:5000/api/v1/issues
   ```

---

## 次のステップ

おめでとうございます！Broadlistening が動作しています。

### 基本的な使い方を学ぶ

- [ユーザーズマニュアル](user-manual.md): 詳細な操作方法
- [用語集](glossary.md): システムの概念を理解

### 本格的に運用する

- [設定ガイド](configuration.md): 環境変数の詳細
- [デプロイガイド](deployment-guide.md): 本番環境構築
- [ハードウェアガイド](hardware-guide.md): スペック最適化

### データを活用する

- [APIリファレンス](api-reference.md): 外部連携
- 週次レポート: `docker exec broadlistening-n8n python3 /scripts/weekly_summary.py`
- CSVエクスポート: Web UI の「エクスポート」ボタン

### トラブル発生時

- [FAQ](faq.md): よくある質問
- [GitHub Issues](https://github.com/your-org/broadlistening/issues): バグ報告

---

## チートシート

よく使うコマンド:

```bash
# 起動
docker compose -f docker-compose.cpu.yml up -d

# 停止
docker compose down

# ログ確認
docker compose logs -f

# 再起動
docker compose restart

# 全削除（データも消える）
docker compose down -v

# バッチクラスタリング
docker exec broadlistening-n8n python3 /scripts/batch_clustering.py

# 週次レポート
docker exec broadlistening-n8n python3 /scripts/weekly_summary.py

# CSVインポート
docker exec broadlistening-n8n python3 /scripts/csv_import.py /data/import.csv
```

---

## 困ったときは

### よくあるエラー

**「port is already in use」**
```bash
# 使用中のポートを確認
netstat -an | grep LISTEN | grep 3000

# 該当プロセスを停止するか、.envでポート変更
```

**「cannot connect to Docker daemon」**
```bash
# Docker Desktop が起動しているか確認
# Windows: タスクトレイのDockerアイコン
# Mac: メニューバーのDockerアイコン
```

**「out of memory」**
```bash
# Docker Desktop のメモリ割り当てを増やす
# Settings → Resources → Memory: 8GB以上
```

### サポート

- [FAQ](faq.md)
- [GitHub Issues](https://github.com/your-org/broadlistening/issues)
- [Discussions](https://github.com/your-org/broadlistening/discussions)
