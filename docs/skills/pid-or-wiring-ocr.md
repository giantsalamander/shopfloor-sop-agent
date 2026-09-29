# pid-or-wiring-ocr

**description**: 把 Step3-VL 对 P&ID/接线图/仪器面板的视觉输出归一化为设备、端口、设定值清单。

## 何时使用
StdParse/EvidenceParse 步处理接线图、P&ID 缩略图、仪器面板截图之后。

## 输入
- `vision_json` (dict)：Step3-VL 结构化输出（InstrumentPanelReading 或自由 schema）

## 输出
```json
{"devices":[], "ports":[], "setpoints":[], "anomalies":["red triangle icon"]}
```

## 实现要点（tools.py: pid_or_wiring_ocr）
- 纯后处理：归一字段名、把 warnings 映射为 anomalies
- 视觉抽取本身由 clients.step3vl_image_json 完成（response_format json_object 强制 JSON）

## 挂载点
pipeline.step_std_parse / step_evidence_parse 的视觉结果规范化
