# sop-graph-builder

**description**: 把抽取的步骤列表合成为有向 SOP 执行图：节点=步骤，边=先后依赖/分支条件，标注安全门。

## 何时使用
SOPPlanner 步，Nemotron 产出步骤 JSON 之后。

## 输入
- `steps_json` (dict)：{"steps":[{"id","title","instrument_required","safety_notes","record_fields"}]}
- `vision_json` (dict, 可选)：视觉补充信息

## 输出
```json
{"nodes":[...], "edges":[{"from":"S1","to":"S2"}], "safety_gates":["S1"]}
```

## 实现要点（tools.py: sop_graph_builder）
- 确定性组装：顺序边 + 安全门识别（有 safety_notes 的节点）
- 模型只产步骤语义，图结构由代码保证合法性（无环、编号连续）

## 挂载点
pipeline.step_sop_planner → ctx["sop_plan"]["graph"]，供 InstrumentCheck/WorkerExecute/Validate 使用
