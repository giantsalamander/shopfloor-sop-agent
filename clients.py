"""双模型客户端：Nemotron(:8000) 文本/推理 + Step3-VL(:8001) 图文。
OpenAI 兼容协议直连 vLLM，不依赖模型原生 tool_use。"""
from __future__ import annotations
import json, os, re
from openai import OpenAI

NEMOTRON_BASE = os.getenv("NEMOTRON_BASE_URL", "http://localhost:8000/v1")
STEP3VL_BASE  = os.getenv("STEP3VL_BASE_URL",  "http://localhost:8001/v1")
DUMMY_KEY = "sk-dummy"

nemotron = OpenAI(base_url=NEMOTRON_BASE, api_key=DUMMY_KEY, timeout=300)
step3vl  = OpenAI(base_url=STEP3VL_BASE,  api_key=DUMMY_KEY, timeout=300)

NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nemotron")
STEP3VL_MODEL  = os.getenv("STEP3VL_MODEL",  "step3vl")


def _strip_reasoning(text: str) -> str:
    """Nemotron/Step3-VL 会先吐思考链再给答案；提取首个 ```json ... ``` 或末段 JSON。
    没有 fenced block 就尝试找首个 { ... }。"""
    if not text:
        return text
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    if m:
        return m.group(1).strip()
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0).strip() if m else text


def nemotron_json(system: str, user: str, *, max_tokens: int = 4096, json_mode: bool = False) -> dict:
    """让 Nemotron 出 JSON。json_mode=True 时用 response_format json_object 强制合法 JSON。
    prompt 强约束 '只输出 JSON'，再兜底解析。"""
    kwargs = dict(model=NEMOTRON_MODEL, max_tokens=max_tokens, temperature=0.2,
                  messages=[{"role": "system", "content": system},
                            {"role": "user", "content": user + "\n\nIMPORTANT: 输出严格 JSON，不要额外解释。"}])
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = nemotron.chat.completions.create(**kwargs)
    raw = resp.choices[0].message.content or ""
    cleaned = _strip_reasoning(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        return {"_raw": raw, "_parse_error": True}


def step3vl_image(image_path_or_b64: str, question: str, *, max_tokens: int = 1024) -> str:
    """Step3-VL 识图。image 可为本地路径或 data: URL。返回文本。"""
    import base64, mimetypes
    if image_path_or_b64.startswith(("http", "data:")):
        url = image_path_or_b64
    else:
        mime = mimetypes.guess_type(image_path_or_b64)[0] or "image/png"
        with open(image_path_or_b64, "rb") as f:
            url = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    resp = step3vl.chat.completions.create(
        model=STEP3VL_MODEL, max_tokens=max_tokens, temperature=0.1,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": question},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
    )
    return resp.choices[0].message.content or ""


def step3vl_image_json(image_path_or_b64: str, schema, *, max_tokens: int = 1024) -> dict:
    """识图→JSON。用 response_format json_object 强制合法 JSON（vLLM JSON 模式）。
    schema 可为 dict（转提示）或 str。"""
    import base64, mimetypes, json as _json
    if image_path_or_b64.startswith(("http", "data:")):
        url = image_path_or_b64
    else:
        mime = mimetypes.guess_type(image_path_or_b64)[0] or "image/png"
        with open(image_path_or_b64, "rb") as f:
            url = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    hint = _json.dumps(schema) if isinstance(schema, dict) else str(schema)
    resp = step3vl.chat.completions.create(
        model=STEP3VL_MODEL, max_tokens=max_tokens, temperature=0.1,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": f"Extract instrument panel fields into a JSON object matching this schema. Fields not visible -> null. Numeric values as numbers. Schema: {hint}"},
            {"type": "image_url", "image_url": {"url": url}}]}])
    raw = resp.choices[0].message.content or ""
    cleaned = _strip_reasoning(raw)
    try:
        return json.loads(cleaned)
    except Exception:
        return {"_raw": raw, "_parse_error": True}


def ping() -> dict:
    """健康检查：返回两个端点 /v1/models 状态。"""
    out = {"nemotron": "down", "step3vl": "down"}
    try:
        ms = nemotron.models.list().data
        out["nemotron"] = "up:" + ",".join(m.id for m in ms)
    except Exception as e:
        out["nemotron"] = f"err:{e}"
    try:
        ms = step3vl.models.list().data
        out["step3vl"] = "up:" + ",".join(m.id for m in ms)
    except Exception as e:
        out["step3vl"] = f"err:{e}"
    return out
