# 六项递进实践

依赖：**Python 3.9+，仅标准库**；本次实际为 Python 3.9.6。离线项目无需模型密钥，不访问网络。所有 fixture:// 来源均为合成教学资料，不是真实项目事实。`ScriptedModel` 是确定性替身，不是小型语言模型。

先在终端进入本文件所在目录，后面所有命令都在此运行：

```sh
cd agent-engineering-lab/实践
python3 -m unittest -v
```

## 代码导航

| 文件 | 作用 |
|---|---|
| minimal.py | 最小两轮行动/反馈循环 |
| lab.py | 工具契约、错误观察、证据验收、检查点、脚本模型和 Responses 适配器 |
| data/docs.json | 合成资料，含一段恶意内容；gold facts 不经 search 返回 |
| evaluate.py | 8 个任务条件各重复 5 次，保存原始轨迹与摘要 |
| metrics.py | token、费用、每成功成本、延迟和 Wilson 算式 |
| compare.py | 固定等待的串行/并发隔离循环对照 |
| ablations.py | 重试预算、上下文选择和错误记忆的机制反例 |
| planning.py | 可观测图环境的计划、遇阻反馈与重规划 |
| live_benchmark.py | 待联网验证的固定工作流/单 Agent/双 Agent 受控入口 |
| test_lab.py | 运行契约、恢复、计量、协议映射和三种架构本地测试 |
| results/ | 历史实验快照；新运行结果写入 results/generated/ |

## 实践 1：手写循环

**目标**：看到模型建议、代码执行、工具反馈与结束的职责。**最小代码**：minimal.py（完整独立脚本）。**输入**：内置“计算 2+3”。

```sh
python3 minimal.py
```

**验证**：输出应依次包含 user、assistant 的 add 建议、tool 的 5、assistant 的答案；能解释如果工具给不同结果会怎样。**常见错误**：把模型建议直接当工具结果，或不把结果回传。**扩展**：改成乘法，限制轮数为 1，观察为何未能产出最终答复。

## 实践 2：参数、错误与终止

**目标**：失败是可观察、有限的执行路径。**最小代码**：lab.py 的 strict_json、search、run。**依赖**：无。

```sh
python3 lab.py --topic alpha --scenario badargs --checkpoint results/my-badargs.json
python3 lab.py --scenario transient --checkpoint results/my-timeout.json
python3 lab.py --scenario loop --checkpoint results/my-loop.json
python3 lab.py --scenario early --checkpoint results/my-early.json
```

**验证**：badargs 先 ValueError 后成功；transient 只读超时后恢复；loop 以 repeat_limit 结束；early 为 rejected_final。**常见错误**：所有异常都重试；每次恢复重置预算；把正常失败处理算任务成功。**扩展**：增加未知工具与额外字段，分别说明哪层拒绝；给写入动作设计幂等键，先用本地假服务测试。

注意：重复检测按工具名+原始参数字符串，属于简化设计，可被等价 JSON 排版变化绕过；不宣称通用循环检测。工具只读、进程内执行，不是任意代码安全沙箱。

## 实践 3：检索与来源引用

**目标**：答案来自实际证据并通过独立规则。**最小代码**：search、evidence、verify。**输入**：alpha/beta/gamma/不存在的项目。

```sh
python3 lab.py --topic beta --checkpoint results/my-beta.json
python3 lab.py --topic gamma --checkpoint results/my-gamma.json
python3 lab.py --topic missing --checkpoint results/my-missing.json
```

**验证**：beta 负责人陈、状态待审，引用 D2 且包含原文；missing 不得成功；gamma 的攻击句子不改变代码可用工具。**常见错误**：把搜索结果 ID 当已经读过；引用无关片段；将合成 fixture 当外部证据。**扩展**：换成三个官方文档的本地摘录，保留 URL、版本、日期、段落位置；另写主张支持检查，不能沿用模板 gold 冒充通用语义评估。

## 实践 4：跨进程中断与恢复

**目标**：保存事实、预算与调用关联，重启后继续。

```sh
python3 lab.py --topic alpha --checkpoint results/my-resume.json --pause-after 1
python3 lab.py --checkpoint results/my-resume.json --resume
```

**验证**：首次 steps=1、status=running，已存工具观察；恢复后 steps=2、success，只有一次工具读取。再次 resume 不应重新执行。修改 docs.json 后旧状态应因 doc_hash 不匹配而拒绝；修改前请备份并恢复教学资料。

**常见错误**：把暂停写成成功；只存最终答案；恢复时重复工具；多人写同一个 JSON。**扩展**：改 SQLite 并加任务 ID 索引，故障注入到工具返回和 checkpoint 保存之间；说明原子替换不等于断电持久性，也不等于远端写入原子提交。

## 实践 5：任务集与计算

**目标**：原始结果可重算，区分契约通过与目标成功。

```sh
python3 evaluate.py
python3 metrics.py results/generated/runs.json
python3 ablations.py
```

**验证**：evaluate 在 `results/generated/` 写 runs.json 和 summary.json；每种失败都有 expected 状态。compare、ablations 和 planning 的新结果也写入该目录，历史快照保持不变。脚本替身 token 与费用为 null；不能从字符串长度伪造 token。**常见错误**：删掉失败再算平均成本；把确定性重复的 40 次当独立模型样本。**扩展**：新增一个保留任务，不用它调策略；为工具故障、来源冲突与过期记忆加任务。

计价输入示例（**合成费率，仅作算式教学，绝非服务商价格**）：

```json
{"input": 2, "cached_input": 1, "output": 4}
```

保存为自己的 rates.json 后，可对真实 Responses usage 运行：

```sh
python3 metrics.py results/live/runs.json --rates rates.json
```

真正使用请将费率改为所选模型官方页面的当日值，并另存模型 ID、币种、访问日期、工具费/存储费。该计算器只自动算三类 Responses token 费用；兼容字段 cost/cost_per_success 仅指 token 费；为每条 run 补入同币种 non_token_cost（工具、资源、人工等合计）后，才会生成 total_cost_all_categories/total_cost_per_success，否则完整费用保持 null。Claude/Gemini usage 须先转换，缓存写入和托管工具费用未包含，不能当完整账单。

计算定义：

```text
任务 token = 所有请求 usage 的和（含重复发送历史、重试、子任务）
token 费 = [(input-cached)*输入单价 + cached*缓存单价 + output*输出单价]/1e6
完整任务费 = token费 + 工具费 + 存储/运行资源费 + 可归属人工费
每成功任务平均成本 = 所有任务总费 / 成功任务数
墙钟延迟 = 结束时间 - 开始时间（跨恢复时另记录实际人工/暂停等待）
串行等待 ≈ 各环节等待和；并行墙钟 ≈ 关键路径 + 调度/合并
```

本地 elapsed_s 累加运行片段，**不含暂停期间**；不能直接当含人工等待的端到端延迟。timings 只是主要类别，未计的编排/序列化以墙钟剩余部分观察。并发各环节累计时间可能大于墙钟，不可当错误自动相减。

## 实践 6：单/多 Agent 与工作流对照

**目标**：先理解调度，再以真实 usage 检验架构。**最小离线代码**：compare.py。

```sh
python3 compare.py
```

同样 alpha/beta、同策略、同工具、同 4 次策略调用，每次注入 .02 秒等待；比较顺序执行两条隔离循环与双工作者并发。确定性汇总代码不调用模型。输出真实墙钟、调用数和结果传输字节。**局限**：这不是共享上下文的单 Agent 对照，也不是模型规划/协作能力测试，只验证等待可重叠与状态隔离。

**真实架构入口**：live_benchmark.py。选定当前账户能用的模型 ID，并在自己的环境配置 OPENAI_API_KEY；不要把密钥写进资料或贴到聊天。没有内置模型名/价格，避免未经验证的替换。

```sh
python3 live_benchmark.py --help
python3 live_benchmark.py --model '你选择的真实模型ID' --repeats 3 --total-calls 6 --max-output 800
```

运行会实际发起计费请求。本次只执行 help、语法和本地假响应测试，未执行上述联网命令。

三种模式：workflow 代码先读两个文档再一次模型抽取；single 在一个上下文中自主取证；multi 两个隔离上下文各分配一半总调用预算，再由代码合并。相同模型、工具、任务、总最大调用数、每调用输出限制；工作流的实际调用较少，保留这个差异。模式顺序按重复轮转；记录每轮 usage 与状态。

**公平性边界**：相同上限不等于相同实际 token；worker 输入重复/协调开销可能不同；本例确定性协调者未计模型汇总，因为确实没调用。若改成模型协调，必须从总预算中扣除。程序目前没有硬输入 token/美元上限，仅有总调用上限与每调用输出上限；因此不能把结果解释成完全相同费用实验。应按实际费用分层，或继续增加调用前 token 预算预留与同预算曲线。

**验证**：从 results/live/runs.json 逐题看证据、失败和 usage；summary 可重算。网络失败可能已发生服务端执行但未拿到 usage，标为未知；不要当零成本。工具只读，可安全失败，不自动重试网络请求。

**常见错误**：每位工作者都拿完整预算；额外模型汇总未计费；把并发变快写成准确率提升。**扩展**：真实资料分片、带来源合并、交叉检查；若加共享文件，建立归属与冲突合并，不让两者随意覆盖。

## 对照实验清单

| 要比较什么 | 本次可运行材料 | 能回答/不能回答 |
|---|---|---|
| 重试预算 | ablations.py、badargs/transient/loop | 能显示固定故障恢复所需轮数；不能推断真实模型最佳重试次数 |
| 上下文组织 | ablations.py 的同字符上限选择 | 能显示原始截断挤掉证据；字符不是模型 token，未测模型质量 |
| 有无/错误记忆 | ablations.py 的 scope/valid 过滤 | 能暴露错误作用域选择；未测长期模型记忆收益 |
| 串行/并发隔离循环 | compare.py | 能测固定等待的重叠；不能证明多 Agent 智力提升 |
| 工作流/单 Agent/多 Agent | live_benchmark.py，联网待验证 | 本地 fake provider 已验控制流；真实结论需实际 usage 和结果 |
| 规划是否有效 | planning.py 的纯代码图环境；真实模型规划提示作扩展 | 已验证遇阻重规划机制；本次未执行语言模型规划质量对照，不能作性能结论 |

## 实现限制

这是学习运行时：没有总墙钟取消、通用工具进程隔离、网络退避、审批服务、租户认证、并发 checkpoint 锁或故障后自动重发。OpenAI 请求设置 timeout=45，但它不是涵盖所有网络阶段的严格任务总期限。steps 与输出上限只能给出部分资源约束。把限制明确列出是为了知道何时必须补工程，不将示例当生产模板。

补充规划机制实验：`python3 planning.py`。相同初始图和 4 次行动上限，比较固定计划与遇阻重规划；输出每步输入、预期、观察、剩余计划和搜索展开数。扩展：减少预算、加入无法绕行的阻塞、增加行动成本；解释为什么搜索要求可观察/可回退环境。普通 BFS 不代表模型规划能力。

真实多 Agent 任务选择：当前两个短文档仅是冒烟测试，**没有足够复杂性证明需要多 Agent**。正式比较应换成两个独立且较大的官方资料集合（例如两个项目的版本兼容矩阵），各有多条要核对的主张、明确来源与冲突；共享上下文版与隔离工作者版使用同一总工具权限和预算。若业务要求数据域隔离，则单 Agent 基线也必须序贯切换隔离上下文；不能让单 Agent 获得额外联合数据权限。只有资料量、独立探索或隔离需求提供具体理由时，才把多 Agent 作为候选方案。当前交付没有用简单 fixture 宣称已证明协作必要性。
