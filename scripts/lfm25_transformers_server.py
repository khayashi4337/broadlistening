#!/usr/bin/env python3
"""
LFM2.5 Transformers Server
Japanese-specialized model server using HuggingFace Transformers
Model: LiquidAI/LFM2.5-1.2B-JP
"""

import os
import logging
from typing import Optional, List

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LFM2.5 Transformers Server",
    description="Japanese-specialized LLM API using LiquidAI/LFM2.5-1.2B-JP",
    version="1.0.0"
)

# Model configuration
MODEL_ID = os.getenv("MODEL_ID", "LiquidAI/LFM2.5-1.2B-JP")
DEVICE = os.getenv("DEVICE", "cpu")
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "2048"))

# Global model and tokenizer
model = None
tokenizer = None


def load_model():
    """Load model and tokenizer at startup"""
    global model, tokenizer

    logger.info(f"Loading model: {MODEL_ID}")
    logger.info(f"Device: {DEVICE}")
    logger.info(f"Max length: {MAX_LENGTH}")

    try:
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            trust_remote_code=True
        )

        # Set pad token if not exists
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Determine dtype based on device
        if DEVICE == "cpu":
            dtype = torch.float32  # CPU requires float32
        else:
            dtype = torch.float16

        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            device_map=DEVICE if DEVICE != "cpu" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        if DEVICE == "cpu":
            model = model.to("cpu")

        model.eval()
        logger.info("Model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Initialize model on startup"""
    load_model()


# Request/Response models
class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 100
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    top_k: Optional[int] = 50
    do_sample: Optional[bool] = True


class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 100
    temperature: Optional[float] = 0.7
    stop: Optional[List[str]] = None


class ClassifyRequest(BaseModel):
    text: str
    categories: Optional[List[str]] = None


class SummarizeRequest(BaseModel):
    text: str
    max_length: Optional[int] = 100


class ExtractThemesRequest(BaseModel):
    text: str
    num_themes: Optional[int] = 3


# Health check
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": DEVICE,
        "message": "LFM2.5 Transformers server is running"
    }


# OpenAI-compatible completions endpoint
@app.post("/v1/completions")
async def completions(req: CompletionRequest):
    """OpenAI-compatible completions endpoint"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        inputs = tokenizer(
            req.prompt,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH
        )

        if DEVICE == "cpu":
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=req.max_tokens,
                temperature=req.temperature if req.temperature > 0 else 1.0,
                do_sample=req.temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

        # Decode only new tokens
        input_length = inputs["input_ids"].shape[1]
        generated_text = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        )

        # Handle stop sequences
        if req.stop:
            for stop_seq in req.stop:
                if stop_seq in generated_text:
                    generated_text = generated_text.split(stop_seq)[0]

        return {
            "id": "cmpl-lfm25",
            "object": "text_completion",
            "model": MODEL_ID,
            "choices": [{
                "text": generated_text,
                "index": 0,
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": input_length,
                "completion_tokens": len(outputs[0]) - input_length,
                "total_tokens": len(outputs[0])
            }
        }

    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Generate endpoint (custom)
@app.post("/generate")
async def generate(req: GenerateRequest):
    """Generate text completion"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        inputs = tokenizer(
            req.prompt,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH
        )

        if DEVICE == "cpu":
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=req.max_tokens,
                temperature=req.temperature if req.do_sample else 1.0,
                top_p=req.top_p,
                top_k=req.top_k,
                do_sample=req.do_sample,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

        # Decode full output
        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Get only generated part
        input_length = inputs["input_ids"].shape[1]
        generated_text = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        )

        return {
            "prompt": req.prompt,
            "completion": generated_text,
            "full_text": full_text,
            "stop_reason": "stop"
        }

    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Classify endpoint
@app.post("/classify")
async def classify(req: ClassifyRequest):
    """Classify text into categories (Japanese-optimized)"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    categories = req.categories or ["問題提起", "提案", "質問", "フィードバック"]

    prompt = f"""以下のテキストを次のカテゴリのいずれかに分類してください: {', '.join(categories)}

テキスト: {req.text}

分類結果:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_LENGTH)

        if DEVICE == "cpu":
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.3,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id
            )

        input_length = inputs["input_ids"].shape[1]
        classification = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        ).strip()

        return {
            "text": req.text,
            "classification": classification,
            "categories": categories
        }

    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Summarize endpoint
@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    """Summarize text (Japanese-optimized)"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt = f"""以下のテキストを2-3文で要約してください。

テキスト: {req.text}

要約:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_LENGTH)

        if DEVICE == "cpu":
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=req.max_length,
                temperature=0.5,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id
            )

        input_length = inputs["input_ids"].shape[1]
        summary = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        ).strip()

        return {
            "original": req.text,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Summarization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Extract themes endpoint
@app.post("/extract_themes")
async def extract_themes(req: ExtractThemesRequest):
    """Extract themes from text (Japanese-optimized)"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prompt = f"""以下のテキストから主要なテーマを{req.num_themes}つ抽出してください。
各テーマは簡潔な単語やフレーズで表現してください。

テキスト: {req.text}

テーマ:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_LENGTH)

        if DEVICE == "cpu":
            inputs = {k: v.to("cpu") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.5,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id
            )

        input_length = inputs["input_ids"].shape[1]
        themes = tokenizer.decode(
            outputs[0][input_length:],
            skip_special_tokens=True
        ).strip()

        return {
            "text": req.text,
            "themes": themes,
            "num_requested": req.num_themes
        }

    except Exception as e:
        logger.error(f"Theme extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Model info endpoint
@app.get("/info")
async def info():
    """Get model information"""
    return {
        "model_id": MODEL_ID,
        "device": DEVICE,
        "max_length": MAX_LENGTH,
        "framework": "transformers",
        "endpoints": [
            "GET /health - Health check",
            "GET /info - Model information",
            "POST /v1/completions - OpenAI-compatible completions",
            "POST /generate - Text generation",
            "POST /classify - Text classification",
            "POST /summarize - Text summarization",
            "POST /extract_themes - Theme extraction"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
