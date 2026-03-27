# GPTase UI Redesign Prompt for Figma Make

```text
请基于一个名为 GPTase 的 AI 多智能体工作台，重新设计并实现一个更成熟、更适合生产环境的 Web UI。目标不是做营销官网，而是做一个真正用于日常工作的桌面优先应用界面。

产品背景：
GPTase 是一个 multi-agent framework，用于 AI task automation，支持单 agent、Plan 工作流、多步骤执行、会话管理、执行状态跟踪、working memory、eval traces，以及生物化学分析相关任务。它有 Web UI，前后端分离，前端是 React + TypeScript。当前界面功能比较基础，信息层级和视觉质量都不够。

设计目标：
1. 做成一个专业的 AI workspace，而不是普通聊天框。
2. 保留三栏结构思路，但整体更清晰、更现代、更精致。
3. 突出“任务执行”“计划状态”“多 agent 协作”和“可观察性”。
4. 桌面端优先，同时兼顾移动端可用性。
5. 风格要克制、专业、偏科研工具 / 高级生产力工具，不要花哨，不要营销页风格，不要过度卡片堆砌。
6. 视觉上比现在明显更高级：更好的排版、留白、层级、配色、边框、阴影和状态反馈。
7. 不要做成通用 ChatGPT 克隆，要有 GPTase 自己的产品感。

功能要求：
- 左栏：
  - 会话列表
  - 新建会话
  - agent 选择器
  - 最近 session / plan 入口
  - 必要时支持搜索或筛选
- 中栏：
  - 主工作区
  - 支持 goal 输入 / 对话消息 / 系统状态消息 / draft plan summary
  - 输入区要清晰，适合长任务描述
  - 可以展示空状态、加载状态、执行中状态
- 右栏：
  - session detail
  - 当前 plan 概览
  - task traces / runtime progress
  - selected agent memory
  - eval traces 或调试信息入口
- 整体需要支持：
  - draft plan review
  - approve / revise session
  - plan execution progress
  - 历史消息与状态消息区分
  - 长内容滚动时仍然清晰

交互要求：
- 强化任务流感受：用户输入目标后，界面要清晰表达“生成 draft -> 审核 -> 执行 -> 完成/继续反馈”的过程。
- 让用户能快速知道：
  - 当前选中了哪个 agent
  - 当前 session 在做什么
  - 当前 plan 到哪一步了
  - 哪些信息是结果，哪些信息是系统状态
- 合理加入 loading、progress、status badges、step indicators、timeline 或 trace 视图
- 不要只做静态好看，要考虑真实数据密度和持续使用体验

视觉方向：
- 整体偏浅色主题，允许有轻微暖灰或冷灰底色
- 避免默认蓝白企业后台模板感
- 可以使用更有辨识度但克制的强调色
- 字体、间距、标题层级、信息密度要专业
- 允许 subtle gradients、panel layering、section dividers，但不要花哨
- 风格参考：高级研发工具、AI ops 控制台、科研工作台，而不是社交产品

代码要求：
- 使用 React + TypeScript
- 输出可运行的单页应用界面
- 优先实现高保真的前端结构和样式
- 可以先用 mock data 模拟：
  - agents
  - sessions
  - messages
  - plan steps
  - task traces
  - memory panel
  - eval traces
- 组件结构清晰，便于后续替换成真实 API
- 请保留合理的状态管理，不要把所有东西都塞进一个巨大组件
- 尽量产出干净、可维护的代码

额外要求：
- 当前版本是中文界面，优化版本也优先中文
- 文案请专业、简洁，不要营销化
- 界面中要明确体现 GPTase 是“Agent + Plan + Execution + Memory + Eval”一体化工作台
- 请直接输出优化后的完整界面实现，不要只给设计说明
```
