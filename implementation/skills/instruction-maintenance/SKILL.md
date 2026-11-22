---
name: instruction-maintenance
description: Create or update active AGENTS.md, SKILL.md, business specs and their governing references with canonical ownership, independent semantic review and local preflight. Use for persistent agent instructions, not ordinary prose or historical logs.
---

# 维护长期指令

## 内容归属

- 全局 AGENTS 只放跨项目偏好与授权边界；项目 AGENTS 只放项目差异、入口和操作边界；业务 Spec 定义行为与独立例子；Skill 保存复用方法。每项规则指定唯一权威位置，其他位置按需引用。
- 仅将影响后续决策的稳定要求加入常驻入口。任务进展、旧工作区、提交编号和验收数字留在历史记录；不要把一次失败推广为永久禁令，不追加“本节覆盖上文”来积累版本。
- 先查现有所有者及相关调用文档，优先更新、合并、替换已有条目。无法自动执行且确需判断的要求才保留为文字；可执行规则以检查器或契约为权威，入口只保留调用位置。
- 入口保持短小，细节按任务条件加载。拆文件必须对应明确作用域，不通过无条件读取多份文档转移体积；体积预算由 `md_rules.py` 统一维护，不把数字再抄到其他文件。

## 草稿、独立审查与发布

- 正式文件之外准备 `.stage` 草稿，将用户原话和必要授权上下文保存为来源文件；补充证据保留原文，不编造批准或把作者解释冒充来源。审查限本次差异及其必要上下文，不扩大为历史清理。
- 先运行 `md_write.py analyze` 修复确定的结构问题，不能提高预算或关闭检查。独立判定标准由`$CODEX_HOME/md-governance/review_policy.json` 中的审查策略维护；不在作者上下文中另造一套评分口径。
- 再运行 `md_write.py review`。写入器启动不继承作者对话的独立 Codex 审查，逐项判断并核对原文证据；作者自填的“审阅通过”JSON不能代替该凭证。

```sh
python3 $CODEX_HOME/md-governance/md_write.py analyze --target /path/AGENTS.md --draft /path/candidate.stage
python3 $CODEX_HOME/md-governance/md_write.py review --target /path/AGENTS.md --draft /path/candidate.stage --request /path/request.txt --evidence /path/source.txt
python3 $CODEX_HOME/md-governance/md_write.py apply --target /path/AGENTS.md --draft /path/candidate.stage --review /path/generated/review.json
```

- `review` 返回 `revise` 时，按具体位置、问题和修改意见改草稿，再重新审查；不直接修改权威文件来绕过意见。返回 `unavailable` 或依据不足时，保留草稿，修复可用性或补齐真实依据，不自签放行。
- 仅在独立审查通过后使用其返回的 `review` 路径执行 `apply`。原文件、草稿、依据、相关权威文档或判断标准变动都会使待发布凭证失效；审查通过不是发布权限或独立人工批准。
- 校验有效后由写入器原子替换正式文件；运行收据保存在私有状态目录，不注入日常上下文。
- 清理时保留有依据的权限、业务含义和例外；历史全文归档并记录去向，不用删字改变授权。有歧义且影响行为的冲突查最新用户决定，无法确定才询问。归档属于证据，不作为现行入口默认读取。

## 验证边界

- 结构检查覆盖预算、段落及同段落句子的规范化重复、坏链接等确定问题；独立模型审查补充语义判断，仍可能误判。签名凭证证明本地受信任流程完成，不保证每条规则必然正确，也不是对同权限蓄意篡改的系统隔离。
- 不能给新增修改补签旧格式凭证。直接写正式指令仍可能先落盘，Hook 会反馈并阻止未通过的本次修改收尾；使用草稿写入器才能在正式替换前拒绝候选。
- 文件删除或迁移前检查引用并保全历史；已登记权威文件的删除需要明确的退役维护，不能删文件或本地收据逃过检查。更新治理程序属于显式维护，保留原检查强度、恢复点和回归验证。
