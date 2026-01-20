#!/usr/bin/env python3
"""
issues.jsonエクスポートスクリプト

Qdrantから全Issueデータを取得し、Web UI用のJSONファイルを生成します。
vis.jsで可視化するための2D座標（UMAP）も計算します。

依存関係:
    - numpy: 次元削減（PCA）
    - qdrant_manager: Qdrantデータ取得
"""

import sys
import json
import os
from typing import List, Dict, Any
from datetime import datetime
import logging
import numpy as np
from qdrant_manager import QdrantManager

# 定数定義
DEFAULT_OUTPUT_PATH = "/usr/share/nginx/html/data/issues.json"
FALLBACK_OUTPUT_PATH = "./web/data/issues.json"
VIS_JS_SCALE_FACTOR = 500
TOOLTIP_MAX_LENGTH = 200
MIN_ISSUES_FOR_PCA = 2  # PCAに必要な最小Issue数

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IssueJSONExporter:
    """Issue JSONエクスポートクラス"""

    def __init__(self, output_path: str = DEFAULT_OUTPUT_PATH):
        """
        初期化

        Args:
            output_path: 出力先ファイルパス（Docker内のnginx配置先）
        """
        self.output_path = output_path
        self.qdrant = QdrantManager()

    def reduce_dimensions(self, embeddings: np.ndarray) -> np.ndarray:
        """
        高次元ベクトルを2次元に削減（UMAP風の簡易版）

        本格的にはumap-learnを使うが、ここではPCAで代用

        Args:
            embeddings: N x 1024の行列

        Returns:
            N x 2の座標行列
        """
        # 入力バリデーション
        if embeddings.shape[0] < MIN_ISSUES_FOR_PCA:
            logger.warning(f"Issue数が少なすぎます（{embeddings.shape[0]}件 < {MIN_ISSUES_FOR_PCA}件）。ランダム配置します。")
            return np.random.randn(len(embeddings), 2)

        try:
            # NumPyで簡易PCA（共分散行列の固有値分解）
            embeddings_centered = embeddings - embeddings.mean(axis=0)
            cov_matrix = np.cov(embeddings_centered.T)
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

            # 固有値が大きい順に2つ選択
            idx = eigenvalues.argsort()[::-1][:2]
            top_eigenvectors = eigenvectors[:, idx]

            # 射影
            coords_2d = embeddings_centered @ top_eigenvectors

            # 正規化（-1.0 ~ 1.0の範囲に）
            coords_2d = coords_2d / (np.abs(coords_2d).max() + 1e-10)

            logger.info(f"次元削減完了: {embeddings.shape} → {coords_2d.shape}")
            return coords_2d

        except Exception as e:
            logger.error(f"次元削減エラー: {e}")
            # フォールバック: ランダム配置
            return np.random.randn(len(embeddings), 2)

    def export(self) -> bool:
        """
        Qdrantからデータ取得してJSONエクスポート

        Returns:
            成功したらTrue
        """
        try:
            # 全ポイント取得
            all_points = self.qdrant.get_all_points()

            if not all_points:
                logger.warning("Issueデータが0件です")
                # 空のJSONを出力
                self._write_json({"nodes": [], "edges": [], "count": 0})
                return True

            # Embedding行列化
            embeddings = np.array([point["embedding"] for point in all_points])

            # 2D座標計算
            coords_2d = self.reduce_dimensions(embeddings)

            # vis.js用のノードデータ生成
            nodes = []
            for i, point in enumerate(all_points):
                metadata = point["metadata"]
                nodes.append({
                    "id": point["issue_id"],
                    "label": metadata.get("title", f"Issue #{point['issue_id']}"),
                    "title": metadata.get("body", "")[:TOOLTIP_MAX_LENGTH],  # ツールチップ用（短縮）
                    "x": float(coords_2d[i, 0]) * VIS_JS_SCALE_FACTOR,  # vis.jsのスケールに合わせる
                    "y": float(coords_2d[i, 1]) * VIS_JS_SCALE_FACTOR,
                    "url": metadata.get("url", ""),
                    "created_at": metadata.get("created_at", ""),
                    "user": metadata.get("user", "anonymous"),
                    "labels": metadata.get("labels", [])
                })

            # エッジ（類似関係）は後でクラスタリング実装時に追加
            edges = []

            # JSON出力データ
            output_data = {
                "nodes": nodes,
                "edges": edges,
                "count": len(nodes),
                "generated_at": self._get_timestamp()
            }

            # ファイル書き込み
            self._write_json(output_data)

            logger.info(f"JSONエクスポート完了: {len(nodes)}件のIssue")
            return True

        except Exception as e:
            logger.error(f"エクスポートエラー: {e}")
            return False

    def _write_json(self, data: Dict[str, Any]) -> None:
        """
        JSONファイル書き込み

        Args:
            data: 出力データ
        """
        # ディレクトリ作成
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # JSON書き込み
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSONファイル出力: {self.output_path}")

    def _get_timestamp(self) -> str:
        """現在時刻のISO形式文字列を取得"""
        return datetime.now().isoformat()


def main():
    """CLIエントリーポイント"""

    # 引数で出力先を指定可能
    if len(sys.argv) > 1:
        output_path = sys.argv[1]
    else:
        # デフォルトはDocker内のnginxパス
        # ローカル実行時は相対パスに変更
        if os.path.exists("/usr/share/nginx/html"):
            output_path = DEFAULT_OUTPUT_PATH
        else:
            output_path = FALLBACK_OUTPUT_PATH

    logger.info(f"出力先: {output_path}")

    exporter = IssueJSONExporter(output_path)

    if exporter.export():
        print(f"成功: {output_path} を生成しました")
        sys.exit(0)
    else:
        print("エラー: JSONエクスポートに失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
