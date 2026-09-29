"""交付物④ 核心：10 步可恢复多Agent编排。
Ingest→StdParse→SOPPlanner→InstrumentCheck→WorkerExecute→EvidenceParse→Validate→ComplianceJudge→Reporter→HumanReview
每步写 checkpoints/<batch_id>/<step>.json；run_from(batch_id, step) 可从指定步重跑。
快速模式：视觉走 vision_cache（prep_vision.py 预缓存），现场只跑 Nemotron，不切换。
全流程模式：EvidenceParse/StdParse 触发 ~/run-step3vl.sh 切换，其余 ~/run-nemotron.sh。
ctx 用语义键合并：每步 out 用后续可读的语义键，run 循环 ctx.update(out)。"""
from __future__ import annotations
import os, json, csv, subprocess, uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CKPT = ROOT / "checkpoints"
MOCK = ROOT / "mock"
import sys; sys.path.insert(0, str(ROOT))
import tools, schemas
from clients import nemotron_json, step3vl_image_json, ping
from schemas import INSTRUMENT_PANEL_SCHEMA_HINT

def _ts(): return datetime.now().isoformat(timespec="seconds")
def ensure_nemotron():
    if ping().get("nemotron","").startswith("up"): return "nemotron already up"
    subprocess.run(["bash","-lc",str(Path.home()/"run-nemotron.sh")], check=False); return "switched to nemotron"
def ensure_step3vl():
    if ping().get("step3vl","").startswith("up"): return "step3vl already up"
    subprocess.run(["bash","-lc",str(Path.home()/"run-step3vl.sh")], check=False); return "switched to step3vl"

def _ck(b, s): return CKPT/b/f"{s}.json"
def _save(b, s, d): p=_ck(b,s); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def _load(b, s):
    p=_ck(b,s); return json.loads(p.read_text()) if p.exists() else None

def step_ingest(ctx, b, sop_path, worker_csv_path):
    sop = Path(sop_path).read_text() if sop_path else ""
    rows = list(csv.DictReader(open(worker_csv_path))) if worker_csv_path else []
    return {"sop_text": sop, "worker_rows": rows}

def step_std_parse(ctx, b, full=False):
    out = tools.std_doc_parse(ctx["sop_text"])
    if full: ensure_step3vl()
    return {"std_parse": out}

def step_sop_planner(ctx, b):
    ensure_nemotron()
    sp = ctx["std_parse"]
    sys_prompt = ("你是 SOP 工程师。把标准拆成工人可执行步骤。"
                  "输出严格 JSON: {steps:[{id,title,instrument_required:{type,range,unit},setpoint,tol_pct,safety_notes:[],record_fields:[]}]}")
    user = f"标准条款: {json.dumps(sp['clauses'], ensure_ascii=False)}\n阈值: {sp['thresholds']}\n设备: {sp['equipment']}"
    out = nemotron_json(sys_prompt, user)
    steps = out.get("steps", []) if isinstance(out, dict) else []
    graph = tools.sop_graph_builder({"steps": steps})
    return {"sop_plan": {"graph": graph, "raw_plan": out}}

def step_instrument_check(ctx, b):
    ensure_nemotron()
    rows = ctx["worker_rows"]
    req = {n["id"]: (n.get("instrument_required") or {}) for n in ctx["sop_plan"]["graph"]["nodes"]}
    trace=[]
    for r in rows:
        ir = req.get(r["step_id"], {})
        res = tools.call_tool("instrument_validator", instrument_sn=r["instrument_sn"],
                              required_range=ir.get("range"), required_unit=ir.get("unit"), required_type=ir.get("type"))
        trace.append({"step":"InstrumentCheck","tool":"instrument_validator","args":{"sn":r["instrument_sn"],"req":ir},"result":res,"ts":_ts()})
        r["_instr_valid"] = res
    return {"worker_rows": rows, "instr_trace": trace}

def step_worker_execute(ctx, b):
    return {"form": tools.worker_form_schema(ctx["sop_plan"]["graph"])}

def step_evidence_parse(ctx, b, full=False, vision_cache_dir=None):
    rows = ctx["worker_rows"]; out={}
    if full:
        ensure_step3vl()
        for r in rows:
            p = Path(MOCK)/r["photo_path"] if r.get("photo_path") else None
            if p and p.exists(): out[r["photo_path"]] = step3vl_image_json(str(p), INSTRUMENT_PANEL_SCHEMA_HINT)
    else:
        cd = Path(vision_cache_dir or (CKPT/"vision_cache"))
        for r in rows:
            photo = r.get("photo_path")
            cp = cd/(Path(photo).stem+".json") if photo else None
            if cp and cp.exists(): out[photo] = json.loads(cp.read_text())
    return {"evidence": {"vision": out}}

def step_validate(ctx, b):
    ensure_nemotron()
    trace = list(ctx.get("instr_trace", []))
    findings = []
    spec = {n["id"]: n for n in ctx["sop_plan"]["graph"]["nodes"]}
    for r in ctx["worker_rows"]:
        sid = r["step_id"]; sp = spec.get(sid, {})
        setpoint = r.get("setpoint") or sp.get("setpoint"); tol = sp.get("tol_pct", 5.0)
        try: meas = float(r["measured"])
        except: meas = None
        if meas is not None and setpoint is not None:
            tc = tools.call_tool("tolerance_calc", measured=meas, setpoint=float(setpoint), unit=r.get("unit"), tol_pct=tol)
            trace.append({"step":"Validate","tool":"tolerance_calc","args":{"measured":meas,"setpoint":setpoint},"result":tc,"ts":_ts()})
        else: tc = {"in_tolerance": None}
        vj = ctx["evidence"]["vision"].get(r.get("photo_path"), {})
        pec = tools.call_tool("photo_evidence_check", vision_json=vj, expected_unit=r.get("unit"), expected_step=sid)
        trace.append({"step":"Validate","tool":"photo_evidence_check","args":{"photo":r.get("photo_path")},"result":pec,"ts":_ts()})
        iv = r.get("_instr_valid", {})
        if iv and not iv.get("valid"): result, root = "fail", iv.get("reason")
        elif tc.get("in_tolerance") is False: result, root = "fail", f"偏差{tc.get('deviation_pct')}%超公差{tol}%"
        elif tc.get("in_tolerance") is None: result, root = "marginal", "数据缺失"
        elif not pec.get("match"): result, root = "marginal", "; ".join(pec.get("discrepancies",[]))
        else: result, root = "pass", None
        findings.append({"step_id":sid,"criterion":f"{r['param_name']}={setpoint}{r.get('unit','')}±{tol}%",
                         "expected":setpoint,"actual":r.get("measured"),"result":result,
                         "reference_page":f"SOP {sid}","bbox":vj.get("bbox"),"root_cause":root})
    return {"findings": findings, "validate_trace": trace}

def step_compliance_judge(ctx, b):
    ensure_nemotron()
    findings = ctx["findings"]
    sys_prompt = ("你是合规判定官。逐条比对标准条款，给 pass/fail/marginal 与根因，引用条款页码。"
                  "输出严格 JSON: {findings:[{step_id,result,root_cause,reference_page}]}")
    judged = nemotron_json(sys_prompt, f"当前 findings:\n{json.dumps(findings, ensure_ascii=False)}")
    if isinstance(judged, dict) and judged.get("findings"):
        for f, j in zip(findings, judged["findings"]):
            if j.get("result"): f["result"] = j["result"]
            if j.get("root_cause"): f["root_cause"] = j["root_cause"]
            if j.get("reference_page"): f["reference_page"] = j["reference_page"]
    nc = [tools.call_tool("nonconformance", finding=f) for f in findings if f["result"] != "pass"]
    return {"findings": findings, "compliance": {"nonconformance": nc, "judge_raw": judged}}

def step_reporter(ctx, b):
    findings = ctx["findings"]
    trace = ctx.get("validate_trace", [])
    rep = tools.call_tool("audit_report", findings=findings, tool_trace=trace, batch_id=b)
    report = schemas.ComplianceReport(batch_id=b, overall=rep["overall"],
        findings=[schemas.ComplianceFinding(**f) for f in findings],
        worker_summary=rep["worker_summary"], engineer_detail=rep["engineer_detail"], audit_trace=trace)
    (ROOT/"reports").mkdir(exist_ok=True)
    rp = ROOT/"reports"/f"{b}.json"; rp.write_text(report.model_dump_json(indent=2))
    return {"report": report.model_dump(), "report_path": str(rp)}

STEPS = [("ingest", step_ingest),("std_parse", step_std_parse),("sop_planner", step_sop_planner),
         ("instrument_check", step_instrument_check),("worker_execute", step_worker_execute),
         ("evidence_parse", step_evidence_parse),("validate", step_validate),
         ("compliance_judge", step_compliance_judge),("reporter", step_reporter)]

def run(batch_id, sop_path, worker_csv_path, full=False, resume_from=None, vision_cache_dir=None):
    ctx = {}; start = 0
    if resume_from:
        names=[n for n,_ in STEPS]; start = names.index(resume_from) if resume_from in names else 0
        for n,_ in STEPS[:start]:
            d=_load(batch_id,n)
            if d: ctx.update(d)
    all_trace=[]
    for i,(name,fn) in enumerate(STEPS):
        if i<start: continue
        if name=="ingest": out=fn(ctx,batch_id,sop_path,worker_csv_path)
        elif name=="std_parse": out=fn(ctx,batch_id,full=full)
        elif name=="evidence_parse": out=fn(ctx,batch_id,full=full,vision_cache_dir=vision_cache_dir)
        else: out=fn(ctx,batch_id)
        ctx.update(out)
        if isinstance(out,dict):
            for k in ("instr_trace","validate_trace"):
                if k in out: all_trace.extend(out[k])
        _save(batch_id,name,out)
    ctx["_all_trace"]=all_trace; _save(batch_id,"_final",ctx)
    return ctx

if __name__ == "__main__":
    import sys
    bid = sys.argv[1] if len(sys.argv)>1 else f"B{uuid.uuid4().hex[:6]}"
    print("ping:", ping())
    ctx = run(bid, str(MOCK/"sop_sample.txt"), str(MOCK/"worker_batch.csv"), full=False)
    rep = ctx.get("report",{})
    print("overall:", rep.get("overall"))
    print("findings:", len(ctx.get("findings",[])), "fails:", sum(1 for f in ctx.get("findings",[]) if f["result"]=="fail"))
    print("report:", ctx.get("report_path"))
