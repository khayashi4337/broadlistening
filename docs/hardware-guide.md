# ハードウェアガイド

Broadlistening を快適に動作させるためのハードウェア要件と推奨スペックです。

## 目次

1. [クイック診断](#クイック診断)
2. [最小要件](#最小要件)
3. [推奨スペック](#推奨スペック)
4. [処理時間の目安](#処理時間の目安)
5. [GPU vs CPU](#gpu-vs-cpu)
6. [クラウド環境](#クラウド環境)
7. [トラブルシューティング](#トラブルシューティング)

## クイック診断

まずはシステム診断ツールを実行してください：

```bash
python scripts/check_requirements.py
```

このツールが以下をチェックします：
- CPU（コア数）
- メモリ容量
- GPU（NVIDIA検出）
- ディスク空き容量
- Docker環境

## 最小要件

これ以下のスペックでは動作しません。

| 項目 | 最小要件 |
|------|---------|
| CPU | 2コア以上 |
| メモリ | 8GB |
| ディスク | 10GB空き |
| OS | Windows 10, Ubuntu 20.04, macOS 12 以降 |
| Docker | Docker 20.10+ / Docker Compose 2.0+ |

## 推奨スペック

### 小規模（〜500件/月）

| 項目 | 推奨 |
|------|------|
| CPU | 4コア / Intel i5相当 |
| メモリ | 16GB |
| GPU | なしでも可 |
| ディスク | 20GB SSD |

```
処理時間の目安:
- 100件: 約30分〜1時間
- 500件: 約2〜4時間
```

### 中規模（〜2000件/月）

| 項目 | 推奨 |
|------|------|
| CPU | 8コア / Intel i7, Ryzen 7相当 |
| メモリ | 32GB |
| GPU | NVIDIA RTX 3060 (8GB VRAM) 以上推奨 |
| ディスク | 50GB SSD |

```
処理時間の目安（GPU利用時）:
- 100件: 約3分
- 1000件: 約30分
- 2000件: 約1時間
```

### 大規模（〜10000件/月）

| 項目 | 推奨 |
|------|------|
| CPU | 16コア / Xeon, Ryzen 9相当 |
| メモリ | 64GB |
| GPU | NVIDIA RTX 4080 (16GB VRAM) 以上 |
| ディスク | 100GB NVMe SSD |

```
処理時間の目安（GPU利用時）:
- 1000件: 約15分
- 5000件: 約1時間
- 10000件: 約2時間
```

## 処理時間の目安

### CPU版（GPUなし）

| 件数 | 低スペック | 標準 | 高スペック |
|------|-----------|------|-----------|
| 100件 | 1時間 | 30分 | 15分 |
| 500件 | 5時間 | 2.5時間 | 1時間 |
| 1000件 | 10時間 | 5時間 | 2時間 |
| 5000件 | 50時間 | 25時間 | 10時間 |

※ 低スペック: 2コア/8GB、標準: 4コア/16GB、高スペック: 8コア/32GB

### GPU版

| 件数 | RTX 3060 | RTX 4080 | A100 |
|------|----------|----------|------|
| 100件 | 3分 | 2分 | 1分 |
| 500件 | 15分 | 8分 | 4分 |
| 1000件 | 30分 | 15分 | 8分 |
| 5000件 | 2.5時間 | 1.5時間 | 40分 |

## GPU vs CPU

### GPUを使うべき場合

- 1日100件以上処理する
- リアルタイム性が求められる
- 定期的に大量データを処理する

### CPUでも十分な場合

- 1日数十件程度
- 夜間バッチ処理で問題ない
- 初期費用を抑えたい

### GPU環境の構築

#### Windows + NVIDIA GPU

1. **NVIDIAドライバをインストール**
   - [NVIDIAドライバダウンロード](https://www.nvidia.com/Download/index.aspx)

2. **CUDA Toolkitをインストール**（オプション）
   - [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)

3. **Docker Desktop でGPUを有効化**
   - Settings → Resources → WSL Integration → GPU対応

4. **GPU版で起動**
   ```bash
   docker compose up -d
   ```

#### Linux + NVIDIA GPU

1. **NVIDIAドライバをインストール**
   ```bash
   sudo apt install nvidia-driver-535
   ```

2. **NVIDIA Container Toolkitをインストール**
   ```bash
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt update
   sudo apt install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

3. **GPU版で起動**
   ```bash
   docker compose up -d
   ```

#### 確認

```bash
# GPU認識確認
nvidia-smi

# Docker内からGPU確認
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

## クラウド環境

### AWS

| インスタンス | スペック | 月額目安 | 用途 |
|------------|---------|---------|------|
| t3.large | 2vCPU/8GB | $60 | 開発・テスト |
| t3.xlarge | 4vCPU/16GB | $120 | 小規模運用 |
| g4dn.xlarge | 4vCPU/16GB + T4 | $380 | 中規模運用 |
| g5.xlarge | 4vCPU/16GB + A10G | $750 | 大規模運用 |

### GCP

| インスタンス | スペック | 月額目安 | 用途 |
|------------|---------|---------|------|
| e2-standard-2 | 2vCPU/8GB | $50 | 開発・テスト |
| e2-standard-4 | 4vCPU/16GB | $100 | 小規模運用 |
| n1-standard-4 + T4 | 4vCPU/15GB + T4 | $350 | 中規模運用 |

### さくらVPS / ConoHa

| プラン | スペック | 月額 | 用途 |
|-------|---------|------|------|
| 2GB | 3コア/2GB | ¥1,000 | テストのみ |
| 8GB | 6コア/8GB | ¥4,000 | 小規模 |
| 16GB | 8コア/16GB | ¥8,000 | 標準運用 |
| 32GB | 12コア/32GB | ¥16,000 | 中規模 |

※ GPUインスタンスは国内VPSでは少ない。AWSやGCPを推奨。

## トラブルシューティング

### メモリ不足（OOM）

**症状**: コンテナが突然停止、"Killed" メッセージ

**対処**:
1. メモリ制限を緩和
   ```yaml
   # docker-compose.cpu.yml
   services:
     llm:
       deploy:
         resources:
           limits:
             memory: 6G  # 4G → 6Gに増加
   ```

2. スワップを追加（Linux）
   ```bash
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### GPU認識されない

**症状**: `nvidia-smi` が動かない、GPU版が CPU で動作

**対処**:
1. ドライバ確認
   ```bash
   nvidia-smi
   ```

2. Docker GPU対応確認
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

3. nvidia-container-toolkit 再インストール

### 処理が遅い

**症状**: 期待より処理時間が長い

**対処**:
1. ベンチマーク実行
   ```bash
   python scripts/benchmark.py
   ```

2. ボトルネック特定
   - Embedding > LLM: Embeddingモデルの問題
   - LLM > Embedding: GPU利用検討

3. リソース確認
   ```bash
   docker stats
   ```

### ディスク容量不足

**症状**: "No space left on device"

**対処**:
1. Docker不要イメージ削除
   ```bash
   docker system prune -a
   ```

2. ログファイル削除
   ```bash
   docker compose logs --tail=0
   truncate -s 0 $(docker inspect --format='{{.LogPath}}' broadlistening-llm)
   ```

## ベンチマーク実行

実際の環境でパフォーマンスを測定：

```bash
# 簡易テスト（5件、約1分）
python scripts/benchmark.py --quick

# 標準テスト（10件、約2-5分）
python scripts/benchmark.py

# フルテスト（50件、約10-30分）
python scripts/benchmark.py --full
```

結果例：
```
=== ベンチマーク結果サマリー ===

  1件あたりの処理時間: 4.5秒

  推定処理時間:
    100件:  7.5分
    500件:  37.5分
    1000件: 1.2時間
    5000件: 6.2時間

  ⚠ ボトルネック: LLM処理
    → GPU環境で大幅に改善できます
```
