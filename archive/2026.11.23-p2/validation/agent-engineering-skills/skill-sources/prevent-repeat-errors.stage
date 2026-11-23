---
name: prevent-repeat-errors
description: Turn evidenced recurring coding-agent mistakes into repository structure or executable checks. Use when the user reports the same mistake again or requests prevention; do not expand a routine bug fix into an unrelated repository audit.
metadata:
  version: "2026.11.21.2"
---

# 防止重复错误

只围绕当前错误及相关历史证据调查，复用已有检查器；此 skill 提供选择约束的办法，不拥有代码门禁或业务规则。

- 从用户纠正、相关提交、回退或审查记录收集可核实实例，区分同类根因与表面相似。一次事件只修复已证实问题，不据此发明全局禁令；缺少历史证据时说明未证实重复。
- 依次评估：用模块边界和单一所有者消除错误入口；用类型或数据契约排除非法状态；用现有 lint、构建或 CI 拒绝错误写法；用行为回归测试覆盖剩余风险。选择能可靠约束该类错误且维护成本合理的一层，不为简单问题重构整个项目。
- 同时检查相邻旧示例，避免 agent 继续模仿错误模式；只在本次授权范围迁移和清理。检查失败信息应指向正确 API、模块或操作；例外遵循项目既有机制，不新增统一审批门槛。
- 用真实旧错误或同根因最小反例证明约束拒绝错误，再证明合法路径通过；沿用已有独立预期及回归要求。检查扫描对象存在且实际覆盖目标，避免错误工作目录或空扫描显示通过；说明静态导入等支持范围及漏检边界。不能运行时列明待验证项。
- 仅在工具无法表达且确实需要判断时补文字。更新唯一权威位置，已有规则只补执行依据；如需对照表，放在现有项目质量文档，列错误证据、约束位置、执行命令及覆盖边界，不把任务日志塞进全局 AGENTS。

目标环境提供 local-code-guard 或 instruction-maintenance 时，按对应 skill 处理门禁维护或持久指令更新；否则复用项目已有质量门禁及指令审阅流程。本 skill 不授权修改全局门禁或生产系统，不依赖固定本机路径。

方法参考：[pstack correct](https://github.com/cursor/plugins/blob/main/pstack/skills/correct/SKILL.md)。此处为适配后的方法概述，未复制其实现。
