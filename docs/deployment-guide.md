# デプロイガイド

Broadlistening の本番環境へのデプロイ手順です。

## 目次

1. [必要要件](#必要要件)
2. [基本デプロイ（単一サーバー）](#基本デプロイ単一サーバー)
3. [本番環境設定](#本番環境設定)
4. [リバースプロキシ設定](#リバースプロキシ設定)
5. [SSL/TLS設定](#ssltls設定)
6. [監視・ログ](#監視ログ)
7. [バックアップ・リストア](#バックアップリストア)
8. [スケーリング](#スケーリング)

## 必要要件

### ハードウェア

| 環境 | CPU | メモリ | ストレージ |
|------|-----|--------|-----------|
| 最小（開発） | 2コア | 8GB | 20GB |
| 推奨（本番） | 4コア | 16GB | 50GB |
| 大規模 | 8コア+ | 32GB+ | 100GB+ |

### ソフトウェア

- Docker 20.10+
- Docker Compose 2.0+
- (オプション) nginx / traefik
- (オプション) certbot（Let's Encrypt）

## 基本デプロイ（単一サーバー）

### 1. サーバー準備

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git

# Docker サービス起動
sudo systemctl enable docker
sudo systemctl start docker

# ユーザーをdockerグループに追加
sudo usermod -aG docker $USER
```

### 2. リポジトリ取得

```bash
cd /opt
sudo git clone https://github.com/your-org/broadlistening.git
sudo chown -R $USER:$USER broadlistening
cd broadlistening
```

### 3. 環境設定

```bash
cp .env.example .env
```

`.env` を編集：

```bash
# 本番環境設定
NODE_ENV=production

# セキュリティ
N8N_BASIC_AUTH_PASSWORD=<強力なパスワード>
BROADLISTENING_API_KEY=<ランダムな文字列>
JWT_SECRET=<ランダムな文字列>

# 外部アクセス（実際のドメインに変更）
FORGEJO_ROOT_URL=https://git.example.com
N8N_WEBHOOK_URL=https://n8n.example.com
```

### 4. 起動

```bash
# CPU版
docker compose -f docker-compose.cpu.yml up -d

# GPU版（NVIDIA GPU搭載）
docker compose up -d
```

### 5. 初期化

```bash
# Qdrantコレクション作成
docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init

# 動作確認
curl http://localhost:5000/api/health
```

## 本番環境設定

### セキュリティ強化

#### 1. APIキー設定

```bash
# ランダムなAPIキー生成
openssl rand -hex 32
```

`.env`:
```bash
BROADLISTENING_API_KEY=<生成したキー>
```

#### 2. n8n認証

```bash
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<強力なパスワード>
```

#### 3. Forgejo初期設定

初回アクセス時に管理者アカウントを作成。以下を設定：

- 登録を無効化（DISABLE_REGISTRATION=true）
- 強力な管理者パスワード

### リソース制限

`docker-compose.cpu.yml` を編集：

```yaml
services:
  llm:
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G
```

## リバースプロキシ設定

### nginx

`/etc/nginx/sites-available/broadlistening`:

```nginx
# Web UI
server {
    listen 80;
    server_name broadlistening.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name broadlistening.example.com;

    ssl_certificate /etc/letsencrypt/live/broadlistening.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/broadlistening.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Forgejo
server {
    listen 443 ssl http2;
    server_name git.example.com;

    ssl_certificate /etc/letsencrypt/live/git.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/git.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# n8n
server {
    listen 443 ssl http2;
    server_name n8n.example.com;

    ssl_certificate /etc/letsencrypt/live/n8n.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/n8n.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

有効化：

```bash
sudo ln -s /etc/nginx/sites-available/broadlistening /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Traefik

`docker-compose.override.yml`:

```yaml
services:
  traefik:
    image: traefik:v2.10
    command:
      - --api.insecure=true
      - --providers.docker
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.letsencrypt.acme.email=admin@example.com
      - --certificatesresolvers.letsencrypt.acme.storage=/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./acme.json:/acme.json

  web:
    labels:
      - traefik.enable=true
      - traefik.http.routers.web.rule=Host(`broadlistening.example.com`)
      - traefik.http.routers.web.tls.certresolver=letsencrypt
```

## SSL/TLS設定

### Let's Encrypt (certbot)

```bash
# certbot インストール
sudo apt install certbot python3-certbot-nginx

# 証明書取得
sudo certbot --nginx -d broadlistening.example.com -d git.example.com -d n8n.example.com

# 自動更新確認
sudo certbot renew --dry-run
```

### 自己署名証明書（開発用）

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/broadlistening.key \
  -out /etc/ssl/certs/broadlistening.crt
```

## 監視・ログ

### ログ管理

```bash
# ログローテーション設定
cat > /etc/logrotate.d/broadlistening << EOF
/var/log/broadlistening/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

### ヘルスチェック

```bash
# cronで定期監視
*/5 * * * * curl -sf http://localhost:5000/api/health || systemctl restart broadlistening
```

### Prometheus メトリクス（オプション）

`docker-compose.override.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## バックアップ・リストア

### 定期バックアップスクリプト

`/opt/broadlistening/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backup/broadlistening"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Qdrantデータ
docker exec broadlistening-qdrant tar czf - /qdrant/storage > $BACKUP_DIR/qdrant_$DATE.tar.gz

# Forgejoデータ
docker exec broadlistening-forgejo gitea dump -c /data/gitea/conf/app.ini
docker cp broadlistening-forgejo:/tmp/gitea-dump*.zip $BACKUP_DIR/forgejo_$DATE.zip

# n8nデータ
docker exec broadlistening-n8n tar czf - /home/node/.n8n > $BACKUP_DIR/n8n_$DATE.tar.gz

# Webデータ
tar czf $BACKUP_DIR/web_$DATE.tar.gz /opt/broadlistening/web/data

# 古いバックアップ削除（30日以上）
find $BACKUP_DIR -mtime +30 -delete

echo "Backup completed: $DATE"
```

cron設定：

```bash
0 3 * * * /opt/broadlistening/backup.sh >> /var/log/broadlistening/backup.log 2>&1
```

### リストア

```bash
# サービス停止
docker compose down

# Qdrantリストア
docker run --rm -v broadlistening_qdrant_data:/qdrant/storage \
  -v /backup/broadlistening:/backup alpine \
  tar xzf /backup/qdrant_YYYYMMDD.tar.gz -C /

# 再起動
docker compose up -d
```

## スケーリング

### 水平スケーリング（複数サーバー）

```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Web/API │    │  Web/API │    │  Web/API │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
              ┌────────────────────┐
              │  Shared Services   │
              │  - Qdrant          │
              │  - LLM             │
              │  - Forgejo         │
              └────────────────────┘
```

### Kubernetes デプロイ（将来対応予定）

Helmチャートを準備中です。

## トラブルシューティング

### サービスが起動しない

```bash
# 状態確認
docker compose ps
docker compose logs <service-name>

# リソース確認
docker stats
```

### メモリ不足

```bash
# swap追加
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### ディスク容量不足

```bash
# Docker不要イメージ削除
docker system prune -a

# ログファイル削除
docker compose logs --tail=0
```
