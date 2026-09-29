"""pydantic 模型：仪器面板识别 / 工人回传 / SOP 步骤图 / 合规报告。
对应交付物②：Step3-VL 识仪器面板 JSON schema（及配套结构）。"""
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

# === 交付物②：Step3-VL 识仪器面板输出 schema ===
class InstrumentPanelReading(BaseModel):
    panel_type: Literal["oscilloscope", "multimeter", "torque_wrench", "thermometer",
                        "pressure_gauge", "calibrator", "other"] = Field(description="仪器类型")
    brand: Optional[str] = None
    model: Optional[str] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = Field(None, description="量程上限")
    range_unit: Optional[str] = None
    setpoint: Optional[float] = Field(None, description="设定值")
    measured: Optional[float] = Field(None, description="屏幕/表盘读数实测值")
    measured_unit: Optional[str] = None
    step_id: Optional[str] = None
    warnings: list[str] = Field(default_factory=list, description="如 over_range, low_battery, cal_expired")
    missing: list[str] = Field(default_factory=list, description="未识别到的必填项")
    bbox: Optional[dict] = Field(None, description="读数区域 bbox {x,y,w,h} 归一化")

INSTRUMENT_PANEL_SCHEMA_HINT = """{
  "panel_type": "oscilloscope|multimeter|torque_wrench|thermometer|pressure_gauge|calibrator|other",
  "brand": "str|null",
  "model": "str|null",
  "range_min": "float|null",
  "range_max": "float|null",
  "range_unit": "str|null",
  "setpoint": "float|null",
  "measured": "float|null (屏幕读数)",
  "measured_unit": "str|null",
  "step_id": "str|null",
  "warnings": ["over_range|low_battery|cal_expired|..."],
  "missing": ["未识别到的字段"],
  "bbox": {"x":0.0,"y":0.0,"w":0.0,"h":0.0}
}"""

# vLLM guided_json 用：token 级强制 JSON，推理模型思考链无法干扰
INSTRUMENT_PANEL_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "panel_type": {"type": "string",
                       "enum": ["oscilloscope", "multimeter", "torque_wrench", "thermometer",
                                "pressure_gauge", "calibrator", "other"]},
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "range_min": {"type": "number"},
        "range_max": {"type": "number"},
        "range_unit": {"type": "string"},
        "setpoint": {"type": "number"},
        "measured": {"type": "number"},
        "measured_unit": {"type": "string"},
        "step_id": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
        "bbox": {"type": "object"},
    },
    "required": ["panel_type", "warnings", "missing"],
    "additionalProperties": False,
}

# === 工人回传 ===
class WorkerFormRow(BaseModel):
    step_id: str
    param_name: str
    setpoint: Optional[float] = None
    measured: Optional[float] = None
    unit: Optional[str] = None
    instrument_sn: Optional[str] = None
    instrument_model: Optional[str] = None
    timestamp: Optional[str] = None
    photo_path: Optional[str] = None

# === SOP 步骤图 ===
class SOPStep(BaseModel):
    id: str
    title: str
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    branch_condition: Optional[str] = None
    instrument_required: Optional[dict] = None  # {type, range, unit, cal_valid}
    safety_notes: list[str] = Field(default_factory=list)
    record_fields: list[str] = Field(default_factory=list)

class SOPGraph(BaseModel):
    batch_id: str
    nodes: list[SOPStep]
    edges: list[dict] = Field(default_factory=list)  # {from, to, condition}
    safety_gates: list[str] = Field(default_factory=list)

# === 合规 ===
class ComplianceFinding(BaseModel):
    step_id: str
    criterion: str = Field(description="标准条款/阈值")
    expected: Optional[str] = None
    actual: Optional[str] = None
    result: Literal["pass", "fail", "marginal"] = "pass"
    reference_page: Optional[str] = None
    bbox: Optional[dict] = None
    root_cause: Optional[str] = None

class ComplianceReport(BaseModel):
    batch_id: str
    overall: Literal["pass", "fail", "marginal"] = "fail"
    findings: list[ComplianceFinding] = Field(default_factory=list)
    worker_summary: str = ""
    engineer_detail: str = ""
    audit_trace: list[dict] = Field(default_factory=list)  # [{step, tool, args, result, ts}]
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
