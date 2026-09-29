# instrument-validator

**description**: 校验工人所用仪器：是否在资产库、型号/类型是否匹配、量程是否覆盖需求、校准是否在有效期。

## 何时使用
InstrumentCheck 步，对每条工人回传记录逐一校验。

## 输入
- `instrument_sn` (str)：仪器序列号（必填）
- `required_range` (float)、`required_unit` (str)、`required_type` (str)：来自 SOP 图的仪器需求

## 输出
```json
{"valid": false, "reason": "校准过期(2026-08-27)", "cal_expiry": "2026-08-27", "model": "Tek DSO", "type": "oscilloscope"}
```

## 实现要点（tools.py: instrument_validator）
- 数据源 mock/instruments_mock.csv（SN/model/type/range_max/range_unit/cal_expiry）
- 校准有效期与"今天"比较；量程不足、类型不符分别给 reason
- 实测战果：抓到 TSC-DSO-22 校准过期 → FAIL（reports/B9db05c.json）

## 挂载点
pipeline.step_instrument_check → 每条 worker row 挂 _instr_valid，Validate 步判 FAIL 优先级最高
