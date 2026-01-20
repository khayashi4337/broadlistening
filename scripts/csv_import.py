#!/usr/bin/env python3
"""
CSV一括インポートスクリプト

CSVファイルから意見データを一括でForgejo Issueとして登録します。

依存関係:
    - requests: HTTP API通信

使用方法:
    python csv_import.py <csv_file> [--dry-run] [--encoding ENCODING]

    csv_file: インポートするCSVファイルのパス
    --dry-run: 実際にはインポートせず、処理内容を表示
    --encoding: CSVファイルのエンコーディング（デフォルト: utf-8）

CSVフォーマット:
    必須列: title, body
    任意列: category, nickname, source, created_at
"""

import sys
import csv
import json
import os
import logging
import argparse
from typing import List, Dict, Optional
from pathlib import Path
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

# インポート設定
MAX_TITLE_LENGTH = 100
MAX_BODY_LENGTH = 65535
BATCH_SIZE = 10  # 一度に処理する件数
RATE_LIMIT_DELAY = 0.5  # API呼び出し間隔（秒）


def get_forgejo_headers() -> Dict[str, str]:
    """Forgejo API用ヘッダーを生成"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if FORGEJO_TOKEN:
        headers["Authorization"] = f"token {FORGEJO_TOKEN}"
    return headers


def sanitize_text(text: Optional[str], max_length: int) -> str:
    """
    テキストをサニタイズして長さを制限

    Args:
        text: 入力テキスト
        max_length: 最大文字数

    Returns:
        サニタイズされたテキスト
    """
    if not text:
        return ""
    # 前後の空白を除去し、長さを制限
    return str(text).strip()[:max_length]


def validate_row(row: Dict, row_num: int) -> Optional[str]:
    """
    CSV行のバリデーション

    Args:
        row: CSV行データ
        row_num: 行番号

    Returns:
        エラーメッセージ（問題なければNone）
    """
    if not row.get("title"):
        return f"行 {row_num}: titleが空です"
    if not row.get("body"):
        return f"行 {row_num}: bodyが空です"
    return None


def parse_csv(file_path: str, encoding: str = "utf-8") -> List[Dict]:
    """
    CSVファイルをパース

    Args:
        file_path: CSVファイルパス
        encoding: ファイルエンコーディング

    Returns:
        パースされた行のリスト
    """
    rows = []
    errors = []

    try:
        with open(file_path, "r", encoding=encoding, newline="") as f:
            # BOM付きUTF-8対応
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]

            reader = csv.DictReader(content.splitlines())

            # 必須列の確認
            fieldnames = reader.fieldnames or []
            if "title" not in fieldnames:
                raise ValueError("CSVに必須列 'title' がありません")
            if "body" not in fieldnames:
                raise ValueError("CSVに必須列 'body' がありません")

            for i, row in enumerate(reader, start=2):  # ヘッダー行を考慮
                error = validate_row(row, i)
                if error:
                    errors.append(error)
                    continue
                rows.append(row)

    except FileNotFoundError:
        raise ValueError(f"ファイルが見つかりません: {file_path}")
    except UnicodeDecodeError:
        raise ValueError(f"エンコーディングエラー。--encoding オプションで正しいエンコーディングを指定してください")

    if errors:
        logger.warning(f"バリデーションエラー: {len(errors)}件")
        for error in errors[:10]:  # 最初の10件のみ表示
            logger.warning(error)

    return rows


def create_issue(row: Dict, source_file: str) -> Optional[Dict]:
    """
    ForgejoにIssueを作成

    Args:
        row: CSV行データ
        source_file: ソースファイル名

    Returns:
        作成されたIssue（エラー時はNone）
    """
    title = sanitize_text(row.get("title"), MAX_TITLE_LENGTH)
    body = sanitize_text(row.get("body"), MAX_BODY_LENGTH)
    category = row.get("category", "その他")
    nickname = row.get("nickname", "匿名")
    original_source = row.get("source", "")
    created_at = row.get("created_at", "")

    # Issue本文の構築
    issue_body = f"""{body}

---
**投稿元:** CSVインポート
**元ファイル:** {source_file}
**投稿者:** {nickname}
**カテゴリ:** {category}"""

    if original_source:
        issue_body += f"\n**元ソース:** {original_source}"
    if created_at:
        issue_body += f"\n**元投稿日:** {created_at}"

    # ラベルの設定
    labels = ["csv-import", "auto-imported"]
    if category:
        # カテゴリをラベルに追加（小文字化）
        category_label = category.lower().replace(" ", "-")
        if category_label not in labels:
            labels.append(category_label)

    url = f"{FORGEJO_URL}/api/v1/repos/{FORGEJO_OWNER}/{FORGEJO_REPO}/issues"

    try:
        payload = {
            "title": title,
            "body": issue_body,
            "labels": labels
        }

        response = requests.post(
            url,
            headers=get_forgejo_headers(),
            json=payload,
            timeout=FORGEJO_API_TIMEOUT
        )
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Issue作成エラー: {e}")
        return None


def import_csv(
    file_path: str,
    encoding: str = "utf-8",
    dry_run: bool = False
) -> Dict:
    """
    CSVファイルをインポート

    Args:
        file_path: CSVファイルパス
        encoding: ファイルエンコーディング
        dry_run: ドライランモード

    Returns:
        インポート結果
    """
    import time

    logger.info(f"CSVファイルを読み込み中: {file_path}")
    rows = parse_csv(file_path, encoding)

    if not rows:
        return {
            "status": "error",
            "message": "インポート可能なデータがありません",
            "total": 0,
            "success": 0,
            "failed": 0
        }

    logger.info(f"インポート対象: {len(rows)}件")

    source_file = Path(file_path).name
    success_count = 0
    failed_count = 0
    created_issues = []

    for i, row in enumerate(rows):
        if dry_run:
            logger.info(f"[DRY-RUN] {i+1}/{len(rows)}: {row.get('title', '')[:50]}")
            success_count += 1
            continue

        logger.info(f"インポート中: {i+1}/{len(rows)}")

        result = create_issue(row, source_file)
        if result:
            success_count += 1
            created_issues.append({
                "id": result.get("id"),
                "number": result.get("number"),
                "title": result.get("title")
            })
        else:
            failed_count += 1

        # レート制限対策
        if i < len(rows) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    return {
        "status": "ok" if failed_count == 0 else "partial",
        "message": f"インポート完了: 成功 {success_count}件, 失敗 {failed_count}件",
        "total": len(rows),
        "success": success_count,
        "failed": failed_count,
        "dry_run": dry_run,
        "created_issues": created_issues[:10]  # 最初の10件のみ
    }


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="CSVファイルからForgejo Issueを一括作成"
    )
    parser.add_argument(
        "csv_file",
        help="インポートするCSVファイルのパス"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際にはインポートせず、処理内容を表示"
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="CSVファイルのエンコーディング（デフォルト: utf-8）"
    )

    args = parser.parse_args()

    try:
        result = import_csv(
            args.csv_file,
            encoding=args.encoding,
            dry_run=args.dry_run
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result["status"] == "error":
            sys.exit(1)

    except ValueError as e:
        logger.error(str(e))
        print(json.dumps({
            "status": "error",
            "message": str(e)
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
