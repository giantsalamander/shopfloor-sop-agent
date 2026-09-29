# nonconformance

**description**: 不合格项分级（critical/major/minor）并给出处置动作与回退建议（重测/隔离/工单/上报）。

## 何时使用
ComplianceJudge 步之后，对每个非 PASS finding。

## 输入
- `finding` (dict)：ComplianceFinding（step_id/result/root_cause/...）

## 输出
```json
{"severity":"critical","action":"隔离+停用仪器+重测","rerun_step":"S1","rerun_phase":"EvidenceParse"}
```

## 实现要点（tools.py: nonconformance）
- 分级规则：校准类根因 → critical；其余 FAIL → major；MARGINAL → minor
- rerun_phase 驱动可恢复回退：EvidenceParse（重识图）或 SOPPlanner（重拆步骤）
- Gradio"从某步重跑"下拉与 rerun_phase 映射

## 挂载点
pipeline.step_compliance_judge → ctx["compliance"]["nonconformance"]，进工程师详版报告
