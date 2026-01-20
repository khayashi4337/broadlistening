# LFM2.5 ファインチューニングガイド

BroadlisteningシステムのLLM（LFM2.5）をカスタマイズし、分類精度を向上させるためのガイドです。

## 目次

1. [概要](#概要)
2. [フレームワーク比較](#フレームワーク比較)
3. [ファインチューニング手法](#ファインチューニング手法)
4. [学習方式](#学習方式)
5. [環境構築](#環境構築)
6. [データセット準備](#データセット準備)
7. [実践：Unslothでのファインチューニング](#実践unslothでのファインチューニング)
8. [実践：Axolotlでのファインチューニング](#実践axolotlでのファインチューニング)
9. [実践：TRLでのファインチューニング](#実践trlでのファインチューニング)
10. [学習済みモデルの利用](#学習済みモデルの利用)
11. [トラブルシューティング](#トラブルシューティング)

---

## 概要

### なぜファインチューニングが必要か

LFM2.5は汎用的なLLMですが、Broadlisteningの分類タスクに特化させることで：

- **分類精度の向上**: 「問題提起」「提案」「質問」の判定精度が上がる
- **一貫性の確保**: 同じような意見に対して同じ分類を返す
- **ドメイン適応**: 特定業界（行政、製造業など）の用語を理解
- **推論速度の向上**: プロンプトを短くできるため高速化

### カスタマイズの3段階

| 段階 | 方法 | 難易度 | 効果 |
|------|------|--------|------|
| 1 | プロンプト調整 | 低 | 小 |
| 2 | LoRA/QLoRA | 中 | 中〜大 |
| 3 | フルファインチューニング | 高 | 大 |

本ガイドでは主に **段階2（LoRA/QLoRA）** を解説します。

---

## フレームワーク比較

LIQUID AIが推奨する3つのフレームワーク：

### TRL (Transformers Reinforcement Learning)

HuggingFace公式のファインチューニングライブラリ。

| 項目 | 内容 |
|------|------|
| **特徴** | SFT、DPO、PPO、ORPO等を統一APIで提供 |
| **メリット** | 細かい制御が可能、豊富なドキュメント |
| **デメリット** | コード量が多い |
| **向いている人** | Python経験者、細かくカスタマイズしたい人 |

```python
from trl import SFTTrainer, DPOTrainer
```

### Unsloth

高速化に特化したファインチューニングライブラリ。

| 項目 | 内容 |
|------|------|
| **特徴** | 2-5倍高速、メモリ70%削減 |
| **メリット** | Google Colab無料枠で実行可能 |
| **デメリット** | 対応モデルが限定的 |
| **向いている人** | リソース制約がある人、すぐ試したい人 |

```python
from unsloth import FastLanguageModel
```

### Axolotl

YAML設定ベースのファインチューニングツールキット。

| 項目 | 内容 |
|------|------|
| **特徴** | コード不要、YAML設定のみで学習 |
| **メリット** | 再現性が高い、マルチGPU対応 |
| **デメリット** | 柔軟性は低い |
| **向いている人** | 設定ファイルで管理したい人、チーム開発 |

```bash
axolotl train configs/lfm2-lora.yml
```

### 選び方フローチャート

```
GPU環境は？
├─ なし/Colab無料 → Unsloth + QLoRA
├─ 1枚 → Unsloth + LoRA または Axolotl
└─ 複数枚 → Axolotl + DeepSpeed

コードを書きたい？
├─ はい → TRL
└─ いいえ → Axolotl
```

---

## ファインチューニング手法

### LoRA (Low-Rank Adaptation) ⭐推奨

**概要**: モデル全体ではなく、小さなアダプター重み（1-2%）のみを学習

**メリット**:
- メモリ効率が高い（VRAM 8GB程度で可能）
- 学習が速い（数時間〜）
- ベースモデルの知識を保持
- 複数タスク用のアダプターを切り替え可能

**パラメータ解説**:

| パラメータ | 説明 | 推奨値 |
|-----------|------|--------|
| `r` (rank) | アダプターのランク。大きいほど表現力↑メモリ↑ | 8〜32 |
| `lora_alpha` | スケーリング係数。通常 r の2倍 | 16〜64 |
| `lora_dropout` | 過学習防止 | 0.05〜0.1 |
| `target_modules` | 適用するレイヤー | q_proj, v_proj等 |

### QLoRA (Quantized LoRA)

**概要**: LoRA + 4bit量子化でさらにメモリ削減

**メリット**:
- メモリ使用量を約4倍削減
- 性能はLoRAとほぼ同等
- Google Colab無料枠（T4 GPU）で実行可能

**デメリット**:
- 推論時も量子化が必要
- わずかな精度低下の可能性

### Full Fine-Tuning

**概要**: 全パラメータを更新

**メリット**:
- 最大限のタスク適応
- 理論上の性能上限が最も高い

**デメリット**:
- 大量のVRAMが必要（24GB以上推奨）
- 学習時間が長い
- 破滅的忘却のリスク

---

## 学習方式

### SFT (Supervised Fine-Tuning)

**用途**: 指示追従、分類タスク

**データ形式**:
```json
{
  "instruction": "以下の意見を「問題提起」「提案」「質問」「その他」に分類してください。",
  "input": "駅前の駐輪場が狭くて困っています",
  "output": "問題提起"
}
```

**学習率**: `1e-5` 〜 `5e-5`

**Broadlisteningでの活用**:
- 意見の分類
- テーマ抽出
- クラスタラベル生成

### DPO (Direct Preference Optimization)

**用途**: 出力品質の調整、好ましい応答の学習

**データ形式**:
```json
{
  "prompt": "以下の意見を分類してください: 公園を増やしてほしい",
  "chosen": "提案",
  "rejected": "問題提起"
}
```

**学習率**: `1e-7` 〜 `1e-6`（SFTより低い）

**パラメータ**:
- `beta`: 基本モデルからの逸脱度（0.1〜0.5）

**Broadlisteningでの活用**:
- 分類の境界ケース改善
- 一貫性のある出力スタイル

### 推奨ワークフロー

```
1. SFTで基本的な分類能力を学習
   ↓
2. DPOで境界ケースや品質を調整（オプション）
```

---

## 環境構築

### 必要スペック

| 手法 | VRAM | RAM | ストレージ |
|------|------|-----|-----------|
| QLoRA | 6GB+ | 16GB+ | 20GB+ |
| LoRA | 12GB+ | 16GB+ | 20GB+ |
| Full | 24GB+ | 32GB+ | 50GB+ |

### Google Colab（無料）での環境構築

```python
# Unslothインストール
!pip install unsloth transformers>=4.55.0 torch>=2.6
!pip install trl datasets

# 確認
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
```

### ローカル環境での環境構築

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# パッケージインストール
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install unsloth transformers>=4.55.0
pip install trl datasets peft accelerate bitsandbytes

# Axolotlを使う場合
pip install axolotl
```

---

## データセット準備

### Broadlistening用データセット形式

#### SFT用（分類タスク）

`data/classification_train.jsonl`:
```jsonl
{"instruction": "以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。", "input": "駅前の駐輪場が狭くて、朝は停める場所がありません。", "output": "問題提起"}
{"instruction": "以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。", "input": "公園にベンチを増やしてはどうでしょうか。", "output": "提案"}
{"instruction": "以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。", "input": "ゴミ収集日はいつですか？", "output": "質問"}
{"instruction": "以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。", "input": "いつもありがとうございます。", "output": "その他"}
```

#### DPO用（品質調整）

`data/classification_dpo.jsonl`:
```jsonl
{"prompt": "以下の意見を分類: 道路の舗装が悪くて危ない", "chosen": "問題提起", "rejected": "提案"}
{"prompt": "以下の意見を分類: 信号機を設置してほしい", "chosen": "提案", "rejected": "問題提起"}
```

### データセット作成のコツ

1. **バランス**: 各カテゴリ同数程度のサンプルを用意
2. **境界ケース**: 判断が難しい例を意図的に含める
3. **多様性**: 様々な表現パターンを含める
4. **品質**: 人間がラベル付けを確認

**推奨サンプル数**:
| 用途 | 最小 | 推奨 | 理想 |
|------|------|------|------|
| PoC | 100 | 500 | - |
| 本番 | 500 | 2,000 | 10,000+ |

### 既存データからの変換スクリプト

```python
import json

def convert_issues_to_sft(issues_json_path, output_path):
    """Broadlisteningの issues.json を SFT形式に変換"""
    with open(issues_json_path, 'r', encoding='utf-8') as f:
        issues = json.load(f)

    instruction = "以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。"

    with open(output_path, 'w', encoding='utf-8') as f:
        for issue in issues:
            if 'category' in issue:  # ラベル付き済みのみ
                record = {
                    "instruction": instruction,
                    "input": issue.get('body', issue.get('title', '')),
                    "output": issue['category']
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

# 使用例
convert_issues_to_sft('web/data/issues.json', 'data/classification_train.jsonl')
```

---

## 実践：Unslothでのファインチューニング

最も簡単に始められる方法です。Google Colabで実行可能。

### ステップ1: モデルのロード

```python
from unsloth import FastLanguageModel
import torch

# LFM2.5モデルをロード（4bit量子化）
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="LiquidAI/LFM2.5-1.2B-Instruct",
    max_seq_length=2048,
    dtype=None,  # 自動検出
    load_in_4bit=True,  # QLoRAを使用
)

print(f"Model loaded: {model.config._name_or_path}")
```

### ステップ2: LoRAアダプターの設定

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # LoRAランク
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    use_gradient_checkpointing="unsloth",  # メモリ節約
    random_state=42,
)
```

### ステップ3: データセットの準備

```python
from datasets import load_dataset

# JSONLファイルからロード
dataset = load_dataset('json', data_files='data/classification_train.jsonl')

# プロンプトテンプレート
def formatting_prompts_func(examples):
    texts = []
    for instruction, input_text, output in zip(
        examples['instruction'],
        examples['input'],
        examples['output']
    ):
        text = f"""### 指示:
{instruction}

### 入力:
{input_text}

### 出力:
{output}"""
        texts.append(text)
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)
```

### ステップ4: 学習の実行

```python
from trl import SFTTrainer, SFTConfig

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset['train'],
    args=SFTConfig(
        output_dir="./outputs/lfm2-classification-lora",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=100,  # 本番は500-1000
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        save_steps=50,
        dataset_text_field="text",
        max_seq_length=2048,
    ),
)

# 学習開始
trainer.train()
```

### ステップ5: モデルの保存

```python
# LoRAアダプターのみ保存
model.save_pretrained("./outputs/lfm2-classification-lora")
tokenizer.save_pretrained("./outputs/lfm2-classification-lora")

# GGUF形式でエクスポート（llama.cpp用）
model.save_pretrained_gguf(
    "./outputs/lfm2-classification-gguf",
    tokenizer,
    quantization_method="q4_k_m"
)
```

---

## 実践：Axolotlでのファインチューニング

YAML設定ファイルで管理する方法。再現性が高くチーム開発向き。

### 設定ファイルの作成

`configs/lfm2-classification-lora.yml`:
```yaml
# モデル設定
base_model: LiquidAI/LFM2.5-1.2B-Instruct
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

# データセット
datasets:
  - path: ./data/classification_train.jsonl
    type: alpaca

# LoRA設定
adapter: lora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj

# 学習パラメータ
sequence_len: 2048
micro_batch_size: 4
gradient_accumulation_steps: 4
num_epochs: 2
learning_rate: 2e-4
optimizer: adamw_torch
lr_scheduler: cosine
warmup_ratio: 0.1

# 最適化
flash_attention: true
gradient_checkpointing: true
bf16: true

# 出力
output_dir: ./outputs/lfm2-classification-axolotl
logging_steps: 10
save_steps: 100
eval_steps: 100
```

### 学習の実行

```bash
# シングルGPU
axolotl train configs/lfm2-classification-lora.yml

# マルチGPU（DeepSpeed ZeRO-2）
axolotl train configs/lfm2-classification-lora.yml \
  --deepspeed deepspeed_configs/zero2.json

# 推論テスト
axolotl inference configs/lfm2-classification-lora.yml \
  --lora-model-dir ./outputs/lfm2-classification-axolotl
```

---

## 実践：TRLでのファインチューニング

最も細かい制御が可能な方法。

### SFTでの学習

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

# モデルロード
model = AutoModelForCausalLM.from_pretrained(
    "LiquidAI/LFM2.5-1.2B-Instruct",
    torch_dtype="auto",
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained("LiquidAI/LFM2.5-1.2B-Instruct")

# LoRA設定
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)

# データセット
dataset = load_dataset('json', data_files='data/classification_train.jsonl')

# トレーナー設定
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset['train'],
    args=SFTConfig(
        output_dir="./outputs/lfm2-classification-trl",
        num_train_epochs=2,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=10,
        save_steps=100,
    ),
)

trainer.train()
trainer.save_model()
```

### DPOでの品質調整

```python
from trl import DPOTrainer, DPOConfig

# DPO用データセット
dpo_dataset = load_dataset('json', data_files='data/classification_dpo.jsonl')

# DPOトレーナー
dpo_trainer = DPOTrainer(
    model=model,  # SFT済みモデル
    ref_model=None,  # 自動でコピー
    tokenizer=tokenizer,
    train_dataset=dpo_dataset['train'],
    args=DPOConfig(
        output_dir="./outputs/lfm2-classification-dpo",
        num_train_epochs=1,
        per_device_train_batch_size=2,
        learning_rate=5e-7,  # DPOは低い学習率
        beta=0.1,  # KL divergence coefficient
        logging_steps=10,
    ),
)

dpo_trainer.train()
dpo_trainer.save_model()
```

---

## 学習済みモデルの利用

### Broadlisteningへの組み込み

#### 1. LoRAアダプター形式

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# ベースモデルをロード
base_model = AutoModelForCausalLM.from_pretrained("LiquidAI/LFM2.5-1.2B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("LiquidAI/LFM2.5-1.2B-Instruct")

# LoRAアダプターを適用
model = PeftModel.from_pretrained(base_model, "./outputs/lfm2-classification-lora")

# 推論
def classify_opinion(text):
    prompt = f"""### 指示:
以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。

### 入力:
{text}

### 出力:
"""
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=10)
    return tokenizer.decode(outputs[0], skip_special_tokens=True).split("### 出力:")[-1].strip()

# テスト
print(classify_opinion("駐輪場が狭くて困っています"))
# → "問題提起"
```

#### 2. GGUF形式（llama.cpp）

```python
from llama_cpp import Llama

# GGUFモデルをロード
llm = Llama(
    model_path="./outputs/lfm2-classification-gguf/model-q4_k_m.gguf",
    n_ctx=2048,
    n_gpu_layers=-1,  # 全レイヤーGPU
)

def classify_opinion(text):
    prompt = f"""### 指示:
以下の市民意見を「問題提起」「提案」「質問」「その他」に分類してください。

### 入力:
{text}

### 出力:
"""
    output = llm(prompt, max_tokens=10, stop=["###", "\n"])
    return output['choices'][0]['text'].strip()
```

#### 3. Docker環境への組み込み

`docker-compose.yml` の llm サービスを更新:

```yaml
services:
  llm:
    image: ghcr.io/ggerganov/llama.cpp:server
    volumes:
      - ./outputs/lfm2-classification-gguf:/models
    command: >
      --model /models/model-q4_k_m.gguf
      --ctx-size 2048
      --n-gpu-layers -1
      --host 0.0.0.0
      --port 8080
```

---

## トラブルシューティング

### よくある問題と解決策

#### CUDA out of memory

**原因**: VRAMが不足

**解決策**:
```python
# バッチサイズを下げる
per_device_train_batch_size=2

# gradient_accumulation_stepsを上げる
gradient_accumulation_steps=8

# QLoRAを使用
load_in_4bit=True

# gradient checkpointingを有効化
gradient_checkpointing=True
```

#### 学習が収束しない

**原因**: 学習率が不適切、データ品質の問題

**解決策**:
```python
# 学習率を下げる
learning_rate=1e-4

# warmupを追加
warmup_ratio=0.1

# データセットを確認
# - ラベルの一貫性
# - 重複の除去
# - バランスの確認
```

#### 過学習

**原因**: データが少ない、エポック数が多い

**解決策**:
```python
# early stoppingを使用
from transformers import EarlyStoppingCallback

trainer = SFTTrainer(
    ...,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
)

# dropoutを上げる
lora_dropout=0.1

# weight decayを追加
weight_decay=0.01
```

#### 破滅的忘却

**原因**: ベースモデルの知識が失われる

**解決策**:
- LoRA/QLoRAを使用（フルファインチューニングを避ける）
- 学習率を低く設定
- 汎用タスクのデータも混ぜる

---

## 参考リンク

- [LIQUID AI公式ドキュメント](https://docs.liquid.ai/)
- [TRL Documentation](https://huggingface.co/docs/trl/)
- [Unsloth GitHub](https://github.com/unslothai/unsloth)
- [Axolotl GitHub](https://github.com/OpenAccess-AI-Collective/axolotl)
- [PEFT Documentation](https://huggingface.co/docs/peft/)

---

## 関連ドキュメント

- [クイックスタート](quickstart.md)
- [設定ガイド](configuration.md)
- [APIリファレンス](api-reference.md)
- [用語集](glossary.md)
