"""离线视觉预缓存：起 Step3-VL → 解 mock/panels 下所有图 → checkpoints/vision_cache/*.json → 恢复 Nemotron。
演示前跑一次：python prep_vision.py
之后现场只跑 Nemotron（快速模式），不切换。"""
from __future__ import annotations
import os, sys, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from clients import step3vl_image_json, ping
from schemas import INSTRUMENT_PANEL_JSON_SCHEMA
import pipeline

PANELS = ROOT / "mock" / "panels"
CACHE = ROOT / "checkpoints" / "vision_cache"

def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    print("ensure Step3-VL up..."); print(pipeline.ensure_step3vl())
    # 等就绪
    for _ in range(60):
        if ping().get("step3vl","").startswith("up"): break
        import time; time.sleep(5)
    imgs = sorted(PANELS.glob("*.png"))
    print(f"{len(imgs)} images to parse")
    for img in imgs:
        print(" →", img.name)
        v = step3vl_image_json(str(img), INSTRUMENT_PANEL_JSON_SCHEMA, max_tokens=800)
        (CACHE / f"{img.stem}.json").write_text(json.dumps(v, ensure_ascii=False, indent=2))
        print("   ", json.dumps(v, ensure_ascii=False)[:160])
    print("restore Nemotron..."); subprocess.run(["bash","-lc",str(Path.home()/"run-nemotron.sh")], check=False)
    print("DONE. vision_cache:", len(list(CACHE.glob('*.json'))), "files")

if __name__ == "__main__":
    main()
