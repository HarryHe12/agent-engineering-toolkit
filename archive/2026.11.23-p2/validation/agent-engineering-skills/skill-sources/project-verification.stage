---
name: project-verification
description: Create or maintain a repository-specific verification skill and feature map when agents lack reliable instructions to launch and exercise the real app, CLI, or API. Reuse an existing working harness; not a replacement for ordinary task tests.
metadata:
  version: "2026.11.21.2"
---

# 项目验证指南

先检查项目已有 verify skill、测试入口、运行脚本及功能地图；能用就补缺口，不另建平行体系。此 skill 管生成和维护验证方法，业务规则仍由项目 Spec 或公开契约定义。

## 建立

- 从源码、路由、命令和项目文档核实启动命令、就绪信号、认证前提、可用驱动工具及实例隔离方式。优先已有 harness 和连接器，无法隔离时不要同时操作同一实例。
- 优先补齐已有指南的启动、只读健康检查、操作、证据和清理。已有入口足以复用时，不另建路由 skill 或平行文档；确有发现入口的缺口时，才在项目约定目录（默认 .agents/skills）添加薄路由，方法仍只维护一份。
- 先覆盖当前任务关键路径，记录入口、前提、操作、独立预期、结果和副作用；单入口 CLI 可内联在指南中。只有多个入口难以发现或重复时才拆功能地图，按需读取，明确未覆盖范围，不猜测选择器。
- 按生成的指南实际跑通一个代表性功能，保存操作与结果证据，清理自己创建的资源后核实证据仍在。无法运行就交付草稿和具体阻碍，不能称为已验证指南。

## 维护

- 产品入口、定位方式或启动流程变化时，对照相关源码并实跑受影响功能，更新原指南及地图。记录覆盖范围和未执行项；一次成功不能代表所有功能通过。
- 指南与实际行为不一致时先区分文档过时和产品回归；产品回归按任务范围修复或报告，不通过改预期掩盖。真实外部发送、付费或生产数据变更仍按当前授权执行。

生成或更新长期指令时，若环境提供 instruction-maintenance，先按该 skill 执行；否则沿用项目现有指令审阅与检查流程。工具、后台操作和测试预期遵循目标环境已有规则，不依赖固定本机路径。

方法参考：[pstack verification](https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md)。此处为适配后的方法概述，未复制其实现。
