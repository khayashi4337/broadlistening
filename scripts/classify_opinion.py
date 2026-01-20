#!/usr/bin/env python3
"""
意見分類スクリプト

LLM APIを使用して意見を「問題提起」「提案」「質問」に分類し、
Qdrantのメタデータを更新します。

依存関係:
    - requests: HTTP API通信
    - qdrant_manager: Qdrant操作
"""

import sys
import json
import os
import requests
import logging
from typing import Dict, Optional
from pathlib import Path

# ロギング設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
LLM_API_URL = os.getenv("LLM_API_URL", "http://llm:8080")
DEFAULT_TIMEOUT = int(os.getenv("LLM_API_TIMEOUT", "60"))
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# プロンプトテンプレート読み込み
SCRIPT_DIR = Path(__file__).parent.parent
PROMPT_PATH = SCRIPT_DIR / "prompts" / "classify_opinion.txt"

try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        CLASSIFY_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    logger.warning(f"プロンプトファイルが見つかりません: {PROMPT_PATH}")
    # フォールバックプロンプト
    CLASSIFY_PROMPT_TEMPLATE = """以下のテキストを次のカテゴリのいずれかに分類してください: 問題提起, 提案, 質問

テキスト: {text}

分類結果:"""


def load_prompt_template(template_name: str) -> str:
    """
    プロンプトテンプレートを読み込む

    Args:
        template_name: テンプレートファイル名（拡張子なし）

    Returns:
        プロンプトテンプレート文字列
    """
    template_path = SCRIPT_DIR / "prompts" / f"{template_name}.txt"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"プロンプトテンプレートが見つかりません: {template_path}")
        raise


def classify_text(text: str, categories: Optional[list] = None) -> Dict:
    """
    LLM APIを使用してテキストを分類

    Args:
        text: 分類対象のテキスト
        categories: カテゴリリスト（省略時はデフォルト）

    Returns:
        分類結果のdict {"classification": "問題提起", "confidence": 0.95}
    """
    if not text or not text.strip():
        logger.error("テキストが空です")
        return {"classification": "その他", "confidence": 0.0}

    # 入力サイズチェック（4000文字制限）
    max_length = int(os.getenv("MAX_INPUT_LENGTH", "4000"))
    if len(text) > max_length:
        logger.warning(f"テキストが長すぎます（{len(text)}文字）。切り詰めます。")
        text = text[:max_length]

    # プロンプト生成
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(text=text)

    try:
        # LLM API呼び出し
        response = requests.post(
            f"{LLM_API_URL}/classify",
            json={"text": text, "categories": categories},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        classification = result.get("classification", "").strip()

        # カテゴリ正規化
        classification = normalize_category(classification)

        logger.info(f"分類成功: {classification}")
        return {
            "classification": classification,
            "confidence": 0.8  # LFM2.5は信頼度を返さないため固定値
        }

    except requests.exceptions.Timeout:
        logger.error("LLM API タイムアウト")
        return {"classification": "その他", "confidence": 0.0}
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM API エラー: {e}")
        return {"classification": "その他", "confidence": 0.0}
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        return {"classification": "その他", "confidence": 0.0}


def normalize_category(category: str) -> str:
    """
    カテゴリ名を正規化

    Args:
        category: LLMが返したカテゴリ名

    Returns:
        正規化されたカテゴリ名
    """
    category = category.strip()

    # マッピング辞書
    mapping = {
        "問題提起": ["問題", "課題", "不満", "困っている"],
        "提案": ["提案", "改善", "アイデア", "導入"],
        "質問": ["質問", "教えて", "知りたい", "わからない"],
        "その他": ["その他", "不明", "分類不能"]
    }

    # 完全一致チェック
    for standard, aliases in mapping.items():
        if category in aliases or category == standard:
            return standard

    # 部分一致チェック
    for standard, aliases in mapping.items():
        for alias in aliases:
            if alias in category:
                return standard

    # どれにも該当しない場合
    return "その他"


def update_qdrant_metadata(issue_id: int, opinion_type: str) -> bool:
    """
    Qdrantのメタデータに分類結果を追加

    Args:
        issue_id: IssueのID
        opinion_type: 分類結果（問題提起/提案/質問）

    Returns:
        成功したらTrue
    """
    try:
        # Qdrant APIでポイント更新
        base_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
        collection_name = os.getenv("QDRANT_COLLECTION", "broadlistening_issues")

        update_url = f"{base_url}/collections/{collection_name}/points/payload"

        payload = {
            "points": [issue_id],
            "payload": {
                "opinion_type": opinion_type
            }
        }

        response = requests.post(update_url, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        if result.get("status") == "ok":
            logger.info(f"Qdrant更新成功: Issue #{issue_id} → {opinion_type}")
            return True
        else:
            logger.error(f"Qdrant更新失敗: {result}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Qdrant更新エラー: {e}")
        return False


def main():
    """
    CLIエントリーポイント

    使用方法:
        1. 標準入力から分類:
           echo '{"text": "消費税が高すぎる"}' | python classify_opinion.py

        2. Issue全体を分類してQdrant更新:
           echo '{"issue_id": 1, "text": "給食費を無償化してほしい"}' | python classify_opinion.py --update
    """
    if len(sys.argv) < 1:
        print("使用方法:")
        print("  echo '{\"text\": \"...\"}' | python classify_opinion.py")
        print("  echo '{\"issue_id\": 1, \"text\": \"...\"}' | python classify_opinion.py --update")
        sys.exit(1)

    update_mode = "--update" in sys.argv

    try:
        input_data = json.load(sys.stdin)
        text = input_data.get("text", "")
        issue_id = input_data.get("issue_id")

        if not text:
            logger.error("テキストが空です")
            print(json.dumps({"error": "text is required"}))
            sys.exit(1)

        # 分類実行
        result = classify_text(text)
        classification = result["classification"]

        # Qdrant更新（オプション）
        if update_mode and issue_id:
            update_success = update_qdrant_metadata(issue_id, classification)
            result["qdrant_updated"] = update_success

        # 結果出力
        output = {
            "issue_id": issue_id,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "opinion_type": classification,
            "confidence": result["confidence"]
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析エラー: {e}")
        print(json.dumps({"error": "Invalid JSON input"}))
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
