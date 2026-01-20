#!/usr/bin/env python3
"""
Broadlistening ベンチマークツール

使用方法:
    python scripts/benchmark.py [--quick] [--full]

オプション:
    --quick     簡易テスト（5件、約1分）
    --full      フルテスト（50件、約10-30分）
    (デフォルト) 標準テスト（10件、約2-5分）

このスクリプトは以下を計測します:
- Embedding生成速度
- LLM分類速度
- Qdrant保存・検索速度
- 総合的な処理速度

注意: Docker環境が起動している必要があります。
"""

import os
import sys
import time
import argparse
import statistics
from typing import List, Tuple, Optional

# HTTPリクエスト用
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# =============================================================================
# 定数
# =============================================================================

# テストデータ
SAMPLE_TEXTS = [
    "消費税が10%に上がってから、生活が苦しくなりました。食料品だけでも軽減税率をもっと拡大してほしいです。",
    "子育て支援をもっと充実させてほしい。保育園の待機児童問題が深刻です。",
    "地方のバス路線がどんどん廃止されて、車がないと生活できなくなっています。",
    "オンライン授業の質を向上させてほしい。通信環境の格差が学力格差につながっている。",
    "再生可能エネルギーの導入をもっと進めるべきだと思います。",
    "高齢者向けのデジタル講習会を増やしてほしい。スマホの使い方がわからない。",
    "働き方改革と言いながら、実際には残業が減っていない会社が多い。",
    "公園の遊具が古くて危険です。子供が安全に遊べる環境を整備してください。",
    "ゴミの分別ルールが複雑すぎて、正しく分別できているか不安です。",
    "災害時の避難場所の案内が不十分です。もっとわかりやすく表示してほしい。",
    "図書館の開館時間を延長してほしい。仕事帰りに利用したい。",
    "道路の穴ぼこが多くて自転車で走ると危ない。早急に補修してほしい。",
    "市役所の窓口対応が遅い。オンラインで完結できる手続きを増やしてほしい。",
    "学校給食の質を上げてほしい。栄養バランスだけでなく、おいしさも大事。",
    "ペットと一緒に避難できる場所を確保してほしい。",
    "空き家が増えて治安が悪化している。対策を強化してほしい。",
    "駅前の駐輪場が足りない。違法駐輪が増えて歩行者の邪魔になっている。",
    "医療費の窓口負担が高すぎる。特に慢性疾患を持つ人には厳しい。",
    "若者が地元に残れるような雇用を創出してほしい。",
    "外国人観光客へのゴミ出しルールの説明が不足している。",
    "公共施設のWi-Fi環境を整備してほしい。",
    "防犯カメラの設置を増やして、安全なまちづくりをしてほしい。",
    "介護施設の待機者が多すぎる。施設を増やしてほしい。",
    "公共交通のバリアフリー化をもっと進めてほしい。",
    "夜間の街灯が少なくて怖い。LED化と増設をお願いしたい。",
    "学校のエアコン設置を早急に進めてほしい。夏の教室は危険なほど暑い。",
    "商店街がシャッター街になっている。活性化策を考えてほしい。",
    "SNSでのデマや誹謗中傷への対策を強化してほしい。",
    "投票所が遠くて行きにくい。期日前投票所を増やしてほしい。",
    "ふるさと納税の返礼品競争より、本来の趣旨に立ち返るべき。",
    "騒音問題への対応が遅い。条例を厳しくしてほしい。",
    "子供の医療費無償化の対象年齢を引き上げてほしい。",
    "プラスチックごみの削減に向けた具体的な施策がほしい。",
    "公営住宅の老朽化が進んでいる。建て替えや改修を進めてほしい。",
    "認知症の高齢者を地域で支える仕組みをもっと充実させてほしい。",
    "学校でのプログラミング教育の質を向上させてほしい。",
    "河川の氾濫対策を強化してほしい。毎年浸水被害が出ている。",
    "生活保護の申請手続きがわかりにくい。もっと簡素化してほしい。",
    "公園でのボール遊びを禁止しないでほしい。子供の遊び場がない。",
    "コミュニティバスのルートを見直してほしい。使いにくい。",
    "中小企業への支援を強化してほしい。コロナ後の経営が厳しい。",
    "道路標識が見づらい場所がある。整備してほしい。",
    "高校の学費補助を拡充してほしい。私立に行かざるを得ない家庭もある。",
    "ヤングケアラーへの支援を充実させてほしい。",
    "自転車保険の加入義務化を検討してほしい。事故が増えている。",
    "市民農園を増やしてほしい。食育にもつながる。",
    "障害者の就労支援をもっと充実させてほしい。",
    "公共施設の利用料金を値上げしないでほしい。",
    "ひきこもり支援の窓口がわかりにくい。もっと周知してほしい。",
    "地域の祭りや行事への補助金を増やしてほしい。文化の継承が大事。",
]

# API エンドポイント（Docker環境）
EMBEDDING_URL = os.getenv("EMBEDDING_API_URL", "http://localhost:8081")
LLM_URL = os.getenv("LLM_API_URL", "http://localhost:8080")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


# =============================================================================
# カラー出力
# =============================================================================

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def bold(msg: str) -> str:
    return f"{Colors.BOLD}{msg}{Colors.END}"


def format_time(seconds: float) -> str:
    """時間を読みやすい形式に変換"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        return f"{seconds/60:.1f}分"
    else:
        return f"{seconds/3600:.1f}時間"


# =============================================================================
# ベンチマーク関数
# =============================================================================

def check_services() -> Tuple[bool, bool, bool]:
    """サービスの稼働状況をチェック"""
    embedding_ok = False
    llm_ok = False
    qdrant_ok = False

    if not HAS_REQUESTS:
        print("警告: requestsライブラリがインストールされていません")
        print("  pip install requests")
        return False, False, False

    # Embedding API
    try:
        resp = requests.get(f"{EMBEDDING_URL}/health", timeout=5)
        embedding_ok = resp.status_code == 200
    except Exception:
        pass

    # LLM API
    try:
        resp = requests.get(f"{LLM_URL}/health", timeout=5)
        llm_ok = resp.status_code == 200
    except Exception:
        pass

    # Qdrant
    try:
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        qdrant_ok = resp.status_code == 200
    except Exception:
        pass

    return embedding_ok, llm_ok, qdrant_ok


def benchmark_embedding(texts: List[str]) -> Optional[Tuple[float, float, List]]:
    """Embedding生成のベンチマーク"""
    if not HAS_REQUESTS:
        return None

    times = []
    embeddings = []

    for text in texts:
        try:
            start = time.time()
            resp = requests.post(
                f"{EMBEDDING_URL}/embed",
                json={"inputs": text},
                timeout=60
            )
            elapsed = time.time() - start

            if resp.status_code == 200:
                times.append(elapsed)
                embeddings.append(resp.json())
            else:
                print(f"  Embedding API エラー: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  Embedding API 接続エラー: {e}")
            return None

    total = sum(times)
    avg = statistics.mean(times)
    return total, avg, embeddings


def benchmark_llm(texts: List[str]) -> Optional[Tuple[float, float, List]]:
    """LLM分類のベンチマーク"""
    if not HAS_REQUESTS:
        return None

    times = []
    results = []

    for text in texts:
        try:
            start = time.time()
            resp = requests.post(
                f"{LLM_URL}/v1/completions",
                json={
                    "prompt": f"以下の意見を「問題提起」「提案」「質問」「その他」に分類してください。\n\n意見: {text}\n\n分類:",
                    "max_tokens": 50,
                    "temperature": 0.1,
                },
                timeout=120
            )
            elapsed = time.time() - start

            if resp.status_code == 200:
                times.append(elapsed)
                results.append(resp.json())
            else:
                print(f"  LLM API エラー: {resp.status_code}")
                return None
        except Exception as e:
            print(f"  LLM API 接続エラー: {e}")
            return None

    total = sum(times)
    avg = statistics.mean(times)
    return total, avg, results


def benchmark_qdrant(embeddings: List, texts: List[str]) -> Optional[Tuple[float, float]]:
    """Qdrant保存・検索のベンチマーク"""
    if not HAS_REQUESTS or not embeddings:
        return None

    collection_name = "benchmark_test"
    times = []

    try:
        # テスト用コレクション作成
        requests.delete(f"{QDRANT_URL}/collections/{collection_name}", timeout=10)
        resp = requests.put(
            f"{QDRANT_URL}/collections/{collection_name}",
            json={
                "vectors": {
                    "size": len(embeddings[0][0]) if isinstance(embeddings[0], list) else len(embeddings[0].get("embeddings", [[]])[0]),
                    "distance": "Cosine"
                }
            },
            timeout=10
        )

        # 保存テスト
        for i, (emb, text) in enumerate(zip(embeddings, texts)):
            vector = emb[0] if isinstance(emb, list) else emb.get("embeddings", [[]])[0]
            start = time.time()
            resp = requests.put(
                f"{QDRANT_URL}/collections/{collection_name}/points",
                json={
                    "points": [{
                        "id": i,
                        "vector": vector,
                        "payload": {"text": text[:100]}
                    }]
                },
                timeout=10
            )
            elapsed = time.time() - start
            times.append(elapsed)

        # クリーンアップ
        requests.delete(f"{QDRANT_URL}/collections/{collection_name}", timeout=10)

        total = sum(times)
        avg = statistics.mean(times)
        return total, avg

    except Exception as e:
        print(f"  Qdrant エラー: {e}")
        return None


# =============================================================================
# メイン処理
# =============================================================================

def run_benchmark(num_items: int):
    """ベンチマークを実行"""
    print()
    print(bold("=" * 60))
    print(bold(f"   Broadlistening ベンチマーク ({num_items}件)"))
    print(bold("=" * 60))
    print()

    # サービスチェック
    print("サービス状態を確認中...")
    embedding_ok, llm_ok, qdrant_ok = check_services()

    print()
    print(f"  Embedding API ({EMBEDDING_URL}): {'✓ 稼働中' if embedding_ok else '✗ 停止中'}")
    print(f"  LLM API ({LLM_URL}): {'✓ 稼働中' if llm_ok else '✗ 停止中'}")
    print(f"  Qdrant ({QDRANT_URL}): {'✓ 稼働中' if qdrant_ok else '✗ 停止中'}")
    print()

    if not (embedding_ok or llm_ok or qdrant_ok):
        print(f"{Colors.RED}エラー: すべてのサービスが停止しています{Colors.END}")
        print()
        print("Docker環境を起動してください:")
        print("  docker compose -f docker-compose.cpu.yml up -d")
        print()
        print("起動後、サービスが準備できるまで数分待ってから再実行してください。")
        sys.exit(1)

    # テストデータ準備
    texts = SAMPLE_TEXTS[:num_items]
    print(f"テストデータ: {len(texts)}件")
    print()

    results = {}

    # Embedding ベンチマーク
    if embedding_ok:
        print(bold("-" * 60))
        print("Embedding 生成をテスト中...")
        print(bold("-" * 60))

        emb_result = benchmark_embedding(texts)
        if emb_result:
            total, avg, embeddings = emb_result
            results['embedding'] = {'total': total, 'avg': avg}
            print(f"  合計時間: {format_time(total)}")
            print(f"  平均時間: {format_time(avg)}/件")
            print(f"  スループット: {len(texts)/total:.1f}件/秒")
        else:
            embeddings = []
        print()
    else:
        embeddings = []
        print("Embedding API がスキップされました（停止中）")
        print()

    # LLM ベンチマーク
    if llm_ok:
        print(bold("-" * 60))
        print("LLM 分類をテスト中...")
        print(bold("-" * 60))

        llm_result = benchmark_llm(texts)
        if llm_result:
            total, avg, _ = llm_result
            results['llm'] = {'total': total, 'avg': avg}
            print(f"  合計時間: {format_time(total)}")
            print(f"  平均時間: {format_time(avg)}/件")
            print(f"  スループット: {len(texts)/total:.2f}件/秒")
        print()
    else:
        print("LLM API がスキップされました（停止中）")
        print()

    # Qdrant ベンチマーク
    if qdrant_ok and embeddings:
        print(bold("-" * 60))
        print("Qdrant 保存をテスト中...")
        print(bold("-" * 60))

        qd_result = benchmark_qdrant(embeddings, texts)
        if qd_result:
            total, avg = qd_result
            results['qdrant'] = {'total': total, 'avg': avg}
            print(f"  合計時間: {format_time(total)}")
            print(f"  平均時間: {format_time(avg)}/件")
        print()
    elif not embeddings:
        print("Qdrant テストがスキップされました（Embeddingデータなし）")
        print()
    else:
        print("Qdrant がスキップされました（停止中）")
        print()

    # サマリー
    print(bold("=" * 60))
    print(bold("   ベンチマーク結果サマリー"))
    print(bold("=" * 60))
    print()

    # 総合処理時間計算
    total_per_item = 0
    if 'embedding' in results:
        total_per_item += results['embedding']['avg']
    if 'llm' in results:
        total_per_item += results['llm']['avg']
    if 'qdrant' in results:
        total_per_item += results['qdrant']['avg']

    if total_per_item > 0:
        print(f"  1件あたりの処理時間: {format_time(total_per_item)}")
        print()
        print("  推定処理時間:")
        print(f"    100件:  {format_time(100 * total_per_item)}")
        print(f"    500件:  {format_time(500 * total_per_item)}")
        print(f"    1000件: {format_time(1000 * total_per_item)}")
        print(f"    5000件: {format_time(5000 * total_per_item)}")

        # ボトルネック判定
        print()
        if 'llm' in results and 'embedding' in results:
            if results['llm']['avg'] > results['embedding']['avg'] * 5:
                print(f"  {Colors.YELLOW}⚠ ボトルネック: LLM処理{Colors.END}")
                print("    → GPU環境で大幅に改善できます")
            elif results['embedding']['avg'] > results['llm']['avg'] * 2:
                print(f"  {Colors.YELLOW}⚠ ボトルネック: Embedding生成{Colors.END}")
    else:
        print("  測定できませんでした。サービスの状態を確認してください。")

    print()

    # 環境判定
    print(bold("=" * 60))
    print(bold("   環境評価"))
    print(bold("=" * 60))
    print()

    if 'llm' in results:
        llm_avg = results['llm']['avg']
        if llm_avg < 3:
            print(f"  {Colors.GREEN}◎ 高速環境（GPU利用中と推定）{Colors.END}")
            print("    1000件を約30分で処理できます")
        elif llm_avg < 10:
            print(f"  {Colors.GREEN}○ 良好な環境{Colors.END}")
            print("    1000件を約2-3時間で処理できます")
        elif llm_avg < 30:
            print(f"  {Colors.YELLOW}△ 標準的なCPU環境{Colors.END}")
            print("    1000件を約5-8時間で処理できます")
            print("    → 夜間バッチ処理を推奨")
        else:
            print(f"  {Colors.RED}▽ 低速環境{Colors.END}")
            print("    処理に時間がかかります")
            print("    → GPU環境への移行を検討してください")
    print()


def main():
    """メインエントリーポイント"""
    parser = argparse.ArgumentParser(description="Broadlistening ベンチマークツール")
    parser.add_argument("--quick", action="store_true", help="簡易テスト（5件）")
    parser.add_argument("--full", action="store_true", help="フルテスト（50件）")
    args = parser.parse_args()

    if args.quick:
        num_items = 5
    elif args.full:
        num_items = 50
    else:
        num_items = 10

    if not HAS_REQUESTS:
        print("エラー: requestsライブラリが必要です")
        print("  pip install requests")
        sys.exit(1)

    run_benchmark(num_items)


if __name__ == "__main__":
    main()
