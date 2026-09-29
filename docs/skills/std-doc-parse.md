# std-doc-parse

**description**: 解析标准/SOP 文档文本，抽取可执行条款、数值阈值、涉及设备与安全要点。

## 何时使用
流水线 StdParse 步；输入为标准全文（sop.txt / PDF 转文本）。

## 输入
- `sop_text` (str)：标准文档全文

## 输出
```json
{"clauses":[{"id":"C1","text":"..."}], "thresholds":[{"value":"12","unit":"V"}],
 "equipment":["万用表"], "safety":["操作前佩戴绝缘手套"]}
```

## 实现要点（tools.py: std_doc_parse）
- 确定性抽取：正则抓"数值+单位"阈值（%/ppm/MPa/kPa/°C/Nm/V/A/Ω/Hz）
- 条款按行切分（长度>12 的行），编号 C1..Cn
- 设备/安全要点关键词匹配
- 深度解析（跨页对齐、表格重建）由 Nemotron 在 SOPPlanner 步补充

## 挂载点
pipeline.step_std_parse → 输出进 ctx["std_parse"]，供 SOPPlanner 使用
