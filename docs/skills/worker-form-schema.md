# worker-form-schema

**description**: 由 SOP 执行图生成工人回传表单模板（每步该填什么字段）。

## 何时使用
WorkerExecute 步；也用于前端给工人下发采集模板。

## 输入
- `sop_graph` (dict)：sop-graph-builder 的输出

## 输出
```json
{"form_rows":[{"step_id":"S1","param_name":"measured","setpoint":null,"unit":null,"instrument_sn":null,"photo_path":null}]}
```

## 实现要点（tools.py: worker_form_schema）
- 按节点 record_fields 展开成行；字段集与 schemas.WorkerFormRow 对齐
- 保证回传数据结构统一，Validate 步可机器处理

## 挂载点
pipeline.step_worker_execute → ctx["form"]（Gradio 可展示给"工人侧"）
