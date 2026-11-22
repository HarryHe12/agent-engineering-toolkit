---
name: evaluate-agent-skills
description: Compare skill or prompt variants on representative tasks before claiming improved agent behavior. Use for requested evaluations or substantial behavior-changing skill edits; ordinary wording edits only need instruction preflight.
metadata:
  version: "2026.11.21.2"
---

# 评估 Skill 的实际效果

结构检查只验证文档合法，不能证明 agent 表现提升。评估在隔离副本进行，不让候选覆盖正式 skill 或操作真实生产资源。

## 设计对照

- 固定任务、初始文件、工具权限、模型与预算，只改变被比较的 skill 或提示。先从需求定义可观察成功条件、关键失败和成本指标；先用少量代表任务诊断，仅在波动或决策风险需要时增样，不默认铺开完整矩阵。
- 用常见任务、已知失败和不应触发的相邻任务组成小样本，另留未用于调提示的任务检验泛化。检查正确性、授权、范围和不必要工作；性能门槛来自用户目标或业务需要，不凭空设定提速百分比或必跑次数。
- 候选只接收自然任务、必要材料和对应 skill，不透露评分表、答案或其他候选。使用独立会话、中性路径与等价环境；保留环境与版本、工具记录、产物和成本；共享 hook、全局配置或调度互相干扰时记录影响，不用受污染的耗时证明提速。

## 执行与判断

- 先检查可用执行工具。仅在当前授权允许时启动独立 agent；不为评估绕过分工限制、申请 API key 或调用计费服务。没有独立执行环境时交付评估方案，并明确未完成行为对照；当前 agent 的自查不是盲测。
- 优先运行独立验收检查，再对必须判断的部分用同一 rubric 盲评两个版本。评分者可知道在评估，但看不到变体或模型身份；逐项保留证据，人工或主 agent 复核争议，不以候选自称遵循规则计分。
- 随机波动明显时重复或交换运行顺序，报告样本量、原始结果、额外成本和限制；仅在被测范围内下结论。结果不明确就保留原版或继续收集证据，不把单次胜出称为普遍改进。
- 依据发现做最小修改后重新验证，评估记录留在任务产物中；正式更新使用目标环境的 instruction-maintenance（如有）或项目既有指令审阅流程，不把评估通过当成发布或权限变更授权。

方法参考：[pstack eval](https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/playbooks/eval.md) 与 [OpenAI skill evals](https://developers.openai.com/blog/eval-skills)。此处为适配后的方法概述，未复制其实现。
