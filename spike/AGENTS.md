# AGENTS.md

> 最后核对：2026-06-18

## 命令
- 运行 T1 数据源核验：`python spike/eval/run_spikes.py --stage t1`
- 运行 T2a 无 LLM 评测：`python spike/eval/run_spikes.py --stage t2a`
- 预检 rev2 LLM 端点：`python spike/eval/run_spikes.py --stage precheck-rev2-llm`
- 运行 T2b LLM 基线 + A-min（需 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`）：`python spike/eval/run_spikes.py --stage t2b`
- 运行 T5 C-lite 三臂消融（需同上 LLM env；优先复用 raw 缓存）：`python spike/eval/run_spikes.py --stage t5`
- 汇总写 040 结论：`python spike/eval/run_spikes.py --stage t6`
- 运行 rev2 全流程（T2b→T5→T6）：`python spike/eval/run_spikes.py --stage rev2-full`
- 运行旧 all 流程（需有效 OpenAI API key）：`python spike/eval/run_spikes.py --stage all`

## 测试
- spike 脚本必须能重复运行；原始 API 响应保存在 `spike/raw/`。
- 评测结果以 `spike/eval/results_*.csv/json` 为证据。

## 项目结构
- `raw/`：外部文档、数据集、API 原始响应。
- `eval/`：可复现脚本、查询/候选池、结果表。
- `reports/`：中间审计记录与停机证据。

## 代码风格
- 小脚本、显式错误处理、固定随机种子、不得硬编码密钥。

## Git 流程
- 同根目录：当前非 git 仓库，变更直接落盘。

## 边界与 Gotchas
- 本目录只放 005 验证桩小样本探针产物，可丢弃。
- 不得被后续业务实现直接依赖；验证桩 PASS 前不得搭半成品系统。
- 真实失败和 API 限制必须原样记录，不得改写为成功。
