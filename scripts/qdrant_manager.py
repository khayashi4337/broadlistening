#!/usr/bin/env python3
"""
Qdrant管理スクリプト

ベクトルの保存、類似検索、コレクション管理を行います。

依存関係:
    - requests: HTTP API通信
"""

import sys
import json
import requests
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime

# 定数定義
DEFAULT_COLLECTION_NAME = "broadlistening_issues"
DEFAULT_VECTOR_SIZE = 1024
DEFAULT_DISTANCE_METRIC = "Cosine"
DEFAULT_HEALTH_TIMEOUT = 5

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QdrantManager:
    """Qdrant操作クラス"""

    def __init__(self, host: str = "qdrant", port: int = 6333, collection_name: str = DEFAULT_COLLECTION_NAME):
        """
        初期化

        Args:
            host: Qdrantホスト名
            port: Qdrantポート番号
            collection_name: コレクション名
        """
        self.base_url = f"http://{host}:{port}"
        self.collection_name = collection_name

    def create_collection(self, vector_size: int = DEFAULT_VECTOR_SIZE, force: bool = False) -> bool:
        """
        コレクション作成（既存の場合はスキップ）

        Args:
            vector_size: ベクトルの次元数（bge-m3は1024次元）
            force: 既存コレクションを削除して再作成

        Returns:
            成功したらTrue
        """
        try:
            # 既存チェック
            collections_url = f"{self.base_url}/collections"
            response = requests.get(collections_url)
            response.raise_for_status()

            collections = response.json().get("result", {}).get("collections", [])
            collection_names = [c["name"] for c in collections]

            if self.collection_name in collection_names:
                if force:
                    logger.info(f"既存コレクション削除: {self.collection_name}")
                    self.delete_collection()
                else:
                    logger.info(f"コレクションは既に存在します: {self.collection_name}")
                    return True

            # コレクション作成
            create_url = f"{self.base_url}/collections/{self.collection_name}"
            payload = {
                "vectors": {
                    "size": vector_size,
                    "distance": DEFAULT_DISTANCE_METRIC  # コサイン類似度
                }
            }

            response = requests.put(create_url, json=payload)
            response.raise_for_status()

            logger.info(f"コレクション作成成功: {self.collection_name} (次元={vector_size})")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"コレクション作成エラー: {e}")
            return False

    def delete_collection(self) -> bool:
        """コレクション削除"""
        try:
            delete_url = f"{self.base_url}/collections/{self.collection_name}"
            response = requests.delete(delete_url)
            response.raise_for_status()
            logger.info(f"コレクション削除成功: {self.collection_name}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"コレクション削除エラー: {e}")
            return False

    def upsert_point(
        self,
        issue_id: int,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        ポイント（ベクトル）を保存

        Args:
            issue_id: IssueのID（Qdrantのpoint_idとして使用）
            embedding: ベクトル（1024次元）
            metadata: メタデータ（title, body, created_at等）

        Returns:
            成功したらTrue
        """
        try:
            upsert_url = f"{self.base_url}/collections/{self.collection_name}/points"

            # ペイロード構築
            payload = {
                "points": [
                    {
                        "id": issue_id,
                        "vector": embedding,
                        "payload": metadata
                    }
                ]
            }

            response = requests.put(upsert_url, json=payload)
            response.raise_for_status()

            result = response.json()

            if result.get("status") == "ok":
                logger.info(f"ポイント保存成功: Issue #{issue_id}")
                return True
            else:
                logger.error(f"ポイント保存失敗: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"ポイント保存エラー: {e}")
            return False

    def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 5,
        score_threshold: float = 0.5
    ) -> List[Dict]:
        """
        類似ベクトル検索

        Args:
            query_embedding: クエリベクトル
            limit: 取得件数
            score_threshold: 類似度の閾値（0.0-1.0）

        Returns:
            類似Issue一覧（降順）
        """
        try:
            search_url = f"{self.base_url}/collections/{self.collection_name}/points/search"

            payload = {
                "vector": query_embedding,
                "limit": limit,
                "score_threshold": score_threshold,
                "with_payload": True,  # メタデータも取得
                "with_vector": False   # ベクトルは不要
            }

            response = requests.post(search_url, json=payload)
            response.raise_for_status()

            result = response.json()
            results = result.get("result", [])

            # 整形
            similar_issues = []
            for item in results:
                similar_issues.append({
                    "issue_id": item["id"],
                    "score": item["score"],
                    "title": item["payload"].get("title", ""),
                    "body": item["payload"].get("body", ""),
                    "created_at": item["payload"].get("created_at", ""),
                    "url": item["payload"].get("url", "")
                })

            logger.info(f"類似検索完了: {len(similar_issues)}件ヒット")
            return similar_issues

        except requests.exceptions.RequestException as e:
            logger.error(f"類似検索エラー: {e}")
            return []

    def get_all_points(self, limit: int = 1000) -> List[Dict]:
        """
        全ポイント取得（JSON出力用）

        Args:
            limit: 最大取得件数

        Returns:
            全Issueデータ
        """
        try:
            scroll_url = f"{self.base_url}/collections/{self.collection_name}/points/scroll"

            payload = {
                "limit": limit,
                "with_payload": True,
                "with_vector": True  # 可視化のためベクトルも取得
            }

            response = requests.post(scroll_url, json=payload)
            response.raise_for_status()

            result = response.json()
            points = result.get("result", {}).get("points", [])

            all_issues = []
            for point in points:
                all_issues.append({
                    "issue_id": point["id"],
                    "embedding": point["vector"],
                    "metadata": point["payload"]
                })

            logger.info(f"全ポイント取得完了: {len(all_issues)}件")
            return all_issues

        except requests.exceptions.RequestException as e:
            logger.error(f"全ポイント取得エラー: {e}")
            return []

    def health_check(self) -> bool:
        """Qdrantの稼働確認"""
        try:
            health_url = f"{self.base_url}/healthz"
            response = requests.get(health_url, timeout=DEFAULT_HEALTH_TIMEOUT)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"ヘルスチェック失敗（API通信エラー）: {e}")
            return False
        except Exception as e:
            logger.error(f"ヘルスチェック失敗（予期しないエラー）: {e}")
            return False


def create_metadata(issue_data: Dict) -> Dict[str, Any]:
    """
    IssueデータからQdrant用メタデータを生成

    Args:
        issue_data: ForgejoのWebhookペイロード（issue部分）

    Returns:
        Qdrantに保存するメタデータ
    """
    return {
        "title": issue_data.get("title", ""),
        "body": issue_data.get("body", ""),
        "created_at": issue_data.get("created_at", datetime.now().isoformat()),
        "updated_at": issue_data.get("updated_at", datetime.now().isoformat()),
        "url": issue_data.get("html_url", ""),
        "user": issue_data.get("user", {}).get("login", "anonymous"),
        "labels": [label["name"] for label in issue_data.get("labels", [])]
    }


def main():
    """CLIエントリーポイント"""

    if len(sys.argv) < 2:
        print("使用方法:")
        print("  1. コレクション作成:")
        print("     python qdrant_manager.py init")
        print()
        print("  2. ポイント保存:")
        print("     echo '{\"issue_id\": 1, \"embedding\": [...], \"metadata\": {...}}' | python qdrant_manager.py upsert")
        print()
        print("  3. 類似検索:")
        print("     echo '{\"embedding\": [...], \"limit\": 5}' | python qdrant_manager.py search")
        print()
        print("  4. 全ポイント取得:")
        print("     python qdrant_manager.py get-all")
        print()
        print("  5. ヘルスチェック:")
        print("     python qdrant_manager.py health")
        sys.exit(1)

    command = sys.argv[1]
    manager = QdrantManager()

    # ヘルスチェック
    if command == "health":
        if manager.health_check():
            print("OK: Qdrantは正常に動作しています")
            sys.exit(0)
        else:
            print("ERROR: Qdrantに接続できません")
            sys.exit(1)

    # コレクション初期化
    elif command == "init":
        force = "--force" in sys.argv
        if manager.create_collection(force=force):
            print(f"コレクション作成成功: {manager.collection_name}")
            sys.exit(0)
        else:
            print("コレクション作成失敗")
            sys.exit(1)

    # ポイント保存
    elif command == "upsert":
        try:
            input_data = json.load(sys.stdin)
            issue_id = input_data["issue_id"]
            embedding = input_data["embedding"]
            metadata = input_data["metadata"]

            if manager.upsert_point(issue_id, embedding, metadata):
                print(json.dumps({"status": "ok", "issue_id": issue_id}))
                sys.exit(0)
            else:
                print(json.dumps({"status": "error"}))
                sys.exit(1)
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"入力エラー: {e}")
            sys.exit(1)

    # 類似検索
    elif command == "search":
        try:
            input_data = json.load(sys.stdin)
            embedding = input_data["embedding"]
            limit = input_data.get("limit", 5)
            score_threshold = input_data.get("score_threshold", 0.5)

            results = manager.search_similar(embedding, limit, score_threshold)
            print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
            sys.exit(0)
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"入力エラー: {e}")
            sys.exit(1)

    # 全ポイント取得
    elif command == "get-all":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        all_points = manager.get_all_points(limit)
        print(json.dumps({"points": all_points}, ensure_ascii=False, indent=2))
        sys.exit(0)

    else:
        print(f"不明なコマンド: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
