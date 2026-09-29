# ShopFloor SOP Agent

**基于 NVIDIA DGX Spark 的"标准解析 → 多模态 SOP → 工人回传 → 合规判定 → 可审计报告"可恢复闭环智能体**

> 双本地大模型驱动：NVIDIA Nemotron-3.5-Lightning-30B-A3B-NVFP4（长上下文推理/工具编排）+ 阶跃星辰 Step3-VL-10B（仪器面板/现场图文识别）。
> 全部推理在 DGX Spark（GB10 Grace-Blackwell，128GB 统一内存）本地完成，**数据不出机**。

---

## 1. 作品特点与核心亮点

工厂/实验室的现实痛点：纸质标准改版不同步、工人执行漏步、回传记录靠人工核对、审计无 trace。本作品把 SOP 合规检查做成一条**可恢复的多 Agent 闭环**：

1. **双模型分工，各司其职**
   - **Nemotron 30B-A3B（NVFP4）**：标准条款抽取、SOP 步骤图规划、合规判定、报告生成；1M token 原生上下文（实配 65536），可跨多份标准对齐。
   - **Step3-VL-10B**：仪器面板读数（万用表/扭矩枪/示波器/温度计）、警示符号、现场照片的结构化抽取，输出严格 JSON（读数+单位+量程+bbox+告警）。
2. **统一内存上的双模型调度**：128GB LPDDR5x 装不下两个满载 vLLM 实例 → 设计**互斥切换 + 视觉预缓存**两阶段架构：视觉解析离线批量完成并缓存，在线判定只跑文本模型，演示零切换等待。
3. **不依赖模型原生 tool calling 的稳健编排**：实测 Nemotron 输出伪 XML 工具调用（非结构化 tool_use），故采用 **Python 驱动编排**——模型只产出 JSON 意图，工具由编排器确定性调用，链路 100% 可控、可审计。
4. **推理模型的结构化输出修复**：实测 `guided_json` 对 VLM 无效，改用 `response_format={"type":"json_object"}` token 级强制合法 JSON，视觉字段抽取成功率从 2/4 → **4/4**。
5. **可恢复工作流**：10 步流水线每步落 checkpoint（JSON），失败可从任意步重跑（回退到 SOPPlanner/EvidenceParse 等），支持人工复核后局部重算。
6. **客观评测对齐**：工具规格兼容 **SOP-Bench**（amazon/sop-bench，Bedrock toolSpec 格式）+ OpenAI function 双格式导出；mock 数据覆盖"全合格/单点超差/仪器量程不符/漏步/单位错误"五类批次。

### 实测判定效果（可复现，见 `reports/B9db05c.json`）

| 工人回传 | 系统判定 | 抓到的根因 |
|---|---|---|
| 12.4V（合格） | PASS | — |
| 1250V 用了校准过期的示波器 | **FAIL** | `instrument_validator`：**校准过期(2026-08-27)** |
| 12400 mV（单位错） | **FAIL** | `tolerance_calc`：**偏差 103233% 超公差 5%** |
| 45.0 Nm 扭矩 | PASS | — |

视觉链路 4/4：Step3-VL 正确读出 12.4V / 1250V / 12400mV / 45.0Nm，并在超量程面板上**识别出红色三角告警图标**触发交叉校验 discrepancy。

## 2. 架构设计

```
                 ┌────────────────────────────────────────────────┐
                 │              DGX Spark (GB10, 128GB)           │
                 │                                                │
 标准PDF/图 ────►│  Phase A(离线): Step3-VL :8001                 │
 仪器截图 ──────►│    图→InstrumentPanelReading JSON→vision_cache │
                 │           │ (互斥切换, run-step3vl.sh)         │
                 │           ▼                                    │
 工人回传CSV ───►│  Phase B(在线): Nemotron :8000 (NVFP4)         │
                 │    Ingest→StdParse→SOPPlanner→InstrumentCheck  │
                 │    →WorkerExecute→EvidenceParse(读缓存)        │
                 │    →Validate→ComplianceJudge→Reporter          │
                 │           │ 每步 checkpoint, 可回退            │
                 │           ▼                                    │
                 │    ComplianceReport: 工人简版/工程师详版/审计trace│
                 └────────────────────────────────────────────────┘
        10 个 Agent Skills (tools.py): 确定性 Python 工具, 双格式 spec
        Gradio :7860 ── 上传→判定→报告→"从某步重跑"
```

**为什么这样设计**：
- 视觉是"重、慢、可离线"的（切模型要 4-5 分钟），文本判定是"轻、快、要交互"的 → 两阶段拆分让在线演示只依赖 Nemotron。
- 工具全部确定性 Python（查资产库/算公差/规则匹配），模型只做"理解与决策"，判定结果可复现、可审计——这是合规场景的底线。
- checkpoint 粒度=流水线步骤，回退成本最小化。

## 3. 快速开始

```bash
# 0) 环境: DGX Spark (aarch64, Ubuntu 24.04, CUDA 13.0), Python 3.12
python3 -m venv ~/envs/sop && source ~/envs/sop/bin/activate
pip install -r requirements.txt

# 1) 起 Nemotron (文本模型; 必须登录 shell —— 见"部署说明"flashinfer 陷阱)
~/run-nemotron.sh          # vllm serve ... --max-model-len 65536, :8000

# 2) 造 mock 数据 (仪器面板图/工人CSV/SDS/资产库)
python mock_gen.py

# 3) [可选] 视觉预缓存: 切 Step3-VL 解析面板图 → 自动恢复 Nemotron
~/run-step3vl.sh && python prep_vision.py

# 4) 起 Gradio, 浏览器开 http://<host>:7860
python app.py
# 页面点 "🚀 快速合规判定" → findings 表 + 三版报告 + 审计 trace
```

命令行直跑流水线：`python pipeline.py BATCH01`（用 mock 默认输入）。

## 4. Agent Skills（10 个，详见 `docs/skills/*.md`）

| Skill | 职责 | 类型 |
|---|---|---|
| `std-doc-parse` | 标准文本→条款/阈值/设备/安全要点 | 抽取 |
| `pid-or-wiring-ocr` | P&ID/接线图视觉结果→设备/端口/设定值 | 视觉后处理 |
| `sop-graph-builder` | 条款+视觉→有向步骤图(节点/边/安全门) | 组装 |
| `instrument-validator` | 仪器 SN→型号/量程/校准有效期校验(mock 资产库) | 规则 |
| `worker-form-schema` | SOP 图→工人回传表单模板 | 生成 |
| `photo-evidence-check` | 面板截图读数 vs 表单交叉校验 | 校验 |
| `tolerance-calc` | 偏差%/公差/合格区间计算 | 计算 |
| `regulatory-rule` | SDS→危险类别→闪点→包装组(对齐 SOP-Bench dangerous_goods) | 规则 |
| `nonconformance` | 不合格分级(critical/major/minor)+回退建议 | 决策 |
| `audit-report` | 三版报告(工人/工程师/审计 trace) | 生成 |

每个 skill 同时导出 **OpenAI function spec**（编排器用）与 **Bedrock toolSpec**（SOP-Bench 评测对齐），见 `tools.py` 的 `TOOLS_OPENAI` / `TOOLSPEC_BEDROCK`。

## 5. 技术栈（详见 `docs/03-技术栈.md`）

- **硬件**：NVIDIA DGX Spark（GB10 Grace-Blackwell 超级芯片，20 核 Arm Cortex-X925/A725，128GB LPDDR5x 统一内存）
- **NVIDIA 软件**：CUDA 13.0、驱动 580.142、**vLLM 0.29.0**（FlashInfer attention 后端、Marlin NVFP4 MoE kernel、DeepGEMM）、**NVIDIA ModelOpt**（Nemotron NVFP4 权重量化 + fp8_e4m3 KV cache）
- **NVIDIA 模型**：Nemotron-3.5-Lightning-30B-A3B-NVFP4（NemotronH Mamba-Transformer 混合 MoE，30B 总参/3B 激活，原生 1M 上下文）
- **StepFun 阶跃星辰模型**：Step3-VL-10B（StepVLForConditionalGeneration：ViT 感知编码器 + Qwen3-8B 解码器，bf16，图文多模态）
- **编排/应用**：Python 3.12、Gradio 6、OpenAI SDK、pydantic v2；评测对齐 SOP-Bench（amazon/sop-bench，CC-BY-NC，仅内部评测）

## 6. 目录结构

```
├── app.py               # Gradio 多Agent 主流程 UI
├── pipeline.py          # 10 步可恢复编排 + checkpoint + 模型切换钩子
├── clients.py           # 双模型 OpenAI 客户端 + json_object 强制输出
├── tools.py             # 10 skills: 实现 + OpenAI/Bedrock 双格式 spec
├── schemas.py           # pydantic: 仪器面板/工人回传/SOP图/合规报告
├── mock_gen.py          # mock 数据生成(仪器面板图/CSV/SDS)
├── prep_vision.py       # 离线视觉预缓存(Step3-VL)
├── fix_vision_cache.py  # 视觉JSON修复(json_object 二次抽取)
├── docs/                # 项目说明/部署/技术栈/skills
├── mock/                # 生成的演示数据
├── checkpoints/         # 每批次每步 checkpoint + vision_cache
└── reports/             # 合规报告 JSON(含实测样例 B9db05c.json)
```

## 7. 文档索引

- [项目说明（特点/亮点/技术方案/架构/优化）](docs/01-项目说明.md)
- [部署说明（本地算力部署/大模型优化/Agent Skills 设计）](docs/02-部署说明.md)
- [技术栈说明（NVIDIA SDK 与模型 / StepFun 模型）](docs/03-技术栈.md)
- [Agent Skills 说明（10 个 md）](docs/skills/)

## License / 数据声明

- 代码：MIT（可自行调整）。
- SOP-Bench 数据：CC-BY-NC-4.0，**仅用于内部评测与演示，不再分发**；本项目仓库不包含其数据文件。
- 模型权重：Nemotron 遵循 NVIDIA Open Model License；Step3-VL 遵循 StepFun 相应许可。
