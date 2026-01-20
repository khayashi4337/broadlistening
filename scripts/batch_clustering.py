#!/usr/bin/env python3
"""
バッチクラスタリングスクリプト

Qdrantから全ベクトルを取得し、K-meansでクラスタリングを行い、
クラスタラベルと代表意見を生成します。

依存関係:
    - numpy: 数値計算
    - scikit-learn: K-means
    - requests: HTTP API通信

使用方法:
    python batch_clustering.py [num_clusters]

    num_clusters: クラスタ数（省略時は自動決定）
"""

import sys
import json
import os
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import requests

# 数値計算ライブラリ（pip install numpy scikit-learn）
try:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
except ImportError:
    print("必要なライブラリをインストールしてください:")
    print("  pip install numpy scikit-learn")
    sys.exit(1)

# ロギング設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "broadlistening_issues")
QDRANT_API_TIMEOUT = int(os.getenv("QDRANT_API_TIMEOUT", "30"))
LLM_API_URL = os.getenv("LLM_API_URL", "http://llm:8080")
LLM_API_TIMEOUT = int(os.getenv("LLM_API_TIMEOUT", "60"))

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "web" / "data"

# クラスタリング設定
MIN_CLUSTERS = 2
MAX_CLUSTERS = 20
MIN_POINTS_FOR_CLUSTERING = 5


def get_all_points_from_qdrant() -> List[Dict]:
    """
    Qdrantから全ポイントを取得

    Returns:
        ポイントリスト [{"issue_id": int, "embedding": list, "metadata": dict}, ...]
    """
    base_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    scroll_url = f"{base_url}/collections/{QDRANT_COLLECTION}/points/scroll"

    try:
        payload = {
            "limit": 10000,
            "with_payload": True,
            "with_vector": True
        }

        response = requests.post(scroll_url, json=payload, timeout=QDRANT_API_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        points = result.get("result", {}).get("points", [])

        all_points = []
        for point in points:
            all_points.append({
                "issue_id": point["id"],
                "embedding": point["vector"],
                "metadata": point["payload"]
            })

        logger.info(f"Qdrantから{len(all_points)}件のポイントを取得")
        return all_points

    except requests.exceptions.RequestException as e:
        logger.error(f"Qdrant接続エラー: {e}")
        return []


def determine_optimal_clusters(embeddings: np.ndarray, max_k: int = MAX_CLUSTERS) -> int:
    """
    シルエットスコアを使用して最適なクラスタ数を決定

    Args:
        embeddings: ベクトル行列
        max_k: 最大クラスタ数

    Returns:
        最適なクラスタ数
    """
    n_samples = len(embeddings)

    # サンプル数が少ない場合
    if n_samples < MIN_POINTS_FOR_CLUSTERING:
        logger.warning(f"サンプル数が少なすぎます: {n_samples}")
        return min(n_samples, MIN_CLUSTERS)

    # 最大クラスタ数を調整
    max_k = min(max_k, n_samples - 1)
    if max_k < MIN_CLUSTERS:
        return MIN_CLUSTERS

    best_k = MIN_CLUSTERS
    best_score = -1

    for k in range(MIN_CLUSTERS, max_k + 1):
        try:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            # 各クラスタに少なくとも1つのサンプルがあるか確認
            if len(set(labels)) < k:
                continue

            score = silhouette_score(embeddings, labels)

            if score > best_score:
                best_score = score
                best_k = k

        except Exception as e:
            logger.debug(f"k={k}でエラー: {e}")
            continue

    logger.info(f"最適クラスタ数: {best_k} (シルエットスコア: {best_score:.3f})")
    return best_k


def perform_clustering(embeddings: np.ndarray, num_clusters: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    K-meansクラスタリングを実行

    Args:
        embeddings: ベクトル行列
        num_clusters: クラスタ数

    Returns:
        (クラスタラベル, クラスタ中心)
    """
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    centers = kmeans.cluster_centers_

    logger.info(f"クラスタリング完了: {num_clusters}クラスタ")
    return labels, centers


def find_representative_issues(
    points: List[Dict],
    labels: np.ndarray,
    centers: np.ndarray,
    top_k: int = 3
) -> Dict[int, List[Dict]]:
    """
    各クラスタの代表意見を選択（中心に最も近い意見）

    Args:
        points: 全ポイントリスト
        labels: クラスタラベル
        centers: クラスタ中心
        top_k: 各クラスタから選択する代表意見数

    Returns:
        {cluster_id: [代表意見リスト]}
    """
    representatives = {}
    embeddings = np.array([p["embedding"] for p in points])

    for cluster_id in range(len(centers)):
        # このクラスタに属するポイントのインデックス
        cluster_indices = np.where(labels == cluster_id)[0]

        if len(cluster_indices) == 0:
            representatives[cluster_id] = []
            continue

        # クラスタ中心との距離を計算
        cluster_embeddings = embeddings[cluster_indices]
        center = centers[cluster_id]

        # コサイン類似度（正規化されていればドット積）
        distances = np.linalg.norm(cluster_embeddings - center, axis=1)

        # 距離が近い順にソート
        sorted_indices = np.argsort(distances)

        # top_k件を代表として選択
        top_indices = sorted_indices[:top_k]

        representatives[cluster_id] = []
        for idx in top_indices:
            point_idx = cluster_indices[idx]
            point = points[point_idx]
            representatives[cluster_id].append({
                "issue_id": point["issue_id"],
                "title": point["metadata"].get("title", ""),
                "body": point["metadata"].get("body", "")[:200],
                "distance": float(distances[idx]),
                "url": point["metadata"].get("url", "")
            })

    return representatives


def generate_cluster_label(titles: List[str]) -> str:
    """
    LLMを使用してクラスタラベルを生成

    Args:
        titles: クラスタ内の意見タイトルリスト

    Returns:
        クラスタラベル
    """
    if not titles:
        return "その他"

    # プロンプトテンプレート読み込み
    prompt_path = PROJECT_DIR / "prompts" / "summarize_cluster.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.warning(f"プロンプトファイルが見つかりません: {prompt_path}")
        prompt_template = "以下の意見群のラベルを生成: {issue_titles}\nラベル:"

    # タイトルリストを整形（最大10件）
    titles_text = "\n".join([f"- {title}" for title in titles[:10]])
    prompt = prompt_template.format(issue_titles=titles_text)

    try:
        response = requests.post(
            f"{LLM_API_URL}/summarize",
            json={"text": prompt, "max_length": 20},
            timeout=LLM_API_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        label = result.get("summary", "その他").strip()

        # ラベル正規化
        label = label.replace("ラベル:", "").strip()
        label = label.replace("「", "").replace("」", "")

        if len(label) > 15:
            label = label[:15]

        return label if label else "その他"

    except Exception as e:
        logger.error(f"ラベル生成エラー: {e}")
        # フォールバック: 最頻出単語を使用
        return "クラスタ"


def update_qdrant_cluster_info(issue_id: int, cluster_id: int, cluster_label: str) -> bool:
    """
    Qdrantのメタデータにクラスタ情報を追加

    Args:
        issue_id: IssueのID
        cluster_id: クラスタID
        cluster_label: クラスタラベル

    Returns:
        成功したらTrue
    """
    base_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    update_url = f"{base_url}/collections/{QDRANT_COLLECTION}/points/payload"

    try:
        payload = {
            "points": [issue_id],
            "payload": {
                "cluster_id": cluster_id,
                "cluster_label": cluster_label
            }
        }

        response = requests.post(update_url, json=payload, timeout=10)
        response.raise_for_status()

        return response.json().get("status") == "ok"

    except Exception as e:
        logger.error(f"Qdrant更新エラー (Issue #{issue_id}): {e}")
        return False


def generate_cluster_summary(
    points: List[Dict],
    labels: np.ndarray,
    cluster_labels: Dict[int, str],
    representatives: Dict[int, List[Dict]]
) -> Dict:
    """
    クラスタ要約データを生成

    Args:
        points: 全ポイントリスト
        labels: クラスタラベル配列
        cluster_labels: {cluster_id: label_name}
        representatives: {cluster_id: [代表意見リスト]}

    Returns:
        要約データ
    """
    clusters = []

    for cluster_id, label in cluster_labels.items():
        cluster_indices = np.where(labels == cluster_id)[0]
        cluster_points = [points[i] for i in cluster_indices]

        # クラスタ統計
        cluster_info = {
            "id": cluster_id,
            "label": label,
            "count": len(cluster_points),
            "representatives": representatives.get(cluster_id, []),
            "issues": []
        }

        # 各意見の情報
        for point in cluster_points:
            cluster_info["issues"].append({
                "issue_id": point["issue_id"],
                "title": point["metadata"].get("title", ""),
                "opinion_type": point["metadata"].get("opinion_type", "その他"),
                "themes": point["metadata"].get("themes", []),
                "url": point["metadata"].get("url", "")
            })

        clusters.append(cluster_info)

    # クラスタをサイズ順にソート
    clusters.sort(key=lambda x: x["count"], reverse=True)

    return {
        "total_issues": len(points),
        "num_clusters": len(cluster_labels),
        "clusters": clusters
    }


def save_cluster_results(summary: Dict, output_path: Optional[Path] = None) -> bool:
    """
    クラスタリング結果をJSONファイルに保存

    Args:
        summary: 要約データ
        output_path: 出力パス（省略時はweb/data/clusters.json）

    Returns:
        成功したらTrue
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "clusters.json"

    try:
        # 出力ディレクトリ作成
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"クラスタリング結果を保存: {output_path}")
        return True

    except Exception as e:
        logger.error(f"ファイル保存エラー: {e}")
        return False


def main():
    """
    メインエントリーポイント

    使用方法:
        python batch_clustering.py [num_clusters]

        num_clusters: クラスタ数（省略時は自動決定）
    """
    # コマンドライン引数
    num_clusters = None
    if len(sys.argv) > 1:
        try:
            num_clusters = int(sys.argv[1])
            if num_clusters < MIN_CLUSTERS:
                logger.warning(f"クラスタ数は{MIN_CLUSTERS}以上にしてください")
                num_clusters = MIN_CLUSTERS
        except ValueError:
            logger.error("クラスタ数は整数で指定してください")
            sys.exit(1)

    # 1. Qdrantから全ポイント取得
    logger.info("Step 1: Qdrantからデータ取得中...")
    points = get_all_points_from_qdrant()

    if len(points) < MIN_POINTS_FOR_CLUSTERING:
        logger.error(f"データが少なすぎます: {len(points)}件（最低{MIN_POINTS_FOR_CLUSTERING}件必要）")
        # 空の結果を保存
        empty_summary = {
            "total_issues": len(points),
            "num_clusters": 0,
            "clusters": [],
            "message": "データが少なすぎるためクラスタリングをスキップしました"
        }
        save_cluster_results(empty_summary)
        print(json.dumps(empty_summary, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 2. ベクトル行列に変換
    embeddings = np.array([p["embedding"] for p in points])
    logger.info(f"ベクトル行列: {embeddings.shape}")

    # 3. 最適クラスタ数を決定
    if num_clusters is None:
        logger.info("Step 2: 最適クラスタ数を決定中...")
        num_clusters = determine_optimal_clusters(embeddings)

    # 4. K-meansクラスタリング
    logger.info(f"Step 3: K-meansクラスタリング実行中 (k={num_clusters})...")
    labels, centers = perform_clustering(embeddings, num_clusters)

    # 5. 代表意見を選択
    logger.info("Step 4: 代表意見を選択中...")
    representatives = find_representative_issues(points, labels, centers)

    # 6. クラスタラベルを生成
    logger.info("Step 5: クラスタラベルを生成中...")
    cluster_labels = {}
    for cluster_id in range(num_clusters):
        cluster_indices = np.where(labels == cluster_id)[0]
        titles = [points[i]["metadata"].get("title", "") for i in cluster_indices]

        label = generate_cluster_label(titles)
        cluster_labels[cluster_id] = label
        logger.info(f"  クラスタ {cluster_id}: {label} ({len(cluster_indices)}件)")

    # 7. Qdrantのメタデータを更新
    logger.info("Step 6: Qdrantメタデータを更新中...")
    update_count = 0
    for i, point in enumerate(points):
        cluster_id = int(labels[i])
        cluster_label = cluster_labels[cluster_id]
        if update_qdrant_cluster_info(point["issue_id"], cluster_id, cluster_label):
            update_count += 1
    logger.info(f"  {update_count}/{len(points)}件を更新")

    # 8. 要約データを生成・保存
    logger.info("Step 7: 要約データを生成中...")
    summary = generate_cluster_summary(points, labels, cluster_labels, representatives)
    save_cluster_results(summary)

    # 結果出力
    print(json.dumps({
        "status": "ok",
        "total_issues": len(points),
        "num_clusters": num_clusters,
        "clusters": [
            {"id": c["id"], "label": c["label"], "count": c["count"]}
            for c in summary["clusters"]
        ]
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
