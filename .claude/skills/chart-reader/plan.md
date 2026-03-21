# chart-reader Iteration Plan

## Iteration 1 — 测试结论

所有 with-skill agents 被沙箱拒绝 Bash 权限，OpenCV 完全未执行。
Pass rate: with_skill 86.7% vs without_skill 93.3%（with_skill 反而略低）。

---

## Iteration 2 — 已完成修改

### 1. Bash 不可用时的降级策略（优先级：HIGH）[DONE]

**修改内容**：
- 将 Phase 2 拆分为 Phase 2A（有 Bash）和 Phase 2B（无 Bash）
- Phase 2B 包含系统化的视觉估读流程：
  - Step 1: 记录 axis calibration（tick 坐标 → 数值）
  - Step 2: 线性插值公式
  - Step 3: 对数插值公式（带完整示例）
  - Step 4: 记录不确定度

### 2. 对数轴的系统化视觉估读（优先级：HIGH）[DONE]

**修改内容**：
- 在 Phase 2B Step 3 中加入对数插值公式
- 提供完整计算示例（从 tick 100 到 tick 1000，f=0.33 → value ≈ 214）
- 明确标注常见错误（线性插值 vs 对数插值）
- 在 Calibration 章节加入对数轴检测指标

### 3. 修正 Eval 1 的 Assertion（优先级：MEDIUM）[DONE]

**修改内容**：
- prompt 改为"提取图中所有可见变体，并注明任何缺失的预期变体"
- expected_output 明确说明 Des27.8 缺失
- 添加 assertion: output should contain "Des27.8"（表示提到了缺失）

### 4. 曲线追踪 vs 散点的明确区分（优先级：MEDIUM）[DONE]

**修改内容**：
- 在 Phase 1 加入强制声明要求：必须说明读值目标是 scatter points 还是 fitted curve
- 在 evals.json 中：
  - Eval 2 添加 assertion "scatter" 关键词
  - Eval 3 添加 assertion "curve" 关键词
  - 两个 eval 的 expected_output 都明确要求声明读值目标

### 5. 不确定度量化（优先级：LOW）[DONE]

**修改内容**：
- 在 Output Format 章节强制要求每个测量值附带不确定度
- 格式：`value ± uncertainty`
- 列出不确定度来源：OpenCV 精度、视觉主观判断、对数轴误差放大
- 示例 quality note 模板

---

## Iteration 2 待执行

1. ~~按上述优先级修改 SKILL.md~~ [DONE]
2. ~~修正 evals.json~~ [DONE]
3. 重新跑所有 6 个 agents（3 evals × with/without）
4. 对比 iteration-1 和 iteration-2 的结果

---

## 原始问题记录（Iteration 2 开始前）

### 1. Bash 不可用时的降级策略（优先级：HIGH）

**现状**：Skill 目前假设 Bash 可用。当 Bash 被拒绝时，agent 只是简单回退到视觉估读，与 baseline 没有区别，甚至因为花 token 描述 OpenCV 方法而更慢。

**修复方向**：在 SKILL.md 中加入明确的两层策略：
- **Phase 2A（有 Bash）**：运行 OpenCV 脚本，像素级精度
- **Phase 2B（无 Bash）**：系统化视觉网格法——利用已知 tick 坐标做比例插值，手动估读并给出明确的不确定度范围，比随意视觉读数更严谨

### 2. 对数轴的系统化视觉估读（优先级：HIGH）

**现状**：对数轴视觉读数没有引导，容易出现线性偏差（把 log scale 当 linear 读）。

**修复方向**：在 SKILL.md 中加入对数轴视觉估读公式：
```
log10(value) = log10(lower_tick) + (bar_height_fraction) * (log10(upper_tick) - log10(lower_tick))
```
要求 agent 在对数轴图中显式声明使用此公式，并写出计算过程。

### 3. 修正 Eval 1 的 Assertion（优先级：MEDIUM）

**现状**：`all_14_variants_present` 断言错误——图中确实没有 Des27.8（chart 从 Des27.7 跳到 Des27.9），两个 agent 都正确地只报告了 13 个变体，但断言把它们都标为 FAIL。

**修复方向**：将断言改为"所有可见变体都被识别，且正确说明 Des27.8 缺失"。

### 4. 曲线追踪 vs 散点的明确区分（优先级：MEDIUM）

**现状**：Eval 3 中，with-skill agent 未能明确区分"从拟合曲线上读值"和"从散点读值"（因为没有运行 OpenCV）。Baseline agent 反而用了明确的 "tracing up to the fitted curve" 语言。

**修复方向**：在 SKILL.md 的 Phase 1 中加入：对于有拟合曲线的图，必须明确声明读取目标是曲线还是散点，并描述如何在视觉上区分两者（颜色、连续性、平滑度）。

### 5. 不确定度量化（优先级：LOW）

**现状**：with-skill 的 Eval 2 输出了 "confidence MEDIUM-HIGH, ±0.02 mM, ±2 mOD/min"，这是好的，但只有 with-skill 做到了，而且格式不统一。

**修复方向**：在 SKILL.md 的输出格式要求中，强制要求每个测量值附带不确定度估计，尤其是在 Phase 2B（纯视觉）模式下。
