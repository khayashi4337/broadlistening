#!/usr/bin/env python3
"""
Broadlistening REST API サーバー

意見データ、クラスタ情報、投票結果などを提供するREST APIサーバー。

依存関係:
    - flask: Webフレームワーク
    - flask-cors: CORS対応

使用方法:
    python server.py [--port PORT] [--host HOST]

    --port: ポート番号（デフォルト: 5000）
    --host: ホスト（デフォルト: 0.0.0.0）
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from functools import wraps

# Flaskがない場合の対応
try:
    from flask import Flask, jsonify, request, abort
    from flask_cors import CORS
except ImportError:
    print("必要なライブラリをインストールしてください:")
    print("  pip install flask flask-cors")
    sys.exit(1)

# ロギング設定
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# パス設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "web" / "data"

# 環境変数
API_KEY = os.getenv("BROADLISTENING_API_KEY", "")
RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT", "60"))

# Flaskアプリ
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# レート制限用の簡易キャッシュ
request_counts = {}


def load_json_file(filename: str) -> dict:
    """JSONファイルを読み込む"""
    file_path = DATA_DIR / filename
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.error(f"JSONパースエラー: {filename}")
        return {}


def require_api_key(f):
    """APIキー認証デコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            # APIキーが設定されていない場合は認証不要
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        api_key_param = request.args.get("api_key", "")

        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]
        else:
            provided_key = api_key_param

        if provided_key != API_KEY:
            abort(401, description="Invalid or missing API key")

        return f(*args, **kwargs)
    return decorated


def rate_limit(f):
    """簡易レート制限デコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        client_ip = request.remote_addr
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        key = f"{client_ip}:{current_minute}"

        count = request_counts.get(key, 0)
        if count >= RATE_LIMIT_PER_MINUTE:
            abort(429, description="Rate limit exceeded")

        request_counts[key] = count + 1

        # 古いエントリを削除（メモリリーク防止）
        old_keys = [k for k in request_counts if not k.endswith(current_minute)]
        for k in old_keys:
            del request_counts[k]

        return f(*args, **kwargs)
    return decorated


# ===== API エンドポイント =====

@app.route("/api/health", methods=["GET"])
def health_check():
    """ヘルスチェック"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v1/issues", methods=["GET"])
@rate_limit
def get_issues():
    """意見一覧を取得"""
    data = load_json_file("issues.json")
    issues = data.get("issues", [])

    # ページネーション
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)  # 最大100件

    start = (page - 1) * per_page
    end = start + per_page

    # フィルタリング
    opinion_type = request.args.get("type")
    if opinion_type:
        issues = [i for i in issues if i.get("opinion_type") == opinion_type]

    theme = request.args.get("theme")
    if theme:
        issues = [i for i in issues if theme in i.get("themes", [])]

    total = len(issues)
    paginated = issues[start:end]

    return jsonify({
        "data": paginated,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    })


@app.route("/api/v1/issues/<int:issue_id>", methods=["GET"])
@rate_limit
def get_issue(issue_id):
    """特定の意見を取得"""
    data = load_json_file("issues.json")
    issues = data.get("issues", [])

    for issue in issues:
        if issue.get("id") == issue_id:
            return jsonify({"data": issue})

    abort(404, description="Issue not found")


@app.route("/api/v1/clusters", methods=["GET"])
@rate_limit
def get_clusters():
    """クラスタ一覧を取得"""
    data = load_json_file("clusters.json")

    return jsonify({
        "data": data.get("clusters", []),
        "total_issues": data.get("total_issues", 0),
        "num_clusters": data.get("num_clusters", 0)
    })


@app.route("/api/v1/clusters/<int:cluster_id>", methods=["GET"])
@rate_limit
def get_cluster(cluster_id):
    """特定のクラスタを取得"""
    data = load_json_file("clusters.json")
    clusters = data.get("clusters", [])

    for cluster in clusters:
        if cluster.get("id") == cluster_id:
            return jsonify({"data": cluster})

    abort(404, description="Cluster not found")


@app.route("/api/v1/voting", methods=["GET"])
@rate_limit
def get_voting():
    """投票データを取得"""
    data = load_json_file("voting.json")

    return jsonify({
        "summary": data.get("summary", {}),
        "cluster_trends": data.get("cluster_trends", []),
        "updated_at": data.get("updated_at")
    })


@app.route("/api/v1/reports", methods=["GET"])
@rate_limit
def get_reports():
    """週次レポートを取得"""
    data = load_json_file("reports.json")
    reports = data.get("reports", [])

    # 最新N件
    limit = request.args.get("limit", 5, type=int)
    limit = min(limit, 10)

    return jsonify({
        "data": reports[:limit],
        "updated_at": data.get("updated_at")
    })


@app.route("/api/v1/reports/latest", methods=["GET"])
@rate_limit
def get_latest_report():
    """最新のレポートを取得"""
    data = load_json_file("reports.json")
    reports = data.get("reports", [])

    if not reports:
        abort(404, description="No reports available")

    return jsonify({"data": reports[0]})


@app.route("/api/v1/statistics", methods=["GET"])
@rate_limit
def get_statistics():
    """統計情報を取得"""
    issues_data = load_json_file("issues.json")
    clusters_data = load_json_file("clusters.json")
    voting_data = load_json_file("voting.json")

    issues = issues_data.get("issues", [])

    # 意見タイプ別カウント
    type_counts = {}
    for issue in issues:
        t = issue.get("opinion_type", "その他")
        type_counts[t] = type_counts.get(t, 0) + 1

    # テーマ別カウント
    theme_counts = {}
    for issue in issues:
        for theme in issue.get("themes", []):
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    return jsonify({
        "total_issues": len(issues),
        "total_clusters": len(clusters_data.get("clusters", [])),
        "total_votes": voting_data.get("summary", {}).get("total_votes", 0),
        "by_type": type_counts,
        "top_themes": sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "consensus_score": voting_data.get("summary", {}).get("overall_consensus", 0)
    })


@app.route("/api/v1/search", methods=["GET"])
@rate_limit
def search_issues():
    """意見を検索"""
    query = request.args.get("q", "").lower()
    if not query or len(query) < 2:
        abort(400, description="Search query must be at least 2 characters")

    data = load_json_file("issues.json")
    issues = data.get("issues", [])

    results = []
    for issue in issues:
        title = (issue.get("title") or "").lower()
        body = (issue.get("body") or "").lower()

        if query in title or query in body:
            results.append(issue)

    # 最大50件
    results = results[:50]

    return jsonify({
        "data": results,
        "total": len(results),
        "query": query
    })


# エラーハンドラ
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad Request", "message": str(e.description)}), 400


@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Unauthorized", "message": str(e.description)}), 401


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "message": str(e.description)}), 404


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Too Many Requests", "message": str(e.description)}), 429


@app.errorhandler(500)
def internal_error(_e):
    return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred"}), 500


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(description="Broadlistening API Server")
    parser.add_argument("--port", type=int, default=5000, help="Port number")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--debug", action="store_true", help="Debug mode")

    args = parser.parse_args()

    logger.info(f"Starting API server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
