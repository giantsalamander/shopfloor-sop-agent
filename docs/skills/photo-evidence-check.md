# photo-evidence-check

**description**: 用 Step3-VL 解析的仪器面板截图与工人表单交叉校验：读数、单位、面板告警、缺失字段。

## 何时使用
Validate 步，对每条带照片的回传记录。

## 输入
- `vision_json` (dict)：InstrumentPanelReading（来自 vision_cache 或实时 Step3-VL）
- `expected_unit` (str)、`expected_step` (str)：表单声称的单位/步骤

## 输出
```json
{"match": false, "discrepancies": ["单位不符(需V/实mV)", "面板告警: ['red triangle icon']"], "measured": 1250, "unit": "V"}
```

## 实现要点（tools.py: photo_evidence_check）
- 三类校验：missing 字段、warnings 告警、单位一致性
- 实测战果：panel_overrange 的红色三角告警被 Step3-VL 识别并触发 discrepancy（SMOKE5）
- 视觉数据经 prep_vision.py 预缓存（response_format json_object，4/4 抽取成功）

## 挂载点
pipeline.step_validate → finding 的 MARGINAL/FAIL 证据来源之一，bbox 进报告
