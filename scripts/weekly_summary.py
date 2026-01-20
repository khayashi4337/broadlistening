#!/usr/bin/env python3
"""
週次サマリー・レポート生成スクリプト

週次サマリー、テーマ別レポート、アクションアイテム抽出、
前週比較を行い、レポートを生成します。

依存関係:
    - requests: HTTP API通信

使用方法:
    python weekly_summary.py [--weeks N]

    --weeks N: 過去N週間のレポートを生成（デフォルト: 1）
"""

import sys
import json
import os
import logging
import re
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime, timedelta
import requests

# ロギング設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
LLM_API_URL = os.getenv("LLM_API_URL", "http://llm:8080")
LLM_API_TIMEOUT = int(os.getenv("LLM_API_TIMEOUT", "120"))

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "web" / "data"
PROMPTS_DIR = PROJECT_DIR / "prompts"


def load_prompt(prompt_name: str) -> str:
    """
    プロンプトファイルを読み込む

    Args:
        prompt_name: プロンプト名（拡張子なし）

    Returns:
        プロンプト文字列
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"プロンプトファイルが見つかりません: {prompt_path}")
        return ""


def load_issues_data() -> Dict:
    """
    issues.jsonを読み込む

    Returns:
        Issueデータ
    """
    issues_path = DATA_DIR / "issues.json"
    try:
        with open(issues_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("issues.jsonが見つかりません")
        return {"clusters": [], "issues": []}
    except json.JSONDecodeError as e:
        logger.error(f"issues.jsonのパースエラー: {e}")
        return {"clusters": [], "issues": []}


def load_clusters_data() -> Dict:
    """
    clusters.jsonを読み込む

    Returns:
        クラスタデータ
    """
    clusters_path = DATA_DIR / "clusters.json"
    try:
        with open(clusters_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("clusters.jsonが見つかりません")
        return {"clusters": [], "total_issues": 0}
    except json.JSONDecodeError as e:
        logger.error(f"clusters.jsonのパースエラー: {e}")
        return {"clusters": [], "total_issues": 0}


def load_previous_report() -> Optional[Dict]:
    """
    前回のレポートを読み込む

    Returns:
        前回のレポートデータ（存在しない場合はNone）
    """
    reports_path = DATA_DIR / "reports.json"
    try:
        with open(reports_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("reports") and len(data["reports"]) > 0:
                return data["reports"][0]
            return None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def filter_issues_by_date(issues: List[Dict], start_date: datetime, end_date: datetime) -> List[Dict]:
    """
    日付範囲でIssueをフィルタリング

    Args:
        issues: 全Issueリスト
        start_date: 開始日
        end_date: 終了日

    Returns:
        フィルタリングされたIssueリスト
    """
    filtered = []
    for issue in issues:
        created_at = issue.get("created_at") or issue.get("metadata", {}).get("created_at")
        if not created_at:
            continue
        try:
            # タイムゾーン情報を除去して比較（ローカル時間として扱う）
            date_str = created_at.replace("Z", "+00:00")
            issue_date = datetime.fromisoformat(date_str)
            # タイムゾーン情報を除去してnaive datetimeに変換
            issue_date = issue_date.replace(tzinfo=None)
            if start_date <= issue_date <= end_date:
                filtered.append(issue)
        except (ValueError, TypeError):
            continue
    return filtered


def call_llm(prompt: str) -> Optional[str]:
    """
    LLM APIを呼び出す

    Args:
        prompt: プロンプト

    Returns:
        LLMの応答（エラー時はNone）
    """
    try:
        payload = {
            "prompt": prompt,
            "max_tokens": 2000,
            "temperature": 0.3,
            "stop": ["```"]
        }

        response = requests.post(
            f"{LLM_API_URL}/completion",
            json=payload,
            timeout=LLM_API_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()
        return result.get("content", "")

    except requests.exceptions.RequestException as e:
        logger.error(f"LLM API エラー: {e}")
        return None


def parse_json_response(response: Optional[str]) -> Optional[Dict]:
    """
    LLMの応答からJSONをパース

    Args:
        response: LLMの応答

    Returns:
        パースされたJSON（エラー時はNone）
    """
    if not response:
        return None

    # JSON部分を抽出
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        return None

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.error("JSONパースエラー")
        return None


def generate_weekly_summary(issues: List[Dict]) -> Dict:
    """
    週次サマリーを生成

    Args:
        issues: 今週のIssueリスト

    Returns:
        週次サマリー
    """
    if not issues:
        return {
            "summary": "今週の意見はありませんでした。",
            "key_topics": [],
            "sentiment": "neutral",
            "notable_trends": "データがありません。"
        }

    # Issueをテキストに変換
    issues_text = "\n".join([
        f"- {issue.get('title', '無題')}: {issue.get('body', '')[:200]}"
        for issue in issues[:50]  # 最大50件
    ])

    prompt_template = load_prompt("weekly_summary")
    if not prompt_template:
        return {
            "summary": "プロンプトの読み込みに失敗しました。",
            "key_topics": [],
            "sentiment": "neutral",
            "notable_trends": ""
        }

    prompt = prompt_template.replace("{issues}", issues_text)
    response = call_llm(prompt)
    result = parse_json_response(response)

    if result:
        return result

    # フォールバック: 基本的な統計ベースのサマリー
    return {
        "summary": f"今週は{len(issues)}件の意見が寄せられました。",
        "key_topics": list(set(
            theme for issue in issues[:10]
            for theme in issue.get("themes", [])[:2]
        ))[:5],
        "sentiment": "neutral",
        "notable_trends": "LLM分析が利用できないため、詳細な傾向分析は省略されています。"
    }


def extract_action_items(issues: List[Dict]) -> List[Dict]:
    """
    アクションアイテムを抽出

    Args:
        issues: Issueリスト

    Returns:
        アクションアイテムリスト
    """
    if not issues:
        return []

    # 問題提起と提案を優先的に抽出
    priority_issues = [
        issue for issue in issues
        if issue.get("opinion_type") in ["問題提起", "提案"]
    ]

    if not priority_issues:
        priority_issues = issues[:20]

    issues_text = "\n".join([
        f"[ID:{issue.get('id', 'N/A')}] {issue.get('title', '無題')}: {issue.get('body', '')[:150]}"
        for issue in priority_issues[:30]
    ])

    prompt_template = load_prompt("extract_actions")
    if not prompt_template:
        return []

    prompt = prompt_template.replace("{issues}", issues_text)
    response = call_llm(prompt)
    result = parse_json_response(response)

    if result and "action_items" in result:
        return result["action_items"]

    # フォールバック: 問題提起からアクションアイテムを自動生成
    action_items = []
    for issue in priority_issues[:5]:
        if issue.get("opinion_type") == "問題提起":
            action_items.append({
                "title": f"対応検討: {issue.get('title', '無題')[:30]}",
                "description": issue.get("body", "")[:100],
                "priority": "medium",
                "source_issues": [issue.get("id")]
            })
    return action_items


def generate_theme_report(theme: str, issues: List[Dict]) -> Dict:
    """
    テーマ別レポートを生成

    Args:
        theme: テーマ名
        issues: テーマに関連するIssueリスト

    Returns:
        テーマ別レポート
    """
    if not issues:
        return {
            "theme": theme,
            "analysis": "このテーマに関する意見がありません。",
            "key_concerns": [],
            "proposals": [],
            "stakeholders": [],
            "recommendation": ""
        }

    issues_text = "\n".join([
        f"- {issue.get('title', '無題')}: {issue.get('body', '')[:150]}"
        for issue in issues[:20]
    ])

    prompt_template = load_prompt("theme_report")
    if not prompt_template:
        return {
            "theme": theme,
            "analysis": "プロンプトの読み込みに失敗しました。",
            "key_concerns": [],
            "proposals": [],
            "stakeholders": [],
            "recommendation": ""
        }

    prompt = prompt_template.replace("{theme}", theme).replace("{issues}", issues_text)
    response = call_llm(prompt)
    result = parse_json_response(response)

    if result:
        return result

    # フォールバック
    return {
        "theme": theme,
        "analysis": f"{theme}に関して{len(issues)}件の意見が寄せられています。",
        "key_concerns": [],
        "proposals": [],
        "stakeholders": [],
        "recommendation": "詳細な分析にはLLMが必要です。"
    }


def calculate_changes(current: Dict, previous: Optional[Dict]) -> Dict:
    """
    前週との変化を計算

    Args:
        current: 今週のデータ
        previous: 前週のデータ

    Returns:
        変化の情報
    """
    if not previous:
        return {
            "issue_count_change": 0,
            "new_topics": current.get("key_topics", []),
            "resolved_topics": [],
            "sentiment_change": "N/A",
            "trend_description": "前週のデータがないため比較できません。"
        }

    current_count = current.get("issue_count", 0)
    previous_count = previous.get("issue_count", 0)
    count_change = current_count - previous_count

    current_topics = set(current.get("key_topics", []))
    previous_topics = set(previous.get("key_topics", []))
    new_topics = list(current_topics - previous_topics)
    resolved_topics = list(previous_topics - current_topics)

    current_sentiment = current.get("sentiment", "neutral")
    previous_sentiment = previous.get("sentiment", "neutral")

    sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
    sentiment_change = sentiment_map.get(current_sentiment, 0) - sentiment_map.get(previous_sentiment, 0)

    if sentiment_change > 0:
        sentiment_desc = "改善"
    elif sentiment_change < 0:
        sentiment_desc = "悪化"
    else:
        sentiment_desc = "変化なし"

    # 変化の説明を生成
    descriptions = []
    if count_change > 0:
        descriptions.append(f"意見数が{count_change}件増加")
    elif count_change < 0:
        descriptions.append(f"意見数が{abs(count_change)}件減少")

    if new_topics:
        descriptions.append(f"新しいトピック: {', '.join(new_topics[:3])}")
    if resolved_topics:
        descriptions.append(f"収束したトピック: {', '.join(resolved_topics[:3])}")

    return {
        "issue_count_change": count_change,
        "new_topics": new_topics,
        "resolved_topics": resolved_topics,
        "sentiment_change": sentiment_desc,
        "trend_description": "。".join(descriptions) if descriptions else "大きな変化はありません。"
    }


def generate_report(weeks_back: int = 0) -> Dict:
    """
    週次レポートを生成

    Args:
        weeks_back: 何週間前のレポートか（0=今週）

    Returns:
        レポートデータ
    """
    # 日付範囲を計算
    today = datetime.now()
    # 週の開始（月曜日）を基準に
    week_start = today - timedelta(days=today.weekday() + (weeks_back * 7))
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    logger.info(f"レポート期間: {week_start.date()} - {week_end.date()}")

    # データ読み込み
    issues_data = load_issues_data()
    clusters_data = load_clusters_data()
    previous_report = load_previous_report() if weeks_back == 0 else None

    # 週間のIssueをフィルタリング
    all_issues = issues_data.get("issues", [])
    week_issues = filter_issues_by_date(all_issues, week_start, week_end)

    logger.info(f"今週のIssue数: {len(week_issues)}")

    # 週次サマリー生成
    summary = generate_weekly_summary(week_issues)
    summary["issue_count"] = len(week_issues)

    # アクションアイテム抽出
    action_items = extract_action_items(week_issues)

    # テーマ別レポート生成（クラスタごと）
    theme_reports = []
    for cluster in clusters_data.get("clusters", [])[:5]:  # 上位5クラスタ
        cluster_issues = [
            issue for issue in week_issues
            if any(theme in issue.get("themes", []) for theme in [cluster.get("label", "")])
        ]
        if cluster_issues:
            report = generate_theme_report(cluster.get("label", ""), cluster_issues)
            report["issue_count"] = len(cluster_issues)
            theme_reports.append(report)

    # 変化の計算
    changes = calculate_changes(summary, previous_report)

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "action_items": action_items,
        "theme_reports": theme_reports,
        "changes": changes,
        "statistics": {
            "total_issues": len(week_issues),
            "by_type": {
                "問題提起": len([i for i in week_issues if i.get("opinion_type") == "問題提起"]),
                "提案": len([i for i in week_issues if i.get("opinion_type") == "提案"]),
                "質問": len([i for i in week_issues if i.get("opinion_type") == "質問"]),
                "その他": len([i for i in week_issues if i.get("opinion_type") not in ["問題提起", "提案", "質問"]])
            },
            "clusters_count": len(clusters_data.get("clusters", []))
        }
    }


def save_report(report: Dict, output_path: Optional[Path] = None) -> bool:
    """
    レポートをJSONファイルに保存

    Args:
        report: レポートデータ
        output_path: 出力パス

    Returns:
        成功したらTrue
    """
    if output_path is None:
        output_path = DATA_DIR / "reports.json"

    try:
        # 既存のレポートを読み込み
        existing_reports = []
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_reports = data.get("reports", [])

        # 同じ週のレポートがあれば更新、なければ追加
        week_start = report["week_start"]
        updated = False
        for i, existing in enumerate(existing_reports):
            if existing.get("week_start") == week_start:
                existing_reports[i] = report
                updated = True
                break

        if not updated:
            existing_reports.insert(0, report)

        # 最新10週分のみ保持
        existing_reports = existing_reports[:10]

        # 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "reports": existing_reports
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"レポートを保存: {output_path}")
        return True

    except Exception as e:
        logger.error(f"レポート保存エラー: {e}")
        return False


def main():
    """
    メインエントリーポイント
    """
    # 引数解析
    weeks = 1
    for i, arg in enumerate(sys.argv):
        if arg == "--weeks" and i + 1 < len(sys.argv):
            try:
                weeks = int(sys.argv[i + 1])
            except ValueError:
                pass

    logger.info(f"過去{weeks}週間のレポートを生成します")

    all_reports = []
    for week_back in range(weeks):
        logger.info(f"Week -{week_back} のレポートを生成中...")
        report = generate_report(week_back)
        save_report(report)
        all_reports.append(report)

    # 結果出力
    print(json.dumps({
        "status": "ok",
        "reports_generated": len(all_reports),
        "latest_summary": all_reports[0]["summary"] if all_reports else {}
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
