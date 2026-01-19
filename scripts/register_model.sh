#!/bin/bash

# Ollama Model Registration - Minimal
# Register LFM2.5 from existing model file

set -e

CONTAINER="broadlistening-llm"
MODEL_FILE="${1:-/mnt/f/prj/broadlistening/models/lfm-2.5-3b-q4_k_m.gguf}"
MODEL_NAME="lfm2.5"

echo "================================================"
echo "Ollama Model Registration"
echo "================================================"
echo "Container: $CONTAINER"
echo "Model File: $MODEL_FILE"
echo "Model Name: $MODEL_NAME"
echo ""

# Verify file exists
if [ ! -f "$MODEL_FILE" ]; then
    echo "Error: Model file not found at $MODEL_FILE"
    exit 1
fi

echo "[1/3] Copying model to container..."
docker cp "$MODEL_FILE" "$CONTAINER:/tmp/model.gguf"
echo "OK"

echo "[2/3] Registering model..."
docker exec "$CONTAINER" sh -c "
    echo 'FROM /tmp/model.gguf
PARAMETER temperature 0.7
PARAMETER num_ctx 4096' | ollama create $MODEL_NAME -f -
"
echo "OK"

echo "[3/3] Verifying..."
docker exec "$CONTAINER" ollama list
echo ""

echo "✓ Model registered successfully!"
echo "Model: $MODEL_NAME"
echo "Endpoint: http://localhost:8080/api/generate"
echo ""
