你是 orchestrator 的评测输入生成器。请不要完成业务任务本身，只评估如何路由。

请对下面 6 个场景分别给出 JSON 决策，输出必须是一个 JSON 对象，格式如下：

```json
{
  "summary": "一句话总结",
  "cases": [
    {
      "case_id": "string",
      "user_request": "string",
      "selected_agent": "string or null",
      "delegation_reason": "string",
      "delegated_task": "string",
      "handoff_agents": ["string"],
      "output_distribution": "string",
      "clarification_needed": true,
      "self_execute": false
    }
  ]
}
```

要求：
- 只能做调度判断，不能自己完成任务。
- 如果信息不足，`selected_agent` 可为空，但必须把 `clarification_needed` 设为 `true`。
- `self_execute` 必须始终为 `false`。
- `delegated_task` 要保留用户原始目标和关键输出要求。
- 如果需要多 agent 协作，使用 `handoff_agents` 说明链路，并用 `output_distribution` 说明上游输出如何传给下游。

场景：

1. `case_id = kinetics_csv`
用户请求：读取 `paper.md`，提取所有酶动力学参数，整理成 CSV。

2. `case_id = figure_review`
用户请求：分析 `figure1.png` 和 `figure2.png`，判断哪些图包含可用于酶反应结论的信息。

3. `case_id = ambiguous_request`
用户请求：帮我处理一下这个实验结果，尽快给个结论。

4. `case_id = explicit_agent`
用户请求：使用 `document-structure-analyzer` 读取 `report.md`，只输出章节结构，不要做反应抽取。

5. `case_id = multi_handoff`
用户请求：先分析 `paper.md` 的章节和图表位置，再抽取酶动力学结果，最后生成一份汇总说明。

6. `case_id = missing_attachment`
用户请求：请分析 `figure3.png` 并告诉我它是否支持酶反应结论。
补充信息：当前没有提供 `figure3.png` 文件。
