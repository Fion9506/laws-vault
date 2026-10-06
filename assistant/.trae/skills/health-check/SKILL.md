---
name: health-check
description: 检查法规库配置健康度与优化空间：语料完整性、元数据质量、git 状态、规则/技能齐全、MCP 存活、更新时效。触发词：检查配置、体检、健康检查、优化建议、库状态。
---

# 配置检查与优化空间技能

## 执行体检

```bash
python scripts/health_check.py
```

脚本输出：各层文件数、待核/缺文号计数、manifest 一致性、未提交变更数、规则与技能齐全性、flk-mcp 端口探活、SILICONFLOW_API_KEY 状态、lawtext 最后同步日、checked_at 陈旧度。

## 解读规则（把脚本输出转成结论给用户）

1. **阻断项**（必须处理）：层文件数与 manifest 不一致；project_rules.md 缺失；未提交变更 >0 且含语料目录。
2. **质量项**（建议处理）：待核 status 数量（>10 → 建议用 flk-mcp 或官方源批量核验后固化 overrides.json）；cas/casi 层缺 doc_number 的文件（逐个补）。
3. **优化空间**（按收益排序呈现）：
   - `policy/` 为空 → 公司执行办法未入库（分层引用需要它）
   - SILICONFLOW_API_KEY 未设 → local-rag 语义检索未接线（口语化长问题召回增强）
   - lawtext 距上次同步 >7 天 → 建议 `git -C tax/lawtext pull`
   - checked_at 超 14 天的文件占比高 → 该跑 vault-update 技能
   - 监管指引层（证监会 监管规则适用指引·会计类）未接入 → 在 fetch_maodocs.py 的 LAYERS 加 securities/garr 条目即可扩层
   - 回归集 <50 条 → 持续用日常真实案例扩充 tests/regression/

## 报告模板

```
## 体检结果（YYYY-MM-DD）
✅ 通过项：…
⚠️ 质量项：…
❌ 阻断项：…（无则写"无"）
## 优化空间（按优先级）
1. …（收益 + 一句话做法）
```
