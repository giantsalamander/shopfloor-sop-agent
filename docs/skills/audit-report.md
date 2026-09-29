# audit-report

**description**: 汇总 findings 与工具调用 trace，生成三版报告：工人简版、工程师详版、审计 trace 版。

## 何时使用
Reporter 步（流水线最后一步）。

## 输入
- `findings` (list)、`tool_trace` (list)、`batch_id` (str)

## 输出
```json
{"overall":"fail","worker_summary":"批次 B9db05c 检查结果：fail。共 4 项，不合格 2 项。",
 "engineer_detail":"- [FAIL] S1: ... 根因 校准过期(2026-08-27); 引用 SOP S1",
 "audit_trace":[{"step":"InstrumentCheck","tool":"instrument_validator","args":{},"result_summary":"...","ts":"..."}]}
```

## 实现要点（tools.py: audit_report）
- overall 汇总规则：有 FAIL → fail；仅 MARGINAL → marginal；全 PASS → pass
- 工程师详版逐条含：结果/条款/期望/实际/根因/引用页
- audit_trace 每条工具调用含参数+结果摘要+时间戳，满足审计回放
- 落盘 reports/<batch_id>.json（schemas.ComplianceReport，pydantic 校验）

## 挂载点
pipeline.step_reporter → reports/*.json + Gradio 三栏展示
