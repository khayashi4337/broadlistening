#!/usr/bin/env python3
"""
Forgejoリアクション集計スクリプト

ForgejoのIssueリアクション（👍👎等）を取得・集計し、
投票傾向分析と合意度スコアを算出します。

依存関係:
    - requests: HTTP API通信

使用方法:
    python reaction_aggregator.py [--update-qdrant]

    --update-qdrant: Qdrantのメタデータも更新する
"""

import sys
import json
import os
import logging
import math
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

# リアクションマッピング（Forgejo/GitHubのリアクションタイプ）
POSITIVE_REACTIONS = ["+1", "thumbs_up", "heart", "hooray", "rocket"]
NEGATIVE_REACTIONS = ["-1", "thumbs_down", "confused"]
NEUTRAL_REACTIONS = ["laugh", "eyes"]


def get_forgejo_headers() -> Dict[str, str]:
    """Forgejo API用ヘッダーを生成"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if FORGEJO_TOKEN:
        headers["Authorization"] = f"token {FORGEJO_TOKEN}"
    return headers


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


def fetch_issue_reactions(issue_number: int) -> Dict[str, int]:
    """
    特定IssueのリアクションをForgejo APIから取得

    Args:
        issue_number: Issue番号

    Returns:
        リアクションカウント {"thumbs_up": 5, "thumbs_down": 2, ...}
    """
    url = f"{FORGEJO_URL}/api/v1/repos/{FORGEJO_OWNER}/{FORGEJO_REPO}/issues/{issue_number}/reactions"

    try:
        response = requests.get(
            url,
            headers=get_forgejo_headers(),
            timeout=FORGEJO_API_TIMEOUT
        )
        response.raise_for_status()

        reactions = response.json()

        # リアクションをカウント
        reaction_counts = {}
        for reaction in reactions:
            reaction_type = reaction.get("content", "")
            reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1

        return reaction_counts

    except requests.exceptions.RequestException as e:
        logger.error(f"リアクション取得エラー (Issue #{issue_number}): {e}")
        return {}


def aggregate_reactions(reaction_counts: Dict[str, int]) -> Dict[str, int]:
    """
    リアクションを肯定/否定/中立に分類して集計

    Args:
        reaction_counts: 生のリアクションカウント

    Returns:
        集計結果 {"positive": 10, "negative": 2, "neutral": 3, "total": 15}
    """
    # POSITIVE_REACTIONSには"+1"が含まれているので重複カウントしない
    positive = sum(reaction_counts.get(r, 0) for r in POSITIVE_REACTIONS)
    negative = sum(reaction_counts.get(r, 0) for r in NEGATIVE_REACTIONS)
    neutral = sum(reaction_counts.get(r, 0) for r in NEUTRAL_REACTIONS)

    total = positive + negative + neutral

    return {
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "total": total
    }


def calculate_approval_rate(aggregated: Dict[str, int]) -> float:
    """
    賛成率を計算

    Args:
        aggregated: 集計済みリアクション

    Returns:
        賛成率 (0.0 - 1.0)
    """
    total_votes = aggregated["positive"] + aggregated["negative"]
    if total_votes == 0:
        return 0.5  # 投票なしの場合は中立

    return aggregated["positive"] / total_votes


def calculate_consensus_score(approval_rate: float, total_votes: int) -> Dict[str, float]:
    """
    合意度スコアを計算

    合意度 = 1 - |approval_rate - 0.5| * 2
    - 1.0: 完全な合意（全員賛成 or 全員反対）
    - 0.0: 完全な分断（50:50）

    分断度 = 1 - 合意度

    信頼度 = 投票数に基づく重み付け

    Args:
        approval_rate: 賛成率
        total_votes: 総投票数

    Returns:
        {"consensus": float, "division": float, "confidence": float}
    """
    # 賛成率が50%からどれだけ離れているか
    deviation = abs(approval_rate - 0.5) * 2

    # 合意度（賛成率が極端なほど高い）
    consensus = deviation

    # 分断度（50:50に近いほど高い）
    division = 1 - deviation

    # 信頼度（投票数が多いほど高い、ログスケール）
    confidence = min(1.0, math.log10(total_votes + 1) / 2) if total_votes > 0 else 0.0

    return {
        "consensus": round(consensus, 3),
        "division": round(division, 3),
        "confidence": round(confidence, 3)
    }


def analyze_cluster_voting_trend(
    issues_with_reactions: List[Dict],
    clusters_data: Optional[Dict] = None
) -> Dict[int, Dict]:
    """
    クラスタ別の投票傾向を分析

    Args:
        issues_with_reactions: リアクション付きIssueリスト
        clusters_data: クラスタデータ（省略時はQdrantから取得）

    Returns:
        {cluster_id: {"label": str, "avg_approval": float, "consensus": float, ...}}
    """
    # クラスタ情報を取得
    if clusters_data is None:
        clusters_path = OUTPUT_DIR / "clusters.json"
        try:
            with open(clusters_path, "r", encoding="utf-8") as f:
                clusters_data = json.load(f)
        except FileNotFoundError:
            logger.warning("clusters.jsonが見つかりません")
            return {}

    # Issue IDとクラスタIDのマッピングを作成
    issue_to_cluster = {}
    cluster_labels = {}
    for cluster in clusters_data.get("clusters", []):
        cluster_id = cluster["id"]
        cluster_labels[cluster_id] = cluster["label"]
        for issue in cluster.get("issues", []):
            issue_to_cluster[issue["issue_id"]] = cluster_id

    # クラスタ別に集計
    cluster_stats = {}
    for issue in issues_with_reactions:
        issue_id = issue["issue_id"]
        cluster_id = issue_to_cluster.get(issue_id)

        if cluster_id is None:
            continue

        if cluster_id not in cluster_stats:
            cluster_stats[cluster_id] = {
                "label": cluster_labels.get(cluster_id, f"クラスタ{cluster_id}"),
                "issues": [],
                "total_positive": 0,
                "total_negative": 0,
                "total_votes": 0
            }

        stats = cluster_stats[cluster_id]
        stats["issues"].append(issue)
        stats["total_positive"] += issue["reactions"]["positive"]
        stats["total_negative"] += issue["reactions"]["negative"]
        stats["total_votes"] += issue["reactions"]["total"]

    # 各クラスタの統計を計算
    for cluster_id, stats in cluster_stats.items():
        total_votes = stats["total_positive"] + stats["total_negative"]

        if total_votes > 0:
            avg_approval = stats["total_positive"] / total_votes
        else:
            avg_approval = 0.5

        consensus = calculate_consensus_score(avg_approval, total_votes)

        stats["avg_approval_rate"] = round(avg_approval, 3)
        stats["consensus_score"] = consensus["consensus"]
        stats["division_score"] = consensus["division"]
        stats["confidence"] = consensus["confidence"]
        stats["issue_count"] = len(stats["issues"])

        # 詳細データは削除
        del stats["issues"]

    return cluster_stats


def update_qdrant_reactions(issue_id: int, reactions: Dict, approval_rate: float) -> bool:
    """
    Qdrantのメタデータにリアクション情報を追加

    Args:
        issue_id: IssueのID
        reactions: リアクション集計
        approval_rate: 賛成率

    Returns:
        成功したらTrue
    """
    base_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}"
    update_url = f"{base_url}/collections/{QDRANT_COLLECTION}/points/payload"

    try:
        payload = {
            "points": [issue_id],
            "payload": {
                "reactions": reactions,
                "approval_rate": round(approval_rate, 3)
            }
        }

        response = requests.post(update_url, json=payload, timeout=QDRANT_API_TIMEOUT)
        response.raise_for_status()

        return response.json().get("status") == "ok"

    except Exception as e:
        logger.error(f"Qdrant更新エラー (Issue #{issue_id}): {e}")
        return False


def save_voting_results(
    issues_with_reactions: List[Dict],
    cluster_trends: Dict[int, Dict],
    output_path: Optional[Path] = None
) -> bool:
    """
    投票結果をJSONファイルに保存

    Args:
        issues_with_reactions: リアクション付きIssueリスト
        cluster_trends: クラスタ別投票傾向
        output_path: 出力パス（省略時はweb/data/voting.json）

    Returns:
        成功したらTrue
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "voting.json"

    # 全体統計を計算
    total_positive = sum(i["reactions"]["positive"] for i in issues_with_reactions)
    total_negative = sum(i["reactions"]["negative"] for i in issues_with_reactions)
    total_votes = total_positive + total_negative

    overall_approval = total_positive / total_votes if total_votes > 0 else 0.5
    overall_consensus = calculate_consensus_score(overall_approval, total_votes)

    # 投票が多い順にソート
    sorted_issues = sorted(
        issues_with_reactions,
        key=lambda x: x["reactions"]["total"],
        reverse=True
    )

    # クラスタ傾向をリストに変換
    cluster_list = [
        {"cluster_id": k, **v}
        for k, v in cluster_trends.items()
    ]
    cluster_list.sort(key=lambda x: x["total_votes"], reverse=True)

    result = {
        "updated_at": datetime.now().isoformat(),
        "summary": {
            "total_issues": len(issues_with_reactions),
            "total_votes": total_votes,
            "total_positive": total_positive,
            "total_negative": total_negative,
            "overall_approval_rate": round(overall_approval, 3),
            "overall_consensus": overall_consensus["consensus"],
            "overall_division": overall_consensus["division"],
            "confidence": overall_consensus["confidence"]
        },
        "cluster_trends": cluster_list,
        "issues": sorted_issues[:100]  # 上位100件のみ
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"投票結果を保存: {output_path}")
        return True

    except Exception as e:
        logger.error(f"ファイル保存エラー: {e}")
        return False


def main():
    """
    メインエントリーポイント

    使用方法:
        python reaction_aggregator.py [--update-qdrant]
    """
    update_qdrant = "--update-qdrant" in sys.argv

    # 1. Forgejoから全Issue取得
    logger.info("Step 1: Forgejoから全Issue取得中...")
    issues = fetch_all_issues()

    if not issues:
        logger.warning("Issueが見つかりません")
        # 空の結果を保存
        empty_result = {
            "updated_at": datetime.now().isoformat(),
            "summary": {
                "total_issues": 0,
                "total_votes": 0,
                "message": "Issueが見つかりませんでした"
            },
            "cluster_trends": [],
            "issues": []
        }
        save_voting_results([], {})
        print(json.dumps(empty_result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 2. 各Issueのリアクションを取得
    logger.info("Step 2: リアクションを取得中...")
    issues_with_reactions = []

    for issue in issues:
        issue_number = issue["number"]
        issue_id = issue["id"]

        # リアクション取得
        raw_reactions = fetch_issue_reactions(issue_number)
        aggregated = aggregate_reactions(raw_reactions)
        approval_rate = calculate_approval_rate(aggregated)
        consensus = calculate_consensus_score(
            approval_rate,
            aggregated["positive"] + aggregated["negative"]
        )

        issue_data = {
            "issue_id": issue_id,
            "issue_number": issue_number,
            "title": issue["title"],
            "reactions": aggregated,
            "raw_reactions": raw_reactions,
            "approval_rate": round(approval_rate, 3),
            "consensus": consensus,
            "url": issue.get("html_url", "")
        }

        issues_with_reactions.append(issue_data)

        # Qdrant更新（オプション）
        if update_qdrant:
            update_qdrant_reactions(issue_id, aggregated, approval_rate)

        logger.debug(f"Issue #{issue_number}: 👍{aggregated['positive']} 👎{aggregated['negative']}")

    logger.info(f"{len(issues_with_reactions)}件のリアクションを集計完了")

    # 3. クラスタ別投票傾向を分析
    logger.info("Step 3: クラスタ別投票傾向を分析中...")
    cluster_trends = analyze_cluster_voting_trend(issues_with_reactions)

    # 4. 結果を保存
    logger.info("Step 4: 結果を保存中...")
    save_voting_results(issues_with_reactions, cluster_trends)

    # 結果出力
    total_positive = sum(i["reactions"]["positive"] for i in issues_with_reactions)
    total_negative = sum(i["reactions"]["negative"] for i in issues_with_reactions)

    print(json.dumps({
        "status": "ok",
        "total_issues": len(issues_with_reactions),
        "total_positive": total_positive,
        "total_negative": total_negative,
        "cluster_count": len(cluster_trends)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
