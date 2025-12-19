# AContext 集成到 mini-swe-agent 实施计划

## 一、集成目标

将 AContext 集成到 mini-swe-agent 中，使其具备以下能力：
1. **SOP 学习能力**：从成功的任务中自动提取标准操作流程（SOP）
2. **经验检索能力**：在新任务开始时，检索相关的历史经验和最佳实践
3. **上下文管理能力**：通过 AContext 管理对话历史，支持长对话场景
4. **持久化存储**：所有 session 的消息和任务自动持久化到 AContext

## 🔒 兼容性保证

**重要原则：完全向后兼容，不改变原有使用方式**

### 1. 默认行为保持不变
- ✅ **默认禁用 AContext**：不添加任何参数时，mini-swe-agent 的行为与原来完全一致
- ✅ **原有命令完全有效**：所有现有的命令行参数和配置文件不受影响
- ✅ **零依赖冲突**：AContext SDK 不会与现有依赖冲突

### 2. 显式启用原则
- 🔧 **必须显式启用**：需要添加 `--acontext` 参数才会启用 AContext
- 🔧 **配置独立**：AContext 配置在独立的 `acontext.yaml` 文件中，不修改 `mini.yaml`
- 🔧 **Agent 独立**：新增的 `ContextAwareAgent` 不修改原有的 `DefaultAgent`

### 3. 失败不影响运行
- 🛡️ **优雅降级**：AContext 服务不可用时自动降级为无 AContext 模式
- 🛡️ **错误隔离**：AContext 相关错误不会导致任务失败
- 🛡️ **日志可控**：AContext 相关日志仅在启用时输出

### 4. 兼容性示例

#### 4.1 mini.py 兼容性

```bash
# ✅ 原有用法 - 完全不受影响
python -m minisweagent.run.mini \
    --task "Fix bug" \
    --model anthropic:claude-3-5-sonnet-20241022

# ✅ 显式禁用 - 等同于上面
python -m minisweagent.run.mini \
    --task "Fix bug" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --no-acontext

# ✅ 启用新功能 - 需要显式添加参数
python -m minisweagent.run.mini \
    --task "Fix bug" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext
```

#### 4.2 swebench.py 兼容性（批量处理）

```bash
# ✅ 原有用法 - 完全不受影响
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --split dev \
    --workers 4 \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --output ./results/baseline

# ✅ 显式禁用 - 等同于上面
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --split dev \
    --workers 4 \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --no-acontext \
    --output ./results/baseline

# ✅ 启用新功能 - 需要显式添加参数
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --split dev \
    --workers 4 \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext \
    --acontext-space-name "swebench-lite-exp" \
    --output ./results/with_acontext

# 说明：
# - 每个实例创建独立的 session
# - 所有实例共享同一个 Space（通过 --acontext-space-name 指定）
# - 后续实例可以从之前实例的 SOP 中学习
# - 并行处理安全，多 worker 可同时写入
```

#### 4.3 swebench_single.py 兼容性（单实例处理）

```bash
# ✅ 原有用法 - 完全不受影响
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --output ./results/instance.traj.json

# ✅ 显式禁用 - 等同于上面
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --no-acontext \
    --output ./results/instance.traj.json

# ✅ 启用新功能 - 需要显式添加参数
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext \
    --acontext-space-name "swebench-lite" \
    --output ./results/instance.traj.json

# ✅ 高级用法：恢复 session 进行调试
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext \
    --acontext-session-id "session-abc123" \
    --output ./results/instance_resumed.traj.json

# 说明：
# - 单个实例创建独立的 session
# - 可以从 Space 中检索历史 SOP
# - 支持 session 恢复（便于调试）
# - 交互模式会显示找到的相关 SOP
```

#### 4.4 兼容性总结

| 功能 | mini.py | swebench.py | swebench_single.py |
|------|---------|-------------|---------------------|
| 默认行为 | ✅ 禁用 AContext | ✅ 禁用 AContext | ✅ 禁用 AContext |
| 原有参数 | ✅ 完全兼容 | ✅ 完全兼容 | ✅ 完全兼容 |
| 启用方式 | `--acontext` | `--acontext` | `--acontext` |
| Space 管理 | 支持自定义 | 支持自定义（共享） | 支持自定义（共享） |
| Session 管理 | 每次新建或恢复 | 每实例独立 | 每实例独立或恢复 |
| 降级行为 | ✅ 优雅降级 | ✅ 优雅降级 | ✅ 优雅降级 |

---

## 二、集成架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     mini-swe-agent                          │
│                                                             │
│  ┌──────────────┐                                          │
│  │ CLI Entries  │ (mini.py, swebench.py, swebench_single) │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ContextAwareAgent (新)                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  AContextManager (新)                          │  │  │
│  │  │  • Space/Session 管理                          │  │  │
│  │  │  • 消息存储与检索                              │  │  │
│  │  │  • SOP 搜索与应用                              │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │                                                        │  │
│  │  继承自 DefaultAgent/InteractiveAgent                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  AContext Platform  │
        │  ┌───────────────┐  │
        │  │     Space     │  │ ← 存储学习的 SOP
        │  ├───────────────┤  │
        │  │   Sessions    │  │ ← 管理对话历史
        │  ├───────────────┤  │
        │  │   Messages    │  │ ← 存储消息
        │  ├───────────────┤  │
        │  │    Tasks      │  │ ← 跟踪任务状态
        │  └───────────────┘  │
        └─────────────────────┘
```

### 2.2 核心组件设计

#### 组件 1: AContextManager (新增)
**位置**：`src/minisweagent/acontext/manager.py`

**职责**：封装所有 AContext 操作的管理类

**核心方法**：
- `initialize()` - 初始化 AContext 客户端和 Space
- `start_session()` - 创建新 session 或恢复已有 session
- `store_message()` - 存储消息到 AContext
- `get_messages()` - 从 AContext 检索消息（支持上下文编辑策略）
- `search_sop()` - 根据任务描述搜索相关 SOP
- `format_sop_for_prompt()` - 将 SOP 块格式化为可注入 prompt 的文本
- `flush_and_wait()` - 等待任务提取完成（调试用）
- `get_task_status()` - 获取当前 session 的任务状态

**关键实现要点**：
- 所有操作包含 try-except 错误处理
- 启用/禁用状态检查（self.enabled）
- 支持通过 Space 名称或 ID 管理
- 支持 session 恢复和创建
- 配置驱动的灵活设计

#### 组件 2: ContextAwareAgent (新增)
**位置**：`src/minisweagent/agents/context_aware.py`

**职责**：继承自 DefaultAgent，集成 AContext 功能

**增强的生命周期**：
```
run() 开始
  ├─> initialize_acontext()          # 初始化 AContext
  ├─> search_and_apply_sop()          # 搜索并应用历史 SOP
  ├─> 执行任务循环
  │    ├─> query()                    # 查询 LLM
  │    │    └─> store_message()      # 存储 assistant 消息
  │    ├─> execute_action()           # 执行命令
  │    └─> get_observation()          # 获取观察
  │         └─> store_message()      # 存储 user 消息
  └─> finalize_acontext()             # 完成时标记任务状态
```

**关键实现要点**：
- 在 `__init__()` 中初始化 AContextManager
- 重写 `run()` 方法，添加 SOP 搜索和应用
- 重写 `add_message()` 方法，同步到 AContext
- 通过 `extra_template_vars` 注入 SOP 到 prompt
- 优雅的错误处理，确保 AContext 失败不影响主流程

#### 组件 3: InteractiveContextAwareAgent (新增)
**位置**：`src/minisweagent/agents/interactive_context_aware.py`

**职责**：继承自 InteractiveAgent，集成 AContext 功能

**关键差异**：
- 在交互模式中显示找到的 SOP
- 在任务完成时显示 AContext 摘要
- 其他实现与 ContextAwareAgent 类似

### 2.3 Space 管理策略

**推荐策略**：所有 session 存储到同一个 Space 中

**理由**：
1. **统一知识库**：所有任务的经验在一个知识库中，便于跨任务检索
2. **SOP 通用性**：代码修复、测试、调试等 SOP 在不同任务间是通用的
3. **简化管理**：避免多个 Space 的维护成本

**可选策略**（配置支持）：
- 按项目分 Space：适合多个独立项目
- 按任务类型分 Space：适合专业化场景（如只做 bug 修复）

**实现方式**：
- 默认 Space 名称：`mini-swe-agent-default`
- 通过 CLI 参数 `--acontext-space-name` 指定
- 通过 CLI 参数 `--acontext-space-id` 精确指定（优先级更高）

---

## 三、详细实施步骤

### 阶段 1：环境准备与依赖安装

#### Step 1.1: 安装 AContext Python SDK
**文件**：`pyproject.toml`

**修改点**：在 `dependencies` 列表中添加 `acontext>=0.1.0`

**验证**：运行 `pip install -e .` 并测试 `import acontext`

#### Step 1.2: 验证 AContext 服务可用性
**创建测试脚本**：`tests/test_acontext_connection.py`

**测试内容**：
- 连接 AContext 服务
- 执行 `client.ping()` 验证连通性
- 打印连接状态

---

### 阶段 2：核心组件实现

#### Step 2.1: 实现 AContextManager

**文件**：`src/minisweagent/acontext/manager.py`

**实现要点**：

1. **初始化流程**：
   ```
   __init__(config: dict)
     ├─> 解析配置
     ├─> 创建 AcontextClient
     └─> 设置 enabled 标志

   initialize()
     ├─> 测试连接 (client.ping())
     ├─> 初始化 Space (查找或创建)
     ├─> 初始化 Session (创建或恢复)
     └─> 返回成功/失败状态
   ```

2. **Space 管理**：
   - 支持通过名称查找（遍历 spaces.list()）
   - 未找到则创建新 Space
   - 支持通过 ID 直接指定
   - 在控制台显示 Space 状态（新创建/已存在）

3. **Session 管理**：
   - 支持创建新 session
   - 支持通过 session_id 恢复
   - 支持恢复最近的 session（resume_last）
   - 在 session configs 中记录元数据（agent、instance_id 等）

4. **消息存储**：
   - 使用 `sessions.store_message()` API
   - 消息格式：OpenAI 格式（role + content）
   - 异步存储，不阻塞主流程
   - 错误时记录日志但不中断

5. **SOP 搜索**：
   - 使用 `spaces.experience_search()` API
   - 支持 fast 和 agentic 两种模式
   - 过滤距离过大的结果（distance > 1.0）
   - 返回 SOP 块列表（title, use_when, preferences, tool_sops）

6. **SOP 格式化**：
   - 生成 Markdown 格式的 SOP 文本
   - 包含相关性评分
   - 包含使用场景和偏好
   - 包含推荐的工具步骤

**错误处理原则**：
- 所有外部调用包含 try-except
- 错误时记录日志并返回空结果或 False
- 不抛出异常，确保不影响主流程

#### Step 2.2: 实现 ContextAwareAgent

**文件**：`src/minisweagent/agents/context_aware.py`

**实现要点**：

1. **初始化**：
   ```
   __init__(model, env, acontext_config=None, **kwargs)
     ├─> 调用 super().__init__(model, env, **kwargs)
     ├─> 创建 AContextManager(acontext_config)
     └─> 初始化 sop_applied = False
   ```

2. **增强的 run() 方法**：
   ```
   run(task, **kwargs)
     ├─> if acontext.initialize():
     │     └─> _search_and_apply_sop(task)
     ├─> try:
     │     └─> exit_status, result = super().run(task, **kwargs)
     ├─> finally:
     │     └─> _finalize_acontext(exit_status)
     └─> return exit_status, result
   ```

3. **SOP 搜索和应用**：
   ```
   _search_and_apply_sop(task)
     ├─> sop_blocks = acontext.search_sop(task)
     ├─> if not sop_blocks:
     │     └─> return
     ├─> sop_text = acontext.format_sop_for_prompt(sop_blocks)
     ├─> extra_template_vars["historical_sop"] = sop_text
     └─> sop_applied = True
   ```

4. **消息同步**：
   ```
   add_message(role, content, **kwargs)
     ├─> super().add_message(role, content, **kwargs)
     └─> if acontext.enabled:
           └─> acontext.store_message(role, content)
   ```

5. **任务完成处理**：
   ```
   _finalize_acontext(exit_status)
     ├─> status = acontext.get_task_status()
     ├─> logger.info(f"AContext 任务状态: {status}")
     └─> acontext.close()
   ```

#### Step 2.3: 实现 InteractiveContextAwareAgent

**文件**：`src/minisweagent/agents/interactive_context_aware.py`

**关键差异**：
- 继承自 InteractiveAgent
- 在 `_search_and_apply_sop()` 中打印找到的 SOP
- 在 `_finalize_acontext()` 中打印 AContext 摘要

---

### 阶段 3：配置文件和模板修改

#### Step 3.1: 创建 AContext 配置文件

**文件**：`src/minisweagent/config/acontext.yaml`

**配置结构**：
```yaml
acontext:
  enabled: true
  api_key: "sk-ac-your-root-api-bearer-token"
  base_url: "http://localhost:8029/api/v1"
  timeout: 60.0

  space:
    space_name: "mini-swe-agent-default"
    space_id: null

  session:
    resume_last: false
    session_id: null

  sop_search:
    enabled: true
    mode: "fast"  # "fast" 或 "agentic"
    limit: 5
    semantic_threshold: 0.8

  message:
    store_realtime: true
    edit_strategies:
      - type: "token_limit"
        params:
          limit_tokens: 20000
      - type: "remove_tool_result"
        params:
          keep_recent_n_tool_results: 3
```

#### Step 3.2: 修改 system_template 支持 SOP 注入

**文件**：`src/minisweagent/config/mini.yaml`

**修改点**：在 `system_template` 末尾添加条件注入块

```jinja2
{% if historical_sop %}
{{ historical_sop }}
{% endif %}
```

---

### 阶段 4：CLI 集成（三个入口文件）

#### Step 4.1: 修改 mini.py

**文件**：`src/minisweagent/run/mini.py`

**修改要点**：

1. **导入新 Agent 类**：
   - `ContextAwareAgent`
   - `InteractiveContextAwareAgent`

2. **添加 typer 参数**（5 个新参数）：
   - `acontext_enabled: bool` (默认 False)
   - `acontext_config: Path | None`
   - `acontext_space_name: str | None`
   - `acontext_space_id: str | None`
   - `acontext_session_id: str | None`

3. **加载 AContext 配置**：
   - 创建辅助函数 `_load_acontext_config()`
   - 优先级：CLI 参数 > 配置文件 > 环境变量 > 默认值
   - 配置文件查找顺序：指定路径 > 默认路径 (config/acontext.yaml)

4. **选择 Agent 类**：
   ```
   确定基础 agent_class:
     if visual_mode:
       base = TextualAgent
     else:
       base = InteractiveAgent

   if acontext_enabled:
     if base == TextualAgent:
       警告：TextualAgent 暂不支持 AContext
       agent_class = TextualAgent  # 降级
     else:
       agent_class = InteractiveContextAwareAgent
   else:
     agent_class = base
   ```

5. **创建 Agent**：
   - 如果启用 AContext，传入 `acontext_config` 参数
   - 否则使用原有方式创建

#### Step 4.2: 修改 swebench.py（批量处理）

**文件**：`src/minisweagent/run/extra/swebench.py`

**修改要点**：

1. **导入新 Agent 类**：
   - `ContextAwareAgent`

2. **重构 ProgressTrackingAgent**：
   - 创建工厂函数 `_create_progress_tracking_agent_class(base_class)`
   - 动态生成继承自任意基类的 ProgressTrackingAgent
   - 保留原有的 step() 进度更新逻辑

3. **添加 typer 参数**（4 个新参数）：
   - `acontext_enabled: bool`
   - `acontext_config: Path | None`
   - `acontext_space_name: str | None`
   - `acontext_space_id: str | None`
   - 注意：不支持 `session_id`（每个实例独立 session）

4. **加载 AContext 配置**：
   - 创建辅助函数 `_load_acontext_config_for_swebench()`
   - 将配置添加到主配置字典 `config["acontext"]`

5. **修改 process_instance()**：
   ```
   确定基础 agent_class:
     if acontext_enabled:
       base = ContextAwareAgent
       # 为每个实例创建独立 session
       instance_acontext_cfg = copy(acontext_cfg)
       instance_acontext_cfg["session"]["session_id"] = None
       instance_acontext_cfg["session"]["configs"] = {"instance_id": instance_id}
     else:
       base = DefaultAgent

   ProgressTrackingAgentClass = _create_progress_tracking_agent_class(base)

   agent = ProgressTrackingAgentClass(
       model, env,
       progress_manager=...,
       acontext_config=instance_acontext_cfg if acontext_enabled else None,
       **config["agent"]
   )
   ```

**关键设计**：
- 每个实例独立 session，避免混淆
- 所有实例共享同一个 Space，积累经验
- 后续实例可以检索到之前实例的 SOP

#### Step 4.3: 修改 swebench_single.py（单实例）

**文件**：`src/minisweagent/run/extra/swebench_single.py`

**修改要点**：

1. **导入新 Agent 类**：
   - `InteractiveContextAwareAgent`

2. **添加 typer 参数**（5 个新参数）：
   - 与 mini.py 相同
   - 支持 `acontext_session_id`（用于调试恢复）

3. **加载 AContext 配置**：
   - 创建辅助函数 `_load_acontext_config_for_swebench_single()`
   - 在 session configs 中记录 `instance_id`

4. **选择 Agent 类**：
   ```
   if acontext_enabled:
     agent = InteractiveContextAwareAgent(
         model, env,
         acontext_config=acontext_cfg,
         **config["agent"]
     )
   else:
     agent = InteractiveAgent(
         model, env,
         **config["agent"]
     )
   ```

#### Step 4.4: 扩展轨迹保存

**文件**：`src/minisweagent/run/utils/save.py`

**修改点**：在 `save_traj()` 函数中添加 AContext 信息

```python
if hasattr(agent, "acontext") and agent.acontext.enabled:
    try:
        task_status = agent.acontext.get_task_status()
        traj["info"]["acontext"] = {
            "session_id": task_status["session_id"],
            "space_id": task_status["space_id"],
            "space_name": task_status["space_name"],
            "total_tasks": task_status["total_tasks"],
            "learning_status": task_status["learning_status"],
            "sop_applied": agent.sop_applied,
        }
    except Exception as e:
        logger.warning(f"保存 AContext 信息失败: {e}")
```

---

### 阶段 5：包结构和导出

#### Step 5.1: 创建 acontext 包

**文件**：`src/minisweagent/acontext/__init__.py`

**内容**：导出 `AContextManager`

#### Step 5.2: 更新主 __init__.py

**文件**：`src/minisweagent/__init__.py`

**添加导出**：
- `ContextAwareAgent`
- `InteractiveContextAwareAgent`
- `AContextManager`

---

### 阶段 6：测试和验证

#### Step 6.1: 单元测试

**文件**：`tests/test_acontext_integration.py`

**测试用例**：
- `test_manager_disabled()` - 测试禁用状态
- `test_manager_initialization()` - 测试初始化
- `test_message_storage()` - 测试消息存储
- `test_agent_without_acontext()` - 测试不启用 AContext
- `test_agent_with_acontext()` - 测试启用 AContext（需要服务）

#### Step 6.2: 集成测试

**文件**：`tests/integration_test_acontext.py`

**测试场景**：
- 基础集成测试（创建 Agent，执行简单任务）
- SOP 检索测试
- Session 恢复测试

#### Step 6.3: 端到端测试

**文件**：`tests/e2e_acontext_scenarios.sh`

**测试场景**：
- 场景 1: 创建文件任务
- 场景 2: Bug 修复任务（检索场景 1 的经验）
- 场景 3: 恢复 session
- 场景 4: SWE-bench 批量处理
- 场景 5: SWE-bench 单实例处理

---

## 四、部署和使用指南

### 4.1 环境变量配置

```bash
# AContext 配置
export ACONTEXT_API_KEY="sk-ac-your-root-api-bearer-token"
export ACONTEXT_BASE_URL="http://localhost:8029/api/v1"

# LLM 配置
export ANTHROPIC_API_KEY="your-anthropic-key"
```

### 4.2 mini.py 使用示例

#### 基础使用

```bash
# 启用 AContext（使用默认 Space）
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext

# 禁用 AContext（原有行为）
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --no-acontext
```

#### 指定 Space

```bash
# 为项目创建专用 Space
python -m minisweagent.run.mini \
    --task "Add authentication" \
    --acontext \
    --acontext-space-name "my-web-project"

# 恢复 Session
python -m minisweagent.run.mini \
    --task "Continue previous work" \
    --acontext \
    --acontext-session-id "session-xyz789"
```

### 4.3 swebench.py 批量处理

#### 基础批量处理

```bash
# 批量处理 SWE-bench Lite，启用 AContext
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --slice 0:10 \
    --workers 2 \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext \
    --acontext-space-name "swebench-lite-exp" \
    --output ./results/batch1
```

#### 断点续跑

```bash
# 第一次运行前 50 个实例
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --slice 0:50 \
    --acontext \
    --acontext-space-name "swebench-exp" \
    --output ./results/exp

# 继续运行剩余实例（自动跳过已完成）
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --acontext \
    --acontext-space-name "swebench-exp" \
    --output ./results/exp
```

#### 多项目隔离

```bash
# 不同 subset 使用不同 Space
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --acontext \
    --acontext-space-name "swebench-lite" \
    --output ./results/lite

python -m minisweagent.run.extra.swebench \
    --subset verified \
    --acontext \
    --acontext-space-name "swebench-verified" \
    --output ./results/verified
```

### 4.4 swebench_single.py 单实例处理

#### 基础使用

```bash
# 处理单个实例
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext \
    --acontext-space-name "swebench-lite" \
    --output ./results/django_12345.traj.json
```

#### 调试和 Session 恢复

```bash
# 第一次运行
python -m minisweagent.run.extra.swebench_single \
    --instance "django__django-12345" \
    --acontext \
    --acontext-space-name "debug-space" \
    -o ./debug/run1.traj.json

# 获取 session_id 并恢复
SESSION_ID=$(jq -r '.info.acontext.session_id' ./debug/run1.traj.json)

python -m minisweagent.run.extra.swebench_single \
    --instance "django__django-12345" \
    --acontext \
    --acontext-session-id "$SESSION_ID" \
    -o ./debug/run2.traj.json
```

### 4.5 端到端工作流示例

#### 场景：从零开始运行 SWE-bench Lite

```bash
# Step 1: 设置环境变量
export ACONTEXT_API_KEY="sk-ac-your-api-key"
export ACONTEXT_BASE_URL="http://localhost:8029/api/v1"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Step 2: 运行前 10 个实例（积累初始经验）
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --slice 0:10 \
    --workers 2 \
    --acontext \
    --acontext-space-name "swebench-lite-experiment" \
    --output ./results/batch1

# Step 3: 继续运行后 10 个实例（受益于历史经验）
python -m minisweagent.run.extra.swebench \
    --subset lite \
    --slice 10:20 \
    --workers 2 \
    --acontext \
    --acontext-space-name "swebench-lite-experiment" \
    --output ./results/batch2

# Step 4: 调试失败的实例
python -m minisweagent.run.extra.swebench_single \
    --subset lite \
    --instance "django__django-12345" \
    --acontext \
    --acontext-space-name "swebench-lite-experiment" \
    --output ./debug/django_12345.traj.json

# Step 5: 查看 AContext 信息
jq '.info.acontext' ./debug/django_12345.traj.json
```

---

## 五、预期效果和验证方法

### 5.1 功能验证清单

#### 基础功能
- [ ] AContext 服务连接成功
- [ ] Space 通过名称自动创建或查找
- [ ] Space 名称正确显示（新创建/已存在）
- [ ] Session 自动创建和管理
- [ ] 消息实时存储到 AContext
- [ ] 任务自动提取和状态跟踪
- [ ] SOP 搜索功能正常
- [ ] SOP 成功注入到 system prompt
- [ ] 历史经验在新任务中被应用
- [ ] 轨迹文件包含 AContext 信息（包括 space_name）

#### mini.py 集成
- [ ] `--acontext` 参数正常工作
- [ ] `--acontext-space-name` 参数正确设置 Space
- [ ] `--acontext-session-id` 参数可以恢复 session
- [ ] InteractiveAgent 模式正常显示 SOP 和 Space 信息
- [ ] TextualAgent 给出警告并降级（暂不支持）
- [ ] `--no-acontext` 完全禁用 AContext
- [ ] 不添加参数时默认禁用 AContext（向后兼容）

#### swebench.py 批量处理
- [ ] `--acontext` 参数启用 AContext
- [ ] 每个实例创建独立的 session
- [ ] 所有实例共享同一个 Space
- [ ] ProgressTrackingAgent 正常工作（基于 ContextAwareAgent）
- [ ] 多 worker 并行处理时无冲突
- [ ] 后续实例能检索到之前实例的 SOP
- [ ] 轨迹文件中包含 instance_id 和 AContext 信息
- [ ] preds.json 中包含结果

#### swebench_single.py 单实例处理
- [ ] `--acontext` 参数启用 AContext
- [ ] 单个实例创建独立的 session
- [ ] 能从 Space 中检索历史 SOP
- [ ] `--acontext-session-id` 可以恢复调试 session
- [ ] 交互模式正常显示 SOP
- [ ] session configs 中正确记录 instance_id

#### 配置加载
- [ ] 从默认位置加载 `acontext.yaml`
- [ ] `--acontext-config` 指定自定义配置文件
- [ ] CLI 参数正确覆盖配置文件
- [ ] 环境变量 `ACONTEXT_API_KEY` 和 `ACONTEXT_BASE_URL` 正常工作

#### 错误处理
- [ ] AContext 服务不可用时优雅降级
- [ ] 配置文件缺失时使用默认配置
- [ ] Space 或 session 创建失败时有明确错误信息
- [ ] SOP 搜索失败不影响任务执行

### 5.2 性能指标

- 初始化延迟: < 1 秒
- 消息存储延迟: < 100ms（异步）
- SOP 搜索延迟（fast 模式）: < 500ms
- SOP 搜索延迟（agentic 模式）: < 10 秒

### 5.3 验证步骤

1. **连接测试**：
   ```bash
   python tests/test_acontext_connection.py
   ```

2. **单元测试**：
   ```bash
   pytest tests/test_acontext_integration.py -v
   ```

3. **集成测试**：
   ```bash
   python tests/integration_test_acontext.py
   ```

4. **端到端测试**：
   ```bash
   bash tests/e2e_acontext_scenarios.sh
   ```

5. **手动验证**：
   - 运行任务 A（例如：修复一个 bug）
   - 查看 AContext Dashboard 确认任务被记录
   - 运行类似任务 B（使用相同 Space 名称）
   - 观察是否检索到任务 A 的 SOP
   - 查看轨迹文件，确认包含 AContext 信息

---

## 六、注意事项和最佳实践

### 6.1 注意事项

1. **不涉及 disk 和 artifact**：
   - 本集成不使用 AContext 的 disk 和 artifact 功能
   - 仅使用 session、message、task 和 space 功能

2. **Space 管理策略**：
   - 默认使用单一 Space（`mini-swe-agent-default`），所有任务共享
   - 适合积累通用的编程和调试经验
   - 可为不同项目指定专用 Space 名称
   - Space ID 优先级高于名称（高级用法）

3. **性能考虑**：
   - 消息存储是异步的，不影响 Agent 执行速度
   - SOP 搜索在任务开始时执行一次，延迟可接受
   - 使用 edit_strategies 控制上下文大小，避免 token 浪费

4. **错误处理**：
   - AContext 故障不应影响 Agent 正常运行
   - 所有 AContext 操作都有异常捕获
   - 连接失败时自动降级为无 AContext 模式

### 6.2 最佳实践

1. **配置管理**：
   - 使用环境变量管理敏感信息（API key）
   - 通过配置文件管理策略（搜索模式、token 限制等）
   - 为不同环境（开发/生产）使用不同配置

2. **Space 组织**：
   - **默认策略**：使用单一 Space（`mini-swe-agent-default`）快速积累通用经验
   - **项目隔离**：为不同项目指定专用 Space 名称
     ```bash
     --acontext-space-name "project-alpha"
     --acontext-space-name "backend-service"
     ```
   - **SWE-bench 专用**：为 SWE-bench 创建专用 Space
     ```bash
     --acontext-space-name "swebench-lite"
     --acontext-space-name "swebench-verified"
     ```
   - **命名规范**：使用清晰、一致的命名（如：`team-frontend`、`ai-research`）
   - **定期维护**：审查 Space 中的 SOP 质量，清理过时内容

3. **Session 生命周期**：
   - 每个独立任务创建新 Session
   - 相关任务可以恢复同一 Session
   - 避免 Session 过长导致上下文混淆
   - SWE-bench: 每个实例独立 session

4. **监控和调试**：
   - 定期检查 `get_task_status()` 输出
   - 查看轨迹文件中的 AContext 信息
   - 使用 AContext Dashboard 可视化学习进度
   - 使用 `--acontext-session-id` 恢复 session 进行调试

5. **渐进式启用**：
   - 第一阶段：仅启用消息存储和任务跟踪
   - 第二阶段：启用 SOP 搜索但不注入 prompt（观察）
   - 第三阶段：完全启用 SOP 应用

---

## 七、文件清单

### 新增文件

```
mini-swe-agent/
├── src/minisweagent/
│   ├── acontext/
│   │   ├── __init__.py                        # AContext 包初始化
│   │   └── manager.py                         # AContextManager 实现
│   ├── agents/
│   │   ├── context_aware.py                   # ContextAwareAgent
│   │   └── interactive_context_aware.py       # InteractiveContextAwareAgent
│   └── config/
│       └── acontext.yaml                      # AContext 配置文件
├── tests/
│   ├── test_acontext_connection.py           # 连接测试
│   ├── test_acontext_integration.py          # 单元测试
│   ├── integration_test_acontext.py          # 集成测试
│   └── e2e_acontext_scenarios.sh             # 端到端测试
└── .env.example                               # 环境变量模板
```

### 修改文件

```
mini-swe-agent/
├── src/minisweagent/
│   ├── __init__.py                            # 添加新 Agent 导出
│   ├── config/mini.yaml                       # 添加 SOP 模板变量
│   └── run/
│       ├── mini.py                            # 添加 CLI 参数和逻辑
│       ├── utils/save.py                      # 保存 AContext 信息
│       └── extra/
│           ├── swebench.py                    # 批量处理集成
│           └── swebench_single.py             # 单实例集成
└── pyproject.toml                             # 添加 acontext 依赖
```

---

## 八、总结

本实施计划详细描述了将 AContext 集成到 mini-swe-agent 的完整方案，包括：

1. **清晰的架构设计**：通过 AContextManager 和 ContextAwareAgent 实现解耦
2. **完整的实施步骤**：从依赖安装到测试验证的全流程
3. **灵活的配置系统**：支持多种使用场景和部署模式
4. **全面的测试方案**：单元测试、集成测试、端到端测试
5. **详细的使用指南**：命令行示例和最佳实践
6. **三个入口支持**：mini.py、swebench.py、swebench_single.py

### 核心特性

**🔒 完全向后兼容**：
- ✅ **默认禁用**：不添加参数时，行为与原有版本完全一致
- ✅ **显式启用**：需要 `--acontext` 才会启用 AContext
- ✅ **优雅降级**：AContext 故障不影响 Agent 正常运行
- ✅ **独立配置**：新增配置文件，不修改原有配置
- ✅ **独立 Agent**：新增 Agent 类，不修改原有类

**Space 名称管理**：
- ✅ 默认创建名为 `mini-swe-agent-default` 的 Space
- ✅ 启动时显示 Space 名称（新创建/已存在）
- ✅ 通过 `--acontext-space-name` 指定自定义 Space
- ✅ 相同名称自动复用已有 Space
- ✅ 支持通过 Space ID 精确指定（高级用法）
- ✅ 轨迹文件包含 space_name 便于追踪

**SWE-bench 支持**：
- ✅ 批量处理：每个实例独立 session，共享 Space
- ✅ 单实例：支持交互式调试和 session 恢复
- ✅ 并行安全：多 worker 同时写入同一个 Space
- ✅ 经验积累：后续实例从之前实例的 SOP 中学习

**优势**：
- **最小侵入性**：不破坏原有架构，完全向后兼容
- **高可用性**：AContext 故障不影响 Agent 运行
- **易于扩展**：模块化设计便于后续增强
- **生产就绪**：包含完整的错误处理和监控机制
- **用户友好**：清晰的命名和可见的状态反馈

实施后，mini-swe-agent 将具备强大的 SOP 学习和应用能力，能够从历史任务中持续学习和改进，**同时完全保持原有使用方式的兼容性**。
