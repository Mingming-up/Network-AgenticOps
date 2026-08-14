# Ollama 基础测试：先检查目标模型是否存在，再执行一次最小推理请求。
import os

import pytest
import requests
from dotenv import load_dotenv

# URL 和模型名允许通过本地 .env 覆盖，避免把机器配置写死在测试里。
load_dotenv()

OLLAMA_API = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_BASE_URL = OLLAMA_API.removesuffix("/api/chat")
MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")


def test_ollama_interaction():
    # 第一步：访问 /api/tags，确认 Ollama 服务在线并列出本机模型。
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        response.raise_for_status()
    except requests.ConnectionError:
        pytest.fail(f"Cannot connect to Ollama at {OLLAMA_BASE_URL}")

    # 列表推导式只提取每个模型的 name 字段，便于做存在性断言。
    models = [model["name"] for model in response.json().get("models", [])]
    assert any(MODEL in model for model in models), f"Model '{MODEL}' not found in {models}"

    # 第二步：真正发起一次非流式推理，确认模型不仅存在而且可以生成内容。
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": MODEL, "prompt": "Say hello in one sentence.", "stream": False},
        timeout=60,
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("response")
