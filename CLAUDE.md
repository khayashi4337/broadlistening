# Broadlistening Project - Claude Code 引き継ぎ資料

## プロジェクト概要

**ゴール**: Forgejo + Qdrant + LFM2.5 で市民/社員の意見をクラスタリング・可視化するブロードリスニング基盤を構築する

**コンセプト**: 
- 安野たかひろ氏（チームみらい）のブロードリスニングシステムをシンプルに再現
- 一般企業向け、docker-composeで無料で立ち上がる構成
- 親和図法（KJ法）のデジタル・自動化版

## 技術選定

| コンポーネント | 選定 | 理由 |
|---------------|------|------|
| 意見収集 | Forgejo | セルフホスト、Issue機能、API充実 |
| ベクトルDB | Qdrant | 軽量、Docker対応、類似検索高速 |
| LLM | LFM2.5 (llama.cpp) | ローカル実行、無料、分類タスク向き |
| Embedding | bge-m3 (TEI) | 多言語対応、無料 |
| パイプライン | n8n | ノーコード、Webhook対応 |
| 可視化 | vis.js + nginx | 軽量、カスタマイズ可能 |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    完全無料構成                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   [Forgejo]  ──Webhook──>  [n8n]                       │
│       │                      │                          │
│       │                      ├──> [LFM2.5] 分類・要約   │
│       │                      │                          │
│       │                      ├──> [Embedding] ベクトル化│
│       │                      │                          │
│       │                      └──> [Qdrant] 保存・検索   │
│       │                                                 │
│       └──────────────> [Web UI] 可視化                  │
│                                                         │
│   外部API: なし                                          │
│   月額コスト: ¥0（電気代のみ）                           │
└─────────────────────────────────────────────────────────┘
```

## LFM2.5の役割

対話Botではなく、バッチ処理・分類系タスクに特化：

- テキスト分類（問題提起/提案/質問）
- テーマ抽出
- クラスタラベル生成（親和図のタイトル）
- 要約・サマリ生成
- 感情分析

## 処理フロー

```python
# Issue登録時（毎回・LFM2.5）
def on_issue_created(issue):
    # 1. Embedding生成（bge-m3）
    embedding = embedding_api.encode(issue.body)
    
    # 2. Qdrant保存
    qdrant.upsert(issue.id, embedding, metadata)
    
    # 3. 類似Issue検索
    similar = qdrant.search(embedding, limit=5)
    
    # 4. LFM2.5で分類
    category = lfm.classify(issue.body)      # 問題提起/提案/質問
    themes = lfm.extract_themes(issue.body)  # テーマ抽出
    
    # 5. JSON出力（Web UI用）
    update_issues_json()

# 週次バッチ
def weekly_clustering():
    clusters = kmeans(all_embeddings)
    for cluster in clusters:
        label = lfm.summarize_cluster(cluster.issues)
    generate_weekly_summary()
```

## 親和図法との対応

| 親和図法 | このシステム |
|---------|-------------|
| 付箋 | Forgejo Issue |
| 付箋を並べる | Qdrant + UMAP（2D座標） |
| 似たものをグループ化 | K-meansクラスタリング |
| グループにタイトル | LFM2.5でラベル生成 |
| 俯瞰する | vis.jsでグラフ表示 |

## ディレクトリ構成

```
broadlistening/
├── docker-compose.yml
├── models/
│   └── lfm-2.5-3b-q4_k_m.gguf
├── embedding_models/
├── web/
│   ├── index.html
│   ├── graph.js
│   └── data/
│       └── issues.json
├── scripts/
│   ├── setup.sh
│   └── download_model.sh
└── n8n_workflows/
    └── issue_pipeline.json
```

## 次のアクション（Phase 1）

1. [ ] docker-compose.yml 完成
2. [ ] models/ にLFM2.5ダウンロード
3. [ ] Forgejo初期設定
4. [ ] n8n Webhook設定
5. [ ] LFM2.5分類プロンプト作成
6. [ ] Qdrant保存・検索スクリプト
7. [ ] vis.js可視化UI作成
8. [ ] 動作確認

## 参考リンク

- Talk to the City: https://github.com/AIObjectives/talk-to-the-city-reports
- 広聴AI: https://github.com/digitaldemocracy2030/kouchou-ai
- LFM2.5: https://huggingface.co/liquidai/lfm-2.5-3b-gguf
- bge-m3: https://huggingface.co/BAAI/bge-m3

## 議論の経緯（このチャットで決まったこと）

1. ブロードリスニングの概念整理（安野たかひろ、vTaiwan、Polis）
2. Qdrantでembedding保存 → クラスタリング → 親和図法のデジタル版
3. Obsidian案 → Web完結（vis.js）に変更
4. LLMは対話Botではなく分類・要約に特化
5. LFM2.5ローカル実行で完全無料構成
6. 一般企業向けにピボット（CS、HR、製品開発等）
