# 080 · 整合 Demo 与提交物料收束 · 执行复盘

- 状态：implemented（待总指挥核查；Codex 不自行宣布 verified）
- 日期：2026-06-20
- 执行方：Codex
- 对应计划：`../plans/080-整合Demo与提交物料收束-计划.md`

## 一句话结论

M080 已把 A-v2 排序、B-lite 证据矩阵、M050 真实出处、M070 研究空白整合为单命令 offline Web Demo，并收束提交物料；承重校验显示整合可运行、忠实呈现零伪造，提交材料指标均挂 verified 来源。

## 实际 diff / 文件列表

### 新增整合层

- `src/scholarloop/demo/AGENTS.md`
- `src/scholarloop/demo/__init__.py`
- `src/scholarloop/demo/assemble.py`
- `src/scholarloop/demo/render.py`
- `src/scholarloop/demo/app.py`
- `src/scholarloop/demo/verify.py`

### 新增提交物料

- `docs/submission/AGENTS.md`
- `docs/submission/01-作品简介.md`
- `docs/submission/02-项目文档.md`
- `docs/submission/03-视频脚本与演示走查.md`
- `docs/submission/04-指标汇总表.md`
- `docs/submission/05-复现说明.md`
- `docs/submission/06-创新叙事.md`
- `docs/submission/07-数据源与许可.md`
- `docs/submission/08-主张溯源清单.md`

### 新增测试与报告

- `tests/test_m080_demo.py`
- `reports/m080/fidelity_audit.json`
- `reports/m080/smoke.txt`
- `reports/m080/pytest.txt`
- `reports/m080/secret_scan.json`
- `reports/m080/submission_identity_scan.json`
- `reports/m080/upstream_hashes.json`
- `reports/m080/validation_summary.json`（最终收束后生成）

### 状态推进

- `docs/dev/plans/080-整合Demo与提交物料收束-计划.md`：`approved → implemented`

## 验收逐项判定

| 验收项 | 判定 | 证据 |
| --- | --- | --- |
| 整合可运行 | PASS | `reports/m080/smoke.txt`：`/healthz`、`/api/queries`、`/api/metrics`、`/api/gaps`、查询 API、HTML repeat 均 200 |
| 四层/五面板可见 | PASS | HTML 包含查询拆解、A-v2 排序、B-lite 证据矩阵、真实连接器富化、研究空白发现 |
| 忠实呈现零伪造 | PASS | `reports/m080/fidelity_audit.json`：fabrication=`0`、out_of_pool=`0`、failures=`[]` |
| 提交物料完备 | PASS | `docs/submission/**` 8 个文件，覆盖简介/文档/视频脚本/指标/复现/创新/许可/溯源 |
| 零夸大可溯源 | PASS | `docs/submission/08-主张溯源清单.md`；所有指标引用 `reports/m040|m060|m070|m080` |
| 零身份信息 | PASS | `reports/m080/submission_identity_scan.json`：命中 0 |
| 密钥不落盘 | PASS | `reports/m080/secret_scan.json`：regex/exact 命中 0 |
| 上游冻结 | PASS | `reports/m080/upstream_hashes.json`：验证过程中 M010–M070 与 M030 web hash 未变 |
| 全量测试 | PASS | `reports/m080/pytest.txt`：`33 passed in 55.63s` |

## M080 承重证据

- 单命令：`PYTHONPATH=src python -m scholarloop.demo.app --host 127.0.0.1 --port 8766`
- Demo 模式：offline、0 LLM 调用、只读 verified JSON。
- 忠实校验覆盖：
  - 30 个查询；
  - 600 行 A-v2 top20 排序；
  - 90 张 M020 证据卡；
  - 90 张 M050 enriched replay 卡；
  - 50 条 M070 gap items；
  - 16 个缺失字段占位检查。

## 全路线七承重墙总账

| 模块 | 承重墙 | 证据 |
| --- | --- | --- |
| M010 | A 主干在 LitSearch 上优于基础基线，H5 0 虚构，可复现 | `reports/m010/results.json`、决策日志 M010 终验记录 |
| M020 | B-lite 证据矩阵字段可追溯，未提供作者/年份/DOI 时只标需人工核验 | `reports/m020/evidence/*.json`、`reports/m020/verification.json` |
| M030 | Web 基线单命令可运行，页面忠实呈现 M020，offline 0-LLM | `reports/m030/web-verification.json` |
| M040 | A-v2 在 LitSearch 上显著优于 BM25 / A-v1，冻结配置为 bge-small-en-v1.5 + cross-encoder | `reports/m040/results.json` |
| M050 | 真实开放学术 API 连接器富化作者/年份/DOI，未解析不补写，离线 replay 可用 | `reports/m050/enriched_replay/*.json`、`reports/m050/data-sources.md` |
| M060 | A-v2 冻结配置在 RealScholarQuery 上零样本泛化，F1 显著优于 BM25 | `reports/m060/results.json`、`reports/m060/significance.json` |
| M070 | 研究空白发现具预测性承重：组合空白填补率显著高于随机概念对，叙述越界 id=0 | `reports/m070/results.json`、`reports/m070/significance.json` |
| M080 | 收束承重：整合可运行 + 忠实呈现零伪造 + 提交物料零夸大可溯源 | `reports/m080/fidelity_audit.json`、`docs/submission/**` |

## 携带项处理

1. **BGE 措辞**：提交文档统一写实测 `BAAI/bge-small-en-v1.5`，不写 BGE-base。
2. **M040 cross-encoder 边际**：如实写为 LitSearch F1 边际约 `0.003137`、NDCG@20 边际约 `0.020425`；不夸大为主要 F1 来源。
3. **M070 频率混杂**：主张精确限定为“高活跃·零历史共现组合空白填补率显著高于随机概念对”；频率配平消融未作为本轮必做项。
4. **M060 cross-encoder 第二基准**：如实标注第二基准未把 cross-encoder 单独作为消融承重。
5. **M050 UA 邮箱**：提交物料只写 `mailto:<redacted>`，不展示真实联系邮箱。

## 偏差与未决项

- 官方“项目文档标准模板”未在仓库出现；本轮按强模板覆盖官方 §3/§4 全要点，后续若官方发布模板，可把现有章节映射进模板。
- M080 不新增 F1 承重墙、不重跑排序评测；所有指标为 verified 引用。
- Demo 使用 stdlib HTTP server 与轻量 HTML，未引入重前端框架；视觉不作为承重。

## 结论

M080 已达到 implemented：整合层可运行，忠实校验与全量测试通过，提交物料无密钥/无身份信息/无超 verified 主张。等待总指挥用新鲜上下文做第十三次初查。

