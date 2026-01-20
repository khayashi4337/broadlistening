#!/usr/bin/env python3
"""
Embedding生成スクリプト

Issueのテキストからbge-m3を使ってベクトル表現を生成します。
n8nワークフローまたはバッチ処理から呼び出されます。

依存関係:
    - requests: HTTP API通信
"""

import sys
import json
import os
import time
import requests
from typing import List, Dict, Optional, Union
import logging

# 定数定義（環境変数でオーバーライド可能）
DEFAULT_EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "http://embedding:80")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("EMBEDDING_TIMEOUT", "30"))
BATCH_TIMEOUT_SECONDS = int(os.getenv("EMBEDDING_BATCH_TIMEOUT", "60"))
HEALTH_CHECK_TIMEOUT_SECONDS = int(os.getenv("EMBEDDING_HEALTH_TIMEOUT", "10"))
EMBEDDING_DIMENSION = 1024
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "10000"))  # 最大テキスト長（セキュリティ）
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "3"))  # リトライ回数
RETRY_BACKOFF_SECONDS = int(os.getenv("RETRY_BACKOFF_SECONDS", "2"))  # リトライ待機時間

# ロギング設定（環境変数でレベル制御可能）
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    bge-m3を使ったEmbedding生成クラス

    環境変数:
        EMBEDDING_API_URL: Embedding APIのURL（デフォルト: http://embedding:80）
        EMBEDDING_TIMEOUT: タイムアウト秒数（デフォルト: 30）
        EMBEDDING_BATCH_TIMEOUT: バッチ処理タイムアウト（デフォルト: 60）
        MAX_TEXT_LENGTH: 最大テキスト長（デフォルト: 10000）
        MAX_RETRY_COUNT: 最大リトライ回数（デフォルト: 3）
        RETRY_BACKOFF_SECONDS: リトライ待機時間（デフォルト: 2）
        LOG_LEVEL: ログレベル（DEBUG/INFO/WARNING/ERROR）
    """

    def __init__(self, api_url: str = DEFAULT_EMBEDDING_API_URL):
        """
        初期化

        Args:
            api_url: Embedding APIのURL（環境変数EMBEDDING_API_URLでオーバーライド可能）
        """
        self.api_url = api_url
        self.embed_endpoint = f"{api_url}/embed"
        logger.debug(f"EmbeddingGenerator初期化: api_url={api_url}")

    def generate(self, text: str, timeout: int = DEFAULT_TIMEOUT_SECONDS, retry: int = MAX_RETRY_COUNT) -> Optional[List[float]]:
        """
        テキストからEmbeddingを生成（リトライ機能付き）

        Args:
            text: 入力テキスト
            timeout: タイムアウト秒数
            retry: リトライ回数

        Returns:
            ベクトル（1024次元のfloatリスト）
            失敗時はNone
        """
        # 入力バリデーション
        if not text or not text.strip():
            logger.warning("空のテキストが入力されました")
            return None

        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(f"テキストが長すぎます（{len(text)}文字 > {MAX_TEXT_LENGTH}文字）。切り詰めます。")
            text = text[:MAX_TEXT_LENGTH]

        # リトライロジック
        for attempt in range(retry):
            try:
                # bge-m3のAPI仕様に従ったリクエスト
                payload = {"inputs": text.strip()}

                logger.info(f"Embedding生成開始: テキスト長={len(text)}文字 (試行 {attempt + 1}/{retry})")

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

                    # 次元数検証
                    if len(embedding) != EMBEDDING_DIMENSION:
                        logger.error(f"不正な次元数: {len(embedding)} != {EMBEDDING_DIMENSION}")
                        return None

                    logger.info(f"Embedding生成成功: 次元数={len(embedding)}")
                    return embedding
                else:
                    logger.error(f"予期しないレスポンス形式: {result}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"タイムアウト (試行 {attempt + 1}/{retry}): {timeout}秒")
                if attempt < retry - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                else:
                    logger.error("最大リトライ回数に到達しました")
                    return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"API呼び出しエラー (試行 {attempt + 1}/{retry}): {e}")
                if attempt < retry - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                else:
                    logger.error("最大リトライ回数に到達しました")
                    return None
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"レスポンス解析エラー: {e}")
                return None

        return None

    def generate_batch(self, texts: List[str], timeout: int = BATCH_TIMEOUT_SECONDS) -> List[Optional[List[float]]]:
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
            test_embedding = self.generate("テスト", timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            return test_embedding is not None
        except requests.exceptions.RequestException as e:
            logger.error(f"ヘルスチェック失敗（API通信エラー）: {e}")
            return False
        except Exception as e:
            logger.error(f"ヘルスチェック失敗（予期しないエラー）: {e}")
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


def _parse_input() -> str:
    """
    標準入力またはコマンドライン引数からテキストを取得

    Returns:
        パースされたテキスト
    """
    if sys.argv[1] != "-":
        return sys.argv[1]

    # 標準入力からJSON読み込み
    try:
        input_data = json.load(sys.stdin)
        if isinstance(input_data, dict):
            # Issueオブジェクトの場合
            return create_issue_text(input_data)
        else:
            return str(input_data)
    except json.JSONDecodeError:
        # プレーンテキストとして扱う
        return sys.stdin.read()


def main():
    """
    CLIエントリーポイント

    環境変数:
        EMBEDDING_API_URL: Embedding APIのURL
        EMBEDDING_TIMEOUT: タイムアウト秒数
        MAX_TEXT_LENGTH: 最大テキスト長
        MAX_RETRY_COUNT: リトライ回数
        LOG_LEVEL: ログレベル（DEBUG/INFO/WARNING/ERROR）
    """

    # 使用例の表示
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  1. 標準入力からJSON受け取り:")
        print("     echo '{\"title\": \"タイトル\", \"body\": \"本文\"}' | python generate_embedding.py -")
        print()
        print("  2. テキスト直接指定:")
        print("     python generate_embedding.py \"テキスト\"")
        print()
        print("  3. ヘルスチェック:")
        print("     python generate_embedding.py --health")
        print()
        print("環境変数:")
        print(f"  EMBEDDING_API_URL: {DEFAULT_EMBEDDING_API_URL}")
        print(f"  EMBEDDING_TIMEOUT: {DEFAULT_TIMEOUT_SECONDS}秒")
        print(f"  MAX_TEXT_LENGTH: {MAX_TEXT_LENGTH}文字")
        print(f"  MAX_RETRY_COUNT: {MAX_RETRY_COUNT}回")
        print(f"  LOG_LEVEL: {log_level}")
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

    # テキスト取得
    text = _parse_input()

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
