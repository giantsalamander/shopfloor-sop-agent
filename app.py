"""交付物④：Gradio 多Agent 主流程入口。
快速模式（演示）：视觉走 prep_vision.py 预缓存，只跑 Nemotron，无切换。
全流程模式：EvidenceParse 触发 Step3-VL 切换。
启动：python app.py → http://0.0.0.0:7860"""
from __future__ import annotations
import os, sys, json, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import gradio as gr
import pipeline, tools
from clients import ping

MOCK = ROOT/"mock"
DEFAULT_SOP = str(MOCK/"sop_sample.txt")
DEFAULT_CSV = str(MOCK/"worker_batch.csv")
CACHE = ROOT/"checkpoints"/"vision_cache"

def status():
    p = ping()
    return f"Nemotron(:8000): {p.get('nemotron')}\nStep3-VL(:8001): {p.get('step3vl')}\nvision_cache: {len(list(CACHE.glob('*.json')))} files"

def run_pipeline(sop_file, worker_csv, full_mode, resume_step):
    # gradio 上传是临时路径；若上传用其路径，否则用 mock 默认
    sop_path = sop_file if sop_file else DEFAULT_SOP
    wcsv = worker_csv if worker_csv else DEFAULT_CSV
    bid = f"B{uuid.uuid4().hex[:6]}"
    if not (Path(sop_path).exists() and Path(wcsv).exists()):
        return bid, "❌ SOP 或 worker CSV 不存在", "", "", status()
    ctx = pipeline.run(bid, sop_path, wcsv, full=bool(full_mode),
                       resume_from=resume_step if resume_step else None,
                       vision_cache_dir=str(CACHE))
    rep = ctx.get("report",{})
    findings = ctx.get("findings",[])
    rows = [[f.get("step_id"), f.get("result"), f.get("criterion"), f.get("expected"),
             f.get("actual"), f.get("root_cause"), f.get("reference_page")] for f in findings]
    overall = rep.get("overall","?")
    summary = rep.get("worker_summary","")
    detail = rep.get("engineer_detail","")
    trace = json.dumps(rep.get("audit_trace",[])[:8], ensure_ascii=False, indent=2)
    rpath = ctx.get("report_path","")
    return (bid,
            f"{summary}\n\noverall={overall}\n报告: {rpath}",
            rows,
            detail,
            trace,
            status())

with gr.Blocks(title="ShopFloor SOP Agent") as demo:
    gr.Markdown("# ShopFloor SOP Agent — DGX Spark 双模型可恢复闭环\n"
                "Nemotron(文本/工具,:8000) + Step3-VL(图文,:8001，预缓存) | 标准PDF→SOP→工人回传→合规报告")
    with gr.Row():
        with gr.Column():
            sop_in = gr.Textbox(value=DEFAULT_SOP, label="标准 SOP（路径，默认 mock/sop_sample.txt）")
            csv_in = gr.Textbox(value=DEFAULT_CSV, label="工人回传 CSV（路径，默认 mock/worker_batch.csv）")
            full = gr.Checkbox(value=False, label="全流程模式（实时切 Step3-VL，慢，约5分钟切换）")
            resume = gr.Dropdown(choices=[None]+[n for n,_ in pipeline.STEPS], value=None,
                                 label="从某步重跑（回退）")
            run_btn = gr.Button("🚀 快速合规判定", variant="primary")
        with gr.Column():
            status_box = gr.Textbox(label="平台状态", value=status(), lines=4)
            bid_box = gr.Textbox(label="批次ID")
    out_summary = gr.Textbox(label="结果摘要", lines=3)
    out_table = gr.Dataframe(headers=["step","result","criterion","expected","actual","root_cause","ref"],
                             label="合规 findings", interactive=False)
    out_detail = gr.Textbox(label="工程师详版", lines=10)
    out_trace = gr.Code(label="审计 trace（tool calls）", language="json")
    run_btn.click(run_pipeline, [sop_in, csv_in, full, resume],
                  [bid_box, out_summary, out_table, out_detail, out_trace, status_box])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
