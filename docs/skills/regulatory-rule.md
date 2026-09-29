# regulatory-rule

**description**: 危化品合规规则链：SDS → 危险类别 → 闪点 → 包装组，并给运输限制提示。

## 何时使用
危化品收货场景的 Validate 步；对齐 SOP-Bench dangerous_goods 子集思路。

## 输入
- `product_id` (str, 格式 P_XXXXX)
- `flash_point_c` (float, 可选)、`hazard_class` (str, 可选)——缺省从 mock/sds_mock.json 查

## 输出
```json
{"product_id":"P_00001","hazard_class":"3","flash_point_c":13.0,"packing_group":"II","compliant":false,"notes":["闪点<23°C，II 类包装，禁空运客机","需隔离装运"]}
```

## 实现要点（tools.py: regulatory_rule）
- 危险类→包装组映射表 _DG_RULES（demo 级；生产应接真实法规库）
- 闪点<23°C 触发 II 类包装与空运限制；3/5.1/6.1 类低闪点判不合规
- mock SDS：乙醇(3类,13°C)/氢氧化钠(8类)/硝酸钠(5.1类)/锂电池(9类)

## 挂载点
pipeline Validate 步（危化品批次）；SOP-Bench 评测对齐导出 Bedrock toolSpec
