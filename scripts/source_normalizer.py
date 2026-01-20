#!/usr/bin/env python3
"""
ソース統合・正規化モジュール

複数のソース（Forgejo, Slack, Webフォーム, CSV）からの意見データを
統一フォーマットに正規化し、出典管理を行います。

依存関係:
    - requests: HTTP API通信

使用方法:
    python source_normalizer.py [--update-metadata]

    --update-metadata: Qdrantのメタデータを更新
"""

import sys
import json
import os
import logging
import re
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import requests

# ロギング設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
FORGEJO_URL = os.getenv("FORGEJO_URL", "http://forgejo:3000")
FORGEJO_TOKEN = os.getenv("FORGEJO_TOKEN", "")
FORGEJO_OWNER = os.getenv("FORGEJO_OWNER", "broadlistening")
FORGEJO_REPO = os.getenv("FORGEJO_REPO", "opinions")
FORGEJO_API_TIMEOUT = int(os.getenv("FORGEJO_API_TIMEOUT", "30"))

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "broadlistening_issues")
QDRANT_API_TIMEOUT = int(os.getenv("QDRANT_API_TIMEOUT", "30"))

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "web" / "data"

# ソースタイプの定義
SOURCE_TYPES = {
    "forgejo": {
        "label": "Forgejo Issue",
        "icon": "🔧",
        "color": "#4ecca3"
    },
    "slack": {
        "label": "Slack",
        "icon": "💬",
        "color": "#4A154B"
    },
    "web_form": {
        "label": "Webフォーム",
        "icon": "📝",
        "color": "#3498db"
    },
    "csv_import": {
        "label": "CSVインポート",
        "icon": "📊",
        "color": "#f39c12"
    },
    "api": {
        "label": "API",
        "icon": "🔌",
        "color": "#9b59b6"
    },
    "unknown": {
        "label": "不明",
        "icon": "❓",
        "color": "#888888"
    }
}


def get_forgejo_headers() -> Dict[str, str]:
    """Forgejo API用ヘッダーを生成"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if FORGEJO_TOKEN:
        headers["Authorization"] = f"token {FORGEJO_TOKEN}"
    return headers


def detect_source_from_body(body: str) -> Dict:
    """
    Issue本文からソース情報を検出

    Args:
        body: Issue本文

    Returns:
        ソース情報
    """
    source = {
        "type": "forgejo",
        "detected_from": "default"
    }

    # 投稿元パターンの検出
    patterns = [
        (r'\*\*投稿元:\*\*\s*(Slack)', "slack"),
        (r'\*\*投稿元:\*\*\s*(Webフォーム)', "web_form"),
        (r'\*\*投稿元:\*\*\s*(CSVインポート)', "csv_import"),
        (r'\*\*Source:\*\*\s*Slack', "slack"),
        (r'\[slack\]', "slack"),
        (r'\[web-form\]', "web_form"),
        (r'\[csv-import\]', "csv_import"),
    ]

    for pattern, source_type in patterns:
        if re.search(pattern, body, re.IGNORECASE):
            source["type"] = source_type
            source["detected_from"] = "body_pattern"
            break

    # 追加メタデータの抽出
    nickname_match = re.search(r'\*\*投稿者:\*\*\s*(.+?)(?:\n|$)', body)
    if nickname_match:
        source["nickname"] = nickname_match.group(1).strip()

    channel_match = re.search(r'\*\*Channel:\*\*\s*(.+?)(?:\n|$)', body)
    if channel_match:
        source["channel_id"] = channel_match.group(1).strip()

    category_match = re.search(r'\*\*カテゴリ:\*\*\s*(.+?)(?:\n|$)', body)
    if category_match:
        source["category"] = category_match.group(1).strip()

    return source


def detect_source_from_labels(labels: List[str]) -> Optional[str]:
    """
    ラベルからソースタイプを検出

    Args:
        labels: ラベルリスト

    Returns:
        ソースタイプ（検出できない場合はNone）
    """
    label_mapping = {
        "slack": "slack",
        "web-form": "web_form",
        "csv-import": "csv_import",
        "api": "api"
    }

    for label in labels:
        label_lower = label.lower()
        if label_lower in label_mapping:
            return label_mapping[label_lower]

    return None


def normalize_source(issue: Dict) -> Dict:
    """
    Issue情報からソースを正規化

    Args:
        issue: Forgejoのissueデータ

    Returns:
        正規化されたソース情報
    """
    body = issue.get("body", "")
    labels = [label.get("name", "") for label in issue.get("labels", [])]

    # ラベルからソースを検出
    source_type = detect_source_from_labels(labels)

    # 本文からソース情報を検出
    source_info = detect_source_from_body(body)

    # ラベルが優先
    if source_type:
        source_info["type"] = source_type
        source_info["detected_from"] = "label"

    # ソースタイプの詳細情報を追加
    type_info = SOURCE_TYPES.get(source_info["type"], SOURCE_TYPES["unknown"])
    source_info["label"] = type_info["label"]
    source_info["icon"] = type_info["icon"]
    source_info["color"] = type_info["color"]

    # Issue基本情報を追加
    source_info["issue_id"] = issue.get("id")
    source_info["issue_number"] = issue.get("number")
    source_info["created_at"] = issue.get("created_at")

    return source_info


def fetch_all_issues() -> List[Dict]:
    """
    Forgejoから全Issueを取得

    Returns:
        Issueリスト
    """
    issues = []
    page = 1
    per_page = 50

    while True:
        url = f"{FORGEJO_URL}/api/v1/repos/{FORGEJO_OWNER}/{FORGEJO_REPO}/issues"
        params = {
            "state": "all",
            "page": page,
            "limit": per_page
        }

        try:
            response = requests.get(
                url,
                headers=get_forgejo_headers(),
                params=params,
                timeout=FORGEJO_API_TIMEOUT
            )
            response.raise_for_status()

            page_issues = response.json()
            if not page_issues:
                break

            issues.extend(page_issues)
            logger.debug(f"ページ{page}: {len(page_issues)}件取得")

            if len(page_issues) < per_page:
                break

            page += 1

        except requests.exceptions.RequestException as e:
            logger.error(f"Forgejo API エラー: {e}")
            break

    logger.info(f"Forgejoから{len(issues)}件のIssueを取得")
    return issues


def update_qdrant_source(issue_id: int, source_info: Dict) -> bool:
    """
    Qdrantのメタデータにソース情報を追加

    Args:
        issue_id: IssueのID
        source_info: ソース情報

    Returns:
        成功したらTrue
    """
    base_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    update_url = f"{base_url}/collections/{QDRANT_COLLECTION}/points/payload"

    try:
        payload = {
            "points": [issue_id],
            "payload": {
                "source": source_info
            }
        }

        response = requests.post(update_url, json=payload, timeout=QDRANT_API_TIMEOUT)
        response.raise_for_status()

        return response.json().get("status") == "ok"

    except requests.exceptions.RequestException as e:
        logger.error(f"Qdrant更新エラー (Issue #{issue_id}): {e}")
        return False


def generate_source_statistics(normalized_issues: List[Dict]) -> Dict:
    """
    ソース統計を生成

    Args:
        normalized_issues: 正規化されたIssueリスト

    Returns:
        統計データ
    """
    stats = {
        "total": len(normalized_issues),
        "by_source": {},
        "by_date": {}
    }

    for issue in normalized_issues:
        source_type = issue.get("source", {}).get("type", "unknown")

        # ソース別カウント
        if source_type not in stats["by_source"]:
            type_info = SOURCE_TYPES.get(source_type, SOURCE_TYPES["unknown"])
            stats["by_source"][source_type] = {
                "count": 0,
                "label": type_info["label"],
                "icon": type_info["icon"],
                "color": type_info["color"]
            }
        stats["by_source"][source_type]["count"] += 1

        # 日付別カウント
        created_at = issue.get("source", {}).get("created_at", "")
        if created_at:
            date_key = created_at[:10]  # YYYY-MM-DD
            stats["by_date"][date_key] = stats["by_date"].get(date_key, 0) + 1

    return stats


def save_normalized_data(
    normalized_issues: List[Dict],
    statistics: Dict,
    output_path: Optional[Path] = None
) -> bool:
    """
    正規化されたデータを保存

    Args:
        normalized_issues: 正規化されたIssueリスト
        statistics: 統計データ
        output_path: 出力パス

    Returns:
        成功したらTrue
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "sources.json"

    result = {
        "updated_at": datetime.now().isoformat(),
        "statistics": statistics,
        "source_types": SOURCE_TYPES,
        "issues": normalized_issues
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"正規化データを保存: {output_path}")
        return True

    except Exception as e:
        logger.error(f"ファイル保存エラー: {e}")
        return False


def main():
    """メインエントリーポイント"""
    update_qdrant = "--update-metadata" in sys.argv

    # 1. Forgejoから全Issue取得
    logger.info("Step 1: Forgejoから全Issue取得中...")
    issues = fetch_all_issues()

    if not issues:
        logger.warning("Issueが見つかりません")
        print(json.dumps({
            "status": "ok",
            "message": "Issueが見つかりませんでした",
            "total": 0
        }, ensure_ascii=False, indent=2))
        return

    # 2. ソース情報を正規化
    logger.info("Step 2: ソース情報を正規化中...")
    normalized_issues = []

    for issue in issues:
        source_info = normalize_source(issue)

        normalized_issue = {
            "id": issue.get("id"),
            "number": issue.get("number"),
            "title": issue.get("title"),
            "source": source_info
        }
        normalized_issues.append(normalized_issue)

        # Qdrant更新（オプション）
        if update_qdrant and issue.get("id"):
            update_qdrant_source(issue["id"], source_info)

    # 3. 統計を生成
    logger.info("Step 3: 統計を生成中...")
    statistics = generate_source_statistics(normalized_issues)

    # 4. 結果を保存
    logger.info("Step 4: 結果を保存中...")
    save_normalized_data(normalized_issues, statistics)

    # 結果出力
    print(json.dumps({
        "status": "ok",
        "total_issues": len(normalized_issues),
        "statistics": statistics
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
