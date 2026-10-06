---
name: vault-update
description: 更新法规资料库（MaoDocs 准则五层 + lawtext 税法法律层）。哨兵查新 → 人工确认 → 重抓 → git 归档。触发词：更新法规库、法规更新、查新、资料库更新、更新库。
---

# 法规库更新技能

收到触发词后严格按流程执行，不得跳步、不得臆造结果。

## 第 1 步：MaoDocs 五层查新（准则/指南/解释/案例/问答）

```bash
python scripts/update_check.py
```

- `[CLEAN] 无变更` → 该源无更新，进入第 2 步（若括号附带「N/M 页不可达未核验」，提醒用户下次补查）。
- `[UNREACHABLE] …页全部不可达` → 网络故障，本次判定**无效**：不得当作无更新，应提示用户检查网络后重跑本步。
- `[PENDING] 新增 N / 变更 M` → 打开 `changelog/pending-YYYYMMDD.md`，进入第 3 步人工审核。

## 第 2 步：税法/法律层更新（lawtext 镜像，每周六官方 Actions 自动同步）

```bash
git -C tax/lawtext pull --ff-only
git -C tax/lawtext log --oneline -5
git -C tax/lawtext diff --name-only HEAD~1   # 定位新增/修改文件
```

## 第 3 步：人工确认（强制，禁止跳过）

把待审清单按此格式呈现给用户逐条确认：

```
| 文件 | 变更 | 建议 status | 待确认点 |
```

确认后：
1. 重抓涉及层：`python scripts/fetch_maodocs.py --layers <层名>`
2. 用户核实的元数据（文号/生效日/时效）固化进 `scripts/overrides.json`
3. 旧版文件改 status + 填 superseded_by，**不删除旧文件**

## 第 4 步：归档并报告

```bash
git add -A && git commit -m "update YYYY-MM-DD: <变更摘要>"
```

报告：新增/变更/废止数量 + 涉及准则或税法 + 生效日变化提醒（如 CAS30 式分批生效）。

## 红线

- 未经用户确认禁止改 status/supersedes。
- 禁止删除任何已入库文件。
- flk 在线核验超时属已知上游风险：改用库内 front-matter + lawtext 镜像，并明示「本次未在线核验」。
