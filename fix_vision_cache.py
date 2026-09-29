"""修复 vision_cache：Step3-VL 输出的是思考链叙述(_raw)，用 Nemotron(已恢复) 重新抽成干净 JSON 覆写。
不切模型、不读内容到本地。运行：python fix_vision_cache.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from clients import nemotron_json

CACHE = ROOT / "checkpoints" / "vision_cache"
SCHEMA = "{panel_type,brand,model,range_min,range_max,range_unit,setpoint,measured,measured_unit,step_id,warnings,missing,bbox}"

for f in sorted(CACHE.glob("*.json")):
    d = json.loads(f.read_text())
    if d.get("_parse_error") or "_raw" in d:
        raw = d.get("_raw", "")
        out = nemotron_json(
            "你是结构化抽取器。从下面模型对仪器面板的描述中抽取字段，输出严格 JSON 匹配 schema: " + SCHEMA +
            "。数值用数字，缺失用 null，禁止任何解释。",
            "模型描述:\n" + raw[:2000], json_mode=True)
        if isinstance(out, dict) and not out.get("_parse_error"):
            f.write_text(json.dumps(out, ensure_ascii=False, indent=2))
            print(f.name, "->", out.get("panel_type"), "measured=", out.get("measured"), out.get("measured_unit"))
        else:
            print(f.name, "still failed, keys=", list(out.keys()) if isinstance(out,dict) else type(out))
    else:
        print(f.name, "already clean:", d.get("panel_type"), d.get("measured"))
print("DONE")
