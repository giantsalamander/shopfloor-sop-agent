# tolerance-calc

**description**: 计算实测值相对设定值的偏差（绝对值+百分比），按公差判合格区间。

## 何时使用
Validate 步，每条有 setpoint+measured 的记录。

## 输入
- `measured` (float)、`setpoint` (float)、`unit` (str)、`tol_pct` (float, 默认 5.0)

## 输出
```json
{"deviation_value": 12388.0, "deviation_pct": 103233.333, "tolerance_pct": 5.0, "in_tolerance": false, "unit": "mV"}
```

## 实现要点（tools.py: tolerance_calc）
- setpoint=0 时只给绝对偏差；数值非法返回 error 不炸流水线
- 实测战果：12400mV vs 12V 单位错 → 偏差 103233% → FAIL（reports/B9db05c.json）
- 可扩展：CPK/均值/RSD 批量统计（征文展望项）

## 挂载点
pipeline.step_validate → FAIL 判定第二优先级（仪器校验之后）
