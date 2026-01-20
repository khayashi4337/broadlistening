#!/usr/bin/env python3
"""
テーマ抽出スクリプト

LLM APIを使用して意見から主要テーマを抽出し、
Qdrantのメタデータに保存します。

依存関係:
    - requests: HTTP API通信
    - qdrant_manager: Qdrant操作
"""

import sys
import json
import os
import requests
import logging
from typing import List, Dict, Optional
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
PROMPT_PATH = SCRIPT_DIR / "prompts" / "extract_themes.txt"

try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        EXTRACT_THEMES_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    logger.warning(f"プロンプトファイルが見つかりません: {PROMPT_PATH}")
    # フォールバックプロンプト
    EXTRACT_THEMES_PROMPT_TEMPLATE = """以下のテキストから主要なテーマを{num_themes}個抽出してください。

テキスト: {text}

テーマ:"""


def extract_themes(text: str, num_themes: int = 3) -> List[str]:
    """
    LLM APIを使用してテキストからテーマを抽出

    Args:
        text: テーマ抽出対象のテキスト
        num_themes: 抽出するテーマの数

    Returns:
        テーマのリスト ["教育", "税制", "福祉"]
    """
    if not text or not text.strip():
        logger.error("テキストが空です")
        return []

    # 入力サイズチェック
    max_length = int(os.getenv("MAX_INPUT_LENGTH", "4000"))
    if len(text) > max_length:
        logger.warning(f"テキストが長すぎます（{len(text)}文字）。切り詰めます。")
        text = text[:max_length]

    # プロンプト生成
    prompt = EXTRACT_THEMES_PROMPT_TEMPLATE.format(
        text=text,
        num_themes=num_themes
    )

    try:
        # LLM API呼び出し
        response = requests.post(
            f"{LLM_API_URL}/extract_themes",
            json={"text": text, "num_themes": num_themes},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        themes_str = result.get("themes", "").strip()

        # テーマ解析
        themes = parse_themes(themes_str, num_themes)

        logger.info(f"テーマ抽出成功: {themes}")
        return themes

    except requests.exceptions.Timeout:
        logger.error("LLM API タイムアウト")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM API エラー: {e}")
        return []
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        return []


def parse_themes(themes_str: str, expected_count: int) -> List[str]:
    """
    LLMが返したテーマ文字列をパースしてリスト化

    Args:
        themes_str: LLMの出力文字列（例: "教育, 税制, 福祉"）
        expected_count: 期待するテーマ数

    Returns:
        正規化されたテーマリスト
    """
    if not themes_str:
        return []

    # カンマ区切りで分割
    themes = []
    for theme in themes_str.split(","):
        theme = theme.strip()

        # 余計な文字を除去
        theme = theme.replace("「", "").replace("」", "")
        theme = theme.replace("・", "")
        theme = theme.replace("1.", "").replace("2.", "").replace("3.", "")

        # 数字のみの場合はスキップ
        if theme.isdigit():
            continue

        # 空文字列や記号のみの場合はスキップ
        if not theme or len(theme) < 2:
            continue

        themes.append(theme)

    # 最大数に制限
    themes = themes[:expected_count]

    return themes


def update_qdrant_metadata(issue_id: int, themes: List[str]) -> bool:
    """
    Qdrantのメタデータにテーマを追加

    Args:
        issue_id: IssueのID
        themes: テーマリスト

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
                "themes": themes
            }
        }

        response = requests.post(update_url, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        if result.get("status") == "ok":
            logger.info(f"Qdrant更新成功: Issue #{issue_id} → {themes}")
            return True
        else:
            logger.error(f"Qdrant更新失敗: {result}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Qdrant更新エラー: {e}")
        return False


def summarize_cluster(issue_titles: List[str]) -> str:
    """
    複数の意見タイトルからクラスタラベルを生成

    Args:
        issue_titles: Issueタイトルのリスト

    Returns:
        クラスタラベル（例: "教育政策"）
    """
    if not issue_titles:
        return "その他"

    # プロンプトテンプレート読み込み
    prompt_path = SCRIPT_DIR / "prompts" / "summarize_cluster.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"プロンプトファイルが見つかりません: {prompt_path}")
        return "その他"

    # タイトルリストを整形
    titles_text = "\n".join([f"- {title}" for title in issue_titles])
    prompt = prompt_template.format(issue_titles=titles_text)

    try:
        # LLM API呼び出し（summarizeエンドポイント使用）
        response = requests.post(
            f"{LLM_API_URL}/summarize",
            json={"text": prompt, "max_length": 20},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        label = result.get("summary", "その他").strip()

        # ラベル正規化
        label = label.replace("ラベル:", "").strip()
        label = label.replace("「", "").replace("」", "")

        # 長すぎる場合は切り詰め
        if len(label) > 10:
            label = label[:10]

        logger.info(f"クラスタラベル生成成功: {label}")
        return label

    except Exception as e:
        logger.error(f"クラスタラベル生成エラー: {e}")
        return "その他"


def main():
    """
    CLIエントリーポイント

    使用方法:
        1. 標準入力からテーマ抽出:
           echo '{"text": "消費税が高すぎる"}' | python extract_themes.py

        2. Issue全体を処理してQdrant更新:
           echo '{"issue_id": 1, "text": "給食費を無償化してほしい", "num_themes": 3}' | python extract_themes.py --update

        3. クラスタラベル生成:
           echo '{"titles": ["消費税が高い", "税金の使い道が不明"]}' | python extract_themes.py --cluster
    """
    update_mode = "--update" in sys.argv
    cluster_mode = "--cluster" in sys.argv

    try:
        input_data = json.load(sys.stdin)

        # クラスタラベル生成モード
        if cluster_mode:
            titles = input_data.get("titles", [])
            label = summarize_cluster(titles)
            print(json.dumps({"cluster_label": label}, ensure_ascii=False))
            sys.exit(0)

        # テーマ抽出モード
        text = input_data.get("text", "")
        issue_id = input_data.get("issue_id")
        num_themes = input_data.get("num_themes", 3)

        if not text:
            logger.error("テキストが空です")
            print(json.dumps({"error": "text is required"}))
            sys.exit(1)

        # テーマ抽出実行
        themes = extract_themes(text, num_themes)

        # Qdrant更新（オプション）
        qdrant_updated = False
        if update_mode and issue_id:
            qdrant_updated = update_qdrant_metadata(issue_id, themes)

        # 結果出力
        output = {
            "issue_id": issue_id,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "themes": themes,
            "num_themes": len(themes)
        }

        if update_mode:
            output["qdrant_updated"] = qdrant_updated

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
