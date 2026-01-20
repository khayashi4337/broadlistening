#!/usr/bin/env python3
"""
Embedding生成スクリプト

Issueのテキストからbge-m3を使ってベクトル表現を生成します。
n8nワークフローまたはバッチ処理から呼び出されます。
"""

import sys
import json
import requests
from typing import List, Dict, Optional
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """bge-m3を使ったEmbedding生成クラス"""

    def __init__(self, api_url: str = "http://embedding:80"):
        """
        初期化

        Args:
            api_url: Embedding APIのURL（デフォルト: Docker内部URL）
        """
        self.api_url = api_url
        self.embed_endpoint = f"{api_url}/embed"

    def generate(self, text: str, timeout: int = 30) -> Optional[List[float]]:
        """
        テキストからEmbeddingを生成

        Args:
            text: 入力テキスト
            timeout: タイムアウト秒数

        Returns:
            ベクトル（1024次元のfloatリスト）
            失敗時はNone
        """
        if not text or not text.strip():
            logger.warning("空のテキストが入力されました")
            return None

        try:
            # bge-m3のAPI仕様に従ったリクエスト
            payload = {"inputs": text.strip()}

            logger.info(f"Embedding生成開始: テキスト長={len(text)}文字")

            response = requests.post(
                self.embed_endpoint,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()

            # レスポンス形式: [[0.123, 0.456, ...]] (2次元配列)
            result = response.json()

            if isinstance(result, list) and len(result) > 0:
                embedding = result[0]  # 最初の要素を取得
                logger.info(f"Embedding生成成功: 次元数={len(embedding)}")
                return embedding
            else:
                logger.error(f"予期しないレスポンス形式: {result}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"タイムアウト: {timeout}秒以内に応答がありませんでした")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API呼び出しエラー: {e}")
            return None
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"レスポンス解析エラー: {e}")
            return None

    def generate_batch(self, texts: List[str], timeout: int = 60) -> List[Optional[List[float]]]:
        """
        複数テキストからEmbeddingを一括生成

        Args:
            texts: テキストのリスト
            timeout: タイムアウト秒数

        Returns:
            ベクトルのリスト（失敗した要素はNone）
        """
        embeddings = []

        for i, text in enumerate(texts, 1):
            logger.info(f"バッチ処理 {i}/{len(texts)}")
            embedding = self.generate(text, timeout)
            embeddings.append(embedding)

        return embeddings

    def health_check(self) -> bool:
        """
        Embedding APIの稼働確認

        Returns:
            正常ならTrue
        """
        try:
            # 簡単なテストテキスト
            test_embedding = self.generate("テスト", timeout=10)
            return test_embedding is not None
        except Exception as e:
            logger.error(f"ヘルスチェック失敗: {e}")
            return False


def create_issue_text(issue_data: Dict) -> str:
    """
    IssueデータからEmbedding用テキストを生成

    Args:
        issue_data: ForgejoのWebhookペイロード

    Returns:
        結合されたテキスト
    """
    # タイトルと本文を結合
    title = issue_data.get("title", "")
    body = issue_data.get("body", "")

    # タイトルは重要なので2回含める（重み付け）
    combined_text = f"{title}\n{title}\n{body}"

    return combined_text.strip()


def main():
    """CLIエントリーポイント"""

    # 使用例の表示
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  1. 標準入力からJSON受け取り:")
        print("     echo '{\"title\": \"タイトル\", \"body\": \"本文\"}' | python generate_embedding.py")
        print()
        print("  2. テキスト直接指定:")
        print("     python generate_embedding.py \"テキスト\"")
        print()
        print("  3. ヘルスチェック:")
        print("     python generate_embedding.py --health")
        sys.exit(1)

    # Embedding生成器の初期化
    generator = EmbeddingGenerator()

    # ヘルスチェックモード
    if sys.argv[1] == "--health":
        if generator.health_check():
            print("OK: Embedding APIは正常に動作しています")
            sys.exit(0)
        else:
            print("ERROR: Embedding APIに接続できません")
            sys.exit(1)

    # テキスト直接指定モード
    if sys.argv[1] != "-":
        text = sys.argv[1]
    else:
        # 標準入力からJSON読み込み
        try:
            input_data = json.load(sys.stdin)
            if isinstance(input_data, dict):
                # Issueオブジェクトの場合
                text = create_issue_text(input_data)
            else:
                text = str(input_data)
        except json.JSONDecodeError:
            # プレーンテキストとして扱う
            text = sys.stdin.read()

    # Embedding生成
    embedding = generator.generate(text)

    if embedding is None:
        logger.error("Embedding生成に失敗しました")
        sys.exit(1)

    # JSON形式で出力（n8nで受け取りやすい形式）
    output = {
        "embedding": embedding,
        "dimension": len(embedding),
        "text_length": len(text)
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
