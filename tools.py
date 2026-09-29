"""交付物①：SOP-Bench toolspec 改写的工具清单。
10 个 skill，每个含 OpenAI function 规格 + Bedrock toolSpec + Python 实现。
设计：函数纯确定性（不内嵌模型调用）；视觉/文本抽取由 pipeline 经 clients 调模型后，结果以参数传入这里做后处理/判定。
数据源：mock/instruments_mock.csv（仪器资产）、mock/sds_mock.json（危化品）。"""
from __future__ import annotations
import json, csv, os, statistics
from datetime import datetime, date

_MOCK = os.path.join(os.path.dirname(__file__), "mock")

def _load_instruments() -> dict:
    p = os.path.join(_MOCK, "instruments_mock.csv")
    if not os.path.exists(p): return {}
    out = {}
    with open(p) as f:
        for r in csv.DictReader(f):
            out[r["instrument_sn"]] = r
    return out

def _load_sds() -> dict:
    p = os.path.join(_MOCK, "sds_mock.json")
    if not os.path.exists(p): return {}
    return json.load(open(p))

# ---------------- 10 skills ----------------
def std_doc_parse(sop_text: str) -> dict:
    """轻量确定性抽取（demo）：从 sop.txt 抽阈值/设备/安全要点。"""
    import re
    thresholds = re.findall(r"(\d+\.?\d*)\s*(%|ppm|MPa|kPa|°C|Nm|V|A|Ω|Hz)\b", sop_text or "")
    clauses = [{"id": f"C{i+1}", "text": ln.strip()} for i, ln in enumerate(sop_text.splitlines()) if ln.strip() and len(ln.strip()) > 12][:20]
    return {"clauses": clauses,
            "thresholds": [{"value": v, "unit": u} for v, u in thresholds[:20]],
            "equipment": [w for w in ["万用表", "扭矩枪", "示波器", "温度计", "压力表"] if w in (sop_text or "")],
            "safety": [ln.strip() for ln in (sop_text or "").splitlines() if any(k in ln for k in ["安全", "佩戴", "警示", "PPE"])]}

def pid_or_wiring_ocr(vision_json: dict) -> dict:
    """后处理 Step3-VL 对接线图/P&ID 的输出：归一设备/端口/设定值。"""
    v = vision_json or {}
    return {"devices": v.get("devices", []),
            "ports": v.get("ports", []),
            "setpoints": v.get("setpoints", []),
            "anomalies": v.get("warnings", [])}

def sop_graph_builder(steps_json: dict, vision_json: dict = None) -> dict:
    """把抽取出的步骤+视觉结果合成有向步骤图。"""
    steps = steps_json.get("steps", []) if isinstance(steps_json, dict) else []
    nodes, edges = [], []
    prev = None
    for i, s in enumerate(steps):
        sid = s.get("id", f"S{i+1}")
        nodes.append({"id": sid, "title": s.get("title", f"步骤{i+1}"),
                      "instrument_required": s.get("instrument_required"),
                      "safety_notes": s.get("safety_notes", []),
                      "record_fields": s.get("record_fields", ["measured", "unit", "instrument_sn", "photo"])})
        if prev: edges.append({"from": prev, "to": sid})
        prev = sid
    return {"nodes": nodes, "edges": edges, "safety_gates": [n["id"] for n in nodes if n.get("safety_notes")]}

def instrument_validator(instrument_sn: str, required_range: float = None,
                         required_unit: str = None, required_type: str = None) -> dict:
    """校验仪器型号/量程/校准有效期（查 mock 资产库）。"""
    db = _load_instruments()
    sn = instrument_sn
    rec = db.get(sn)
    if not rec:
        return {"valid": False, "reason": f"仪器 {sn} 不在资产库", "cal_expiry": None}
    reasons = []
    try:
        cal = datetime.fromisoformat(rec["cal_expiry"]).date()
        if cal < date.today():
            reasons.append(f"校准过期({rec['cal_expiry']})")
    except Exception:
        reasons.append("校准日期无效")
    if required_type and rec.get("type", "").lower() != required_type.lower():
        reasons.append(f"类型不符(需{required_type}/实{rec.get('type')})")
    if required_range and required_unit:
        try:
            if float(rec["range_max"]) < float(required_range):
                reasons.append(f"量程不足(需≥{required_range}{required_unit}/实≤{rec['range_max']}{rec.get('range_unit')})")
        except Exception: pass
    return {"valid": not reasons, "reason": "; ".join(reasons) if reasons else "OK",
            "cal_expiry": rec.get("cal_expiry"), "model": rec.get("model"), "type": rec.get("type")}

def worker_form_schema(sop_graph: dict) -> dict:
    """由 SOP 图生成工人回传模板。"""
    rows = []
    for n in sop_graph.get("nodes", []):
        for fld in n.get("record_fields", ["measured", "unit"]):
            rows.append({"step_id": n["id"], "param_name": fld, "setpoint": None,
                         "measured": None, "unit": None, "instrument_sn": None,
                         "instrument_model": None, "timestamp": None, "photo_path": None})
    return {"form_rows": rows}

def photo_evidence_check(vision_json: dict, expected_unit: str = None,
                         expected_step: str = None) -> dict:
    """交叉校验工人上传的仪器截图与表单。"""
    v = vision_json or {}
    disc = []
    if v.get("missing"): disc.append(f"未识别字段: {v['missing']}")
    if v.get("warnings"): disc.append(f"面板告警: {v['warnings']}")
    if expected_unit and v.get("measured_unit") and v["measured_unit"].lower() != expected_unit.lower():
        disc.append(f"单位不符(需{expected_unit}/实{v['measured_unit']})")
    return {"match": not disc, "discrepancies": disc,
            "measured": v.get("measured"), "unit": v.get("measured_unit")}

def tolerance_calc(measured: float, setpoint: float, unit: str = None,
                   tol_pct: float = 5.0) -> dict:
    """算偏差%与合格区间。"""
    try:
        m, s, t = float(measured), float(setpoint), float(tol_pct)
    except Exception:
        return {"in_tolerance": False, "error": "数值无效"}
    if s == 0:
        dev_abs = m - s; dev_pct = None
    else:
        dev_abs = m - s; dev_pct = round(dev_abs / abs(s) * 100, 3)
    in_tol = dev_pct is not None and abs(dev_pct) <= t
    return {"deviation_value": round(dev_abs, 4), "deviation_pct": dev_pct,
            "tolerance_pct": t, "in_tolerance": in_tol, "unit": unit}

# 危化规则（demo）：危险类→包装组映射
_DG_RULES = {"3": "II", "8": "II", "4.1": "III", "5.1": "II", "6.1": "II", "9": "III"}
def regulatory_rule(product_id: str, flash_point_c: float = None,
                    hazard_class: str = None) -> dict:
    """SDS→危险类→闪点→包装组规则匹配（对齐 SOP-Bench dangerous_goods 思路）。"""
    sds = _load_sds()
    rec = sds.get(product_id, {})
    hc = hazard_class or rec.get("hazard_class")
    fp = flash_point_c if flash_point_c is not None else rec.get("flash_point_c")
    packing = _DG_RULES.get(str(hc), "III" if (fp is not None and fp > 60) else "II")
    compliant = True; notes = []
    if fp is not None and fp < 23: notes.append("闪点<23°C，II 类包装，禁空运客机")
    if hc in ["3", "5.1", "6.1"] and fp is not None and fp < 23: compliant = False; notes.append("需隔离装运")
    return {"product_id": product_id, "hazard_class": hc, "flash_point_c": fp,
            "packing_group": packing, "compliant": compliant, "notes": notes}

def nonconformance(finding: dict) -> dict:
    """不合格分级 + 复测/工单/回退到哪步。"""
    sev = "critical" if finding.get("result") == "fail" and "校准" in (finding.get("root_cause") or "") else \
          "major" if finding.get("result") == "fail" else "minor"
    action = {"critical": "隔离+停用仪器+重测", "major": "复测该步骤", "minor": "记录备案"}.get(sev)
    return {"severity": sev, "action": action,
            "rerun_step": finding.get("step_id"),
            "rerun_phase": "EvidenceParse" if "校准" in (finding.get("root_cause") or "") or "量程" in (finding.get("root_cause") or "") else "SOPPlanner"}

def audit_report(findings: list, tool_trace: list, batch_id: str = "B?") -> dict:
    """生成三版报告：工人简版/工程师详版/审计 trace。"""
    fails = [f for f in findings if f.get("result") == "fail"]
    overall = "fail" if fails else ("marginal" if any(f.get("result")=="marginal" for f in findings) else "pass")
    worker = f"批次 {batch_id} 检查结果：{overall}。共 {len(findings)} 项，不合格 {len(fails)} 项。"
    eng = "\n".join(f"- [{f.get('result').upper()}] {f.get('step_id')}: {f.get('criterion')} "
                    f"(期望 {f.get('expected')} / 实际 {f.get('actual')}; 根因 {f.get('root_cause')}; 引用 {f.get('reference_page')})"
                    for f in findings)
    trace = [{"step": t.get("step"), "tool": t.get("tool"), "args": t.get("args"),
              "result_summary": str(t.get("result"))[:200], "ts": t.get("ts")} for t in tool_trace]
    return {"overall": overall, "worker_summary": worker, "engineer_detail": eng,
            "audit_trace": trace, "findings_count": len(findings), "fail_count": len(fails)}

# ---------------- 规格：OpenAI function + Bedrock toolSpec ----------------
TOOLS_OPENAI = [
    {"type": "function", "function": {
        "name": "instrument_validator", "description": "校验仪器型号/量程/校准有效期",
        "parameters": {"type":"object","properties":{
            "instrument_sn":{"type":"string"},"required_range":{"type":"number"},
            "required_unit":{"type":"string"},"required_type":{"type":"string"}},
            "required":["instrument_sn"]}}},
    {"type": "function", "function": {
        "name": "tolerance_calc", "description": "计算偏差百分比与合格判定",
        "parameters": {"type":"object","properties":{
            "measured":{"type":"number"},"setpoint":{"type":"number"},
            "unit":{"type":"string"},"tol_pct":{"type":"number","default":5.0}},
            "required":["measured","setpoint"]}}},
    {"type": "function", "function": {
        "name": "regulatory_rule", "description": "危化品 SDS→危险类→闪点→包装组合规判定",
        "parameters": {"type":"object","properties":{
            "product_id":{"type":"string"},"flash_point_c":{"type":"number"},
            "hazard_class":{"type":"string"}}, "required":["product_id"]}}},
    {"type": "function", "function": {
        "name": "photo_evidence_check", "description": "交叉校验仪器截图读数与表单",
        "parameters": {"type":"object","properties":{
            "vision_json":{"type":"object"},"expected_unit":{"type":"string"},
            "expected_step":{"type":"string"}}, "required":["vision_json"]}}},
    {"type": "function", "function": {
        "name": "nonconformance", "description": "不合格分级与回退建议",
        "parameters": {"type":"object","properties":{"finding":{"type":"object"}},
            "required":["finding"]}}},
]

# Bedrock toolSpec（对齐 SOP-Bench 评测）
TOOLSPEC_BEDROCK = [
    {"toolSpec": {"name": t["function"]["name"], "description": t["function"]["description"],
                  "inputSchema": {"json": t["function"]["parameters"]}}}
    for t in TOOLS_OPENAI
]

_DISPATCH = {
    "std_doc_parse": std_doc_parse, "pid_or_wiring_ocr": pid_or_wiring_ocr,
    "sop_graph_builder": sop_graph_builder, "instrument_validator": instrument_validator,
    "worker_form_schema": worker_form_schema, "photo_evidence_check": photo_evidence_check,
    "tolerance_calc": tolerance_calc, "regulatory_rule": regulatory_rule,
    "nonconformance": nonconformance, "audit_report": audit_report,
}

def call_tool(name: str, **kwargs) -> dict:
    """编排器调工具的统一入口。"""
    fn = _DISPATCH.get(name)
    if not fn: return {"error": f"unknown tool {name}"}
    try:
        return fn(**kwargs)
    except Exception as e:
        return {"error": f"{name}: {e}"}

if __name__ == "__main__":
    print(json.dumps(TOOLSPEC_BEDROCK, ensure_ascii=False, indent=2)[:600])
