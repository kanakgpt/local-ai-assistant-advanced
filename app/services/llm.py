import logging
import json

import ollama

from app.config import CHAT_MODEL, EMBED_MODEL, OLLAMA_HOST

logger = logging.getLogger(__name__)
client = ollama.Client(host=OLLAMA_HOST)


def embed(texts):
    if not texts:
        return []
    return client.embed(model=EMBED_MODEL, input=texts)["embeddings"]


def chat(system, prompt, temperature=0.2):
    result = client.chat(model=CHAT_MODEL, messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ], options={"temperature": temperature})
    return result["message"]["content"]


def json_chat(system, prompt):
    raw = chat(system + "\nReturn valid JSON only.", prompt, 0)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                result = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                result = None
        else:
            result = None
    if isinstance(result, dict):
        return result
    logger.warning("Ollama returned invalid JSON object for a structured response.")
    return {}
