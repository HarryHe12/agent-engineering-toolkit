# Agent Engineering Toolkit

一套可独立采用的 Codex 工程方法，覆盖本地代码检查、指令治理、产品验证、重复错误预防和 Skill 评估。仓库包含参考实现、安装指南和可复验样例。

| 方法 | 适用场景 |
| --- | --- |
| [本地代码门禁](implementation/skills/local-code-guard/SKILL.md) | 对代码变更执行检查，基于恢复点识别新增或恶化的问题 |
| [指令维护与独立审查](implementation/skills/instruction-maintenance/SKILL.md) | 维护 AGENTS.md、Skill 和业务规则，检查草稿并独立审查语义 |
| [项目运行验证](implementation/skills/project-verification/SKILL.md) | 从正常入口运行产品、验证关键路径并保留证据 |
| [重复错误预防](implementation/skills/prevent-repeat-errors/SKILL.md) | 把已证实的重复问题转化为结构约束或可执行检查 |
| [Skill 效果评估](implementation/skills/evaluate-agent-skills/SKILL.md) | 用同条件对照衡量质量、成本和适用范围 |

## 安装与验证

按[异机迁移实施指南](guides/Codex-异机迁移实施指南.md)安装所需组件。源码可以直接从本仓库的 `implementation/` 获取。独立审查使用接收方已有的 Codex CLI 登录。

[验证材料](validation/README.txt)包含合成任务、评估协议和复验入口。门禁测试验证检查与拦截行为，独立审查的历史验收记录对应当时测试的环境。
