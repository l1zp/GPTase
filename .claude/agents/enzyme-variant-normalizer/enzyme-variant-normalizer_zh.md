---
name: enzyme-variant-normalizer
description: 将原始酶提取副本协调为规范变体记录，包含归一化动力学参数和序列增强提示。
tools:
---

本 agent 由同目录 `hooks.py` 中的 `pre_run` 钩子拦截执行，**不经过 LLM**。

钩子从 prompt 信封中解析 JSON 输入、展开上游工件路径引用，
然后直接调用 `normalize_variant_payload`（实现位于
`.claude/agents/enzyme-variant-normalizer/normalizer.py`）。

Markdown 定义文件存在的目的是让编排器能够发现该 agent，
并与其他工作流步骤保持一致的计划引用验证；其内容对 LLM 不可见
（钩子在 LLM 调用之前短路返回）。
