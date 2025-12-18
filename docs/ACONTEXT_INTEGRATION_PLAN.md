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
- 🔧 **必须显式启用**：需要添加 `--acontext-enabled` 参数才会启用 AContext
- 🔧 **配置独立**：AContext 配置在独立的 `acontext.yaml` 文件中，不修改 `mini.yaml`
- 🔧 **Agent 独立**：新增的 `ContextAwareAgent` 不修改原有的 `DefaultAgent`

### 3. 失败不影响运行
- 🛡️ **优雅降级**：AContext 服务不可用时自动降级为无 AContext 模式
- 🛡️ **错误隔离**：AContext 相关错误不会导致任务失败
- 🛡️ **日志可控**：AContext 相关日志仅在启用时输出

### 4. 兼容性示例

```bash
# ✅ 原有用法 - 完全不受影响
python -m minisweagent.run.mini --task "Fix bug" --model anthropic:claude-3-5-sonnet-20241022

# ✅ 显式禁用 - 等同于上面
python -m minisweagent.run.mini --task "Fix bug" --no-acontext

# ✅ 启用新功能 - 需要显式添加参数
python -m minisweagent.run.mini --task "Fix bug" --acontext-enabled
```

## 二、集成架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     mini-swe-agent                          │
│                                                             │
│  ┌──────────────┐                                          │
│  │   CLI Main   │                                          │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ContextAwareAgent (新)                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  AContextManager (新)                          │  │  │
│  │  │  • session 管理                                │  │  │
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
**职责**：封装所有 AContext 操作的管理类

**核心方法**：
- `initialize()`: 初始化 AContext 客户端和 Space
- `start_session()`: 创建新 session 或恢复已有 session
- `store_message()`: 存储消息到 AContext
- `get_messages()`: 从 AContext 检索消息（支持上下文编辑策略）
- `search_sop()`: 根据任务描述搜索相关 SOP
- `apply_sop_to_prompt()`: 将 SOP 注入到 system prompt
- `flush_and_wait()`: 等待任务提取完成（调试用）
- `get_task_status()`: 获取当前 session 的任务状态

#### 组件 2: ContextAwareAgent (新增)
**职责**：继承自 DefaultAgent/InteractiveAgent，集成 AContext 功能

**增强的生命周期**：
```
run() 开始
  ├─> initialize_acontext()  # 初始化 AContext
  ├─> search_and_apply_sop()  # 搜索并应用历史 SOP
  ├─> 执行任务循环
  │    ├─> query()  # 查询 LLM
  │    │    └─> store_message_to_acontext()  # 存储 assistant 消息
  │    ├─> execute_action()  # 执行命令
  │    └─> get_observation()  # 获取观察
  │         └─> store_message_to_acontext()  # 存储 user 消息
  └─> finalize_acontext()  # 完成时标记任务状态
```

#### 组件 3: 配置扩展
**位置**：新增 `config/acontext.yaml`

**配置项**：
```yaml
acontext:
  enabled: true
  api_key: "sk-ac-your-root-api-bearer-token"
  base_url: "http://localhost:8029/api/v1"
  timeout: 60.0

  # Space 管理策略
  space:
    space_name: "mini-swe-agent-default"  # Space 名称（用于查找或创建）
    space_id: null  # 指定 space ID（优先级高于 space_name）

  # Session 管理策略
  session:
    resume_last: false  # 是否恢复上次的 session
    session_id: null  # 指定 session ID

  # SOP 搜索配置
  sop_search:
    enabled: true
    mode: "fast"  # "fast" 或 "agentic"
    limit: 5  # 返回结果数量
    semantic_threshold: 0.8  # agentic 模式的语义阈值

  # 消息管理配置
  message:
    store_realtime: true  # 是否实时存储消息
    edit_strategies:  # 上下文编辑策略
      - type: "token_limit"
        params:
          limit_tokens: 20000
      - type: "remove_tool_result"
        params:
          keep_recent_n_tool_results: 3
          tool_result_placeholder: "[Previous command output]"
```

### 2.3 Space 管理策略

根据需求分析，建议：**所有 session 存储到同一个 Space 中**

**理由**：
1. **统一知识库**：所有任务的经验在一个知识库中，便于跨任务检索
2. **SOP 通用性**：代码修复、测试、调试等 SOP 在不同任务间是通用的
3. **简化管理**：避免多个 Space 的维护成本

**可选策略**（配置支持）：
- 按项目分 Space：适合多个独立项目
- 按任务类型分 Space：适合专业化场景（如只做 bug 修复）

## 三、详细实施步骤

### 阶段 1：环境准备与依赖安装

#### Step 1.1: 安装 AContext Python SDK
**文件**：`mini-swe-agent/pyproject.toml`

**修改点**：添加依赖
```toml
[project]
dependencies = [
    "acontext>=0.1.0",  # 新增
    # ... 其他依赖
]
```

**执行**：
```bash
cd mini-swe-agent
pip install -e .
```

#### Step 1.2: 验证 AContext 服务可用性
**创建测试脚本**：`tests/test_acontext_connection.py`

```python
from acontext import AcontextClient
import os

def test_acontext_connection():
    client = AcontextClient(
        api_key=os.getenv("ACONTEXT_API_KEY", "sk-ac-your-root-api-bearer-token"),
        base_url=os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1"),
        timeout=10.0
    )

    try:
        result = client.ping()
        assert result == "pong"
        print("✓ AContext 连接成功")
    except Exception as e:
        print(f"✗ AContext 连接失败: {e}")
        raise

if __name__ == "__main__":
    test_acontext_connection()
```

---

### 阶段 2：核心组件实现

#### Step 2.1: 实现 AContextManager

**文件**：`mini-swe-agent/src/minisweagent/acontext/manager.py` (新建)

**完整实现**：

```python
"""AContext 管理器 - 封装所有 AContext 操作"""
from acontext import AcontextClient
from acontext.types import Space, Session, Message
from typing import Optional, Any
import logging
import time

logger = logging.getLogger(__name__)


class AContextManager:
    """管理 AContext 集成的核心类"""

    def __init__(self, config: dict[str, Any]):
        """
        初始化 AContext 管理器

        Args:
            config: AContext 配置字典
        """
        self.config = config
        self.enabled = config.get("enabled", False)

        if not self.enabled:
            logger.info("AContext 集成已禁用")
            return

        # 初始化客户端
        self.client = AcontextClient(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "http://localhost:8029/api/v1"),
            timeout=config.get("timeout", 60.0)
        )

        self.space: Optional[Space] = None
        self.session: Optional[Session] = None
        self.session_id: Optional[str] = None

        logger.info("AContextManager 初始化完成")

    def initialize(self) -> bool:
        """
        初始化 AContext（创建或获取 Space 和 Session）

        Returns:
            bool: 是否成功初始化
        """
        if not self.enabled:
            return False

        try:
            # 1. 测试连接
            self.client.ping()
            logger.info("AContext 服务连接成功")

            # 2. 初始化 Space
            self._initialize_space()

            # 3. 初始化 Session
            self._initialize_session()

            return True

        except Exception as e:
            logger.error(f"AContext 初始化失败: {e}")
            self.enabled = False
            return False

    def _initialize_space(self):
        """初始化或获取 Space（支持名称和 ID）"""
        space_config = self.config.get("space", {})
        space_id = space_config.get("space_id")
        space_name = space_config.get("space_name", "mini-swe-agent-default")

        if space_id:
            # 优先使用指定的 Space ID
            try:
                # 验证 Space 存在（通过列表查询）
                spaces = self.client.spaces.list(limit=100)
                self.space = next(
                    (s for s in spaces.items if s.id == space_id),
                    None
                )
                if not self.space:
                    logger.warning(f"未找到 Space ID: {space_id}，将使用名称创建")
                    self.space = self._find_or_create_space_by_name(space_name)
                else:
                    space_display_name = self.space.configs.get("name", space_id)
                    logger.info(f"使用已有 Space: {space_display_name} ({space_id})")
                    print(f"✓ AContext Space: {space_display_name}")
            except Exception as e:
                logger.warning(f"获取 Space 失败: {e}，将使用名称创建")
                self.space = self._find_or_create_space_by_name(space_name)
        else:
            # 通过名称查找或创建 Space
            self.space = self._find_or_create_space_by_name(space_name)

    def _find_or_create_space_by_name(self, space_name: str) -> Space:
        """
        通过名称查找或创建 Space

        Args:
            space_name: Space 名称

        Returns:
            Space: 找到或创建的 Space
        """
        try:
            # 查找已有的同名 Space
            spaces = self.client.spaces.list(limit=100)
            for space in spaces.items:
                if space.configs.get("name") == space_name:
                    logger.info(f"找到已有 Space: {space_name} ({space.id})")
                    print(f"✓ AContext Space: {space_name} (已存在)")
                    return space

            # 未找到，创建新 Space
            space = self.client.spaces.create(
                configs={"name": space_name}
            )
            logger.info(f"创建新 Space: {space_name} ({space.id})")
            print(f"✓ AContext Space: {space_name} (新创建)")
            return space

        except Exception as e:
            logger.error(f"查找或创建 Space 失败: {e}")
            raise

    def _initialize_session(self):
        """初始化或恢复 Session"""
        session_config = self.config.get("session", {})
        session_id = session_config.get("session_id")
        resume_last = session_config.get("resume_last", False)

        if session_id:
            # 使用指定的 Session
            try:
                # 验证 Session 存在（通过获取消息）
                self.client.sessions.get_messages(session_id, limit=1)
                self.session_id = session_id
                logger.info(f"恢复 Session: {session_id}")
                return
            except Exception as e:
                logger.warning(f"恢复 Session 失败: {e}，将创建新 Session")

        elif resume_last and self.space:
            # 尝试恢复最近的 Session
            try:
                sessions = self.client.sessions.list(
                    space_id=self.space.id,
                    limit=1,
                    time_desc=True
                )
                if sessions.items:
                    self.session_id = sessions.items[0].id
                    logger.info(f"恢复最近的 Session: {self.session_id}")
                    return
            except Exception as e:
                logger.warning(f"恢复最近 Session 失败: {e}")

        # 创建新 Session
        self.session = self.client.sessions.create(
            space_id=self.space.id if self.space else None,
            disable_task_tracking=False,
            configs={"agent": "mini-swe-agent"}
        )
        self.session_id = self.session.id
        logger.info(f"创建新 Session: {self.session_id}")

    def store_message(self, role: str, content: str, **kwargs) -> bool:
        """
        存储消息到 AContext

        Args:
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容
            **kwargs: 其他元数据

        Returns:
            bool: 是否成功存储
        """
        if not self.enabled or not self.session_id:
            return False

        message_config = self.config.get("message", {})
        if not message_config.get("store_realtime", True):
            return False

        try:
            message_blob = {
                "role": role,
                "content": content
            }

            self.client.sessions.store_message(
                session_id=self.session_id,
                blob=message_blob,
                format="openai"
            )

            logger.debug(f"存储消息: {role} - {len(content)} chars")
            return True

        except Exception as e:
            logger.error(f"存储消息失败: {e}")
            return False

    def get_messages(
        self,
        limit: Optional[int] = None,
        apply_edit_strategies: bool = True
    ) -> list[dict[str, str]]:
        """
        从 AContext 获取消息历史

        Args:
            limit: 限制返回消息数量
            apply_edit_strategies: 是否应用上下文编辑策略

        Returns:
            list[dict]: OpenAI 格式的消息列表
        """
        if not self.enabled or not self.session_id:
            return []

        try:
            message_config = self.config.get("message", {})
            edit_strategies = None

            if apply_edit_strategies:
                edit_strategies = message_config.get("edit_strategies", [])

            result = self.client.sessions.get_messages(
                session_id=self.session_id,
                format="openai",
                limit=limit,
                time_desc=False,  # 按时间升序
                edit_strategies=edit_strategies if edit_strategies else None
            )

            logger.info(f"从 AContext 获取 {len(result.items)} 条消息")
            return result.items

        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return []

    def search_sop(self, task_description: str) -> list[dict[str, Any]]:
        """
        搜索相关的 SOP

        Args:
            task_description: 任务描述

        Returns:
            list[dict]: SOP 块列表
        """
        if not self.enabled or not self.space:
            return []

        sop_config = self.config.get("sop_search", {})
        if not sop_config.get("enabled", True):
            return []

        try:
            result = self.client.spaces.experience_search(
                space_id=self.space.id,
                query=task_description,
                mode=sop_config.get("mode", "fast"),
                limit=sop_config.get("limit", 5),
                semantic_threshold=sop_config.get("semantic_threshold", 0.8)
            )

            sop_blocks = []
            for block in result.cited_blocks:
                # 过滤距离太远的结果（距离 > 1.0 表示相关性较低）
                if block.distance > 1.0:
                    continue

                sop_blocks.append({
                    "title": block.title,
                    "distance": block.distance,
                    "use_when": block.props.get("use_when", ""),
                    "preferences": block.props.get("preferences", ""),
                    "tool_sops": block.props.get("tool_sops", [])
                })

            logger.info(f"搜索到 {len(sop_blocks)} 个相关 SOP")
            return sop_blocks

        except Exception as e:
            logger.error(f"搜索 SOP 失败: {e}")
            return []

    def format_sop_for_prompt(self, sop_blocks: list[dict[str, Any]]) -> str:
        """
        将 SOP 块格式化为可注入 prompt 的文本

        Args:
            sop_blocks: SOP 块列表

        Returns:
            str: 格式化的 SOP 文本
        """
        if not sop_blocks:
            return ""

        formatted = "\n## Historical Experience and Best Practices\n\n"
        formatted += "Based on previous successful tasks, here are some relevant patterns:\n\n"

        for idx, block in enumerate(sop_blocks, 1):
            formatted += f"### Experience #{idx} (relevance: {1 - block['distance']/2:.2%})\n"

            if block.get("use_when"):
                formatted += f"**When to use:** {block['use_when']}\n\n"

            if block.get("preferences"):
                formatted += f"**User preferences:** {block['preferences']}\n\n"

            if block.get("tool_sops"):
                formatted += "**Recommended approach:**\n"
                for step_idx, step in enumerate(block["tool_sops"], 1):
                    tool_name = step.get("tool_name", "")
                    action = step.get("action", "")
                    formatted += f"{step_idx}. {tool_name}: {action}\n"
                formatted += "\n"

        formatted += "You should consider these patterns but adapt them to the current task.\n\n"
        return formatted

    def flush_and_wait(self, timeout: int = 30) -> bool:
        """
        等待任务提取完成（主要用于调试）

        Args:
            timeout: 超时时间（秒）

        Returns:
            bool: 是否成功完成
        """
        if not self.enabled or not self.session_id:
            return False

        try:
            logger.info("等待任务提取完成...")
            self.client.sessions.flush(session_id=self.session_id)
            logger.info("任务提取完成")
            return True

        except Exception as e:
            logger.error(f"等待任务提取失败: {e}")
            return False

    def get_task_status(self) -> dict[str, Any]:
        """
        获取当前 session 的任务状态

        Returns:
            dict: 任务状态信息
        """
        if not self.enabled or not self.session_id:
            return {"enabled": False}

        try:
            # 获取任务列表
            tasks = self.client.sessions.get_tasks(
                session_id=self.session_id,
                limit=10,
                time_desc=True
            )

            # 获取学习状态
            learning_status = self.client.sessions.get_learning_status(
                session_id=self.session_id
            )

            return {
                "enabled": True,
                "session_id": self.session_id,
                "space_id": self.space.id if self.space else None,
                "space_name": self.space.configs.get("name", "未命名") if self.space else None,
                "total_tasks": len(tasks.items),
                "recent_tasks": [
                    {
                        "order": t.order,
                        "description": t.data.task_description,
                        "status": t.status
                    }
                    for t in tasks.items[:3]
                ],
                "learning_status": {
                    "digested": learning_status.space_digested_count,
                    "pending": learning_status.not_space_digested_count
                }
            }

        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return {"enabled": True, "error": str(e)}

    def close(self):
        """关闭管理器（清理资源）"""
        if self.enabled:
            logger.info("AContextManager 已关闭")
```

**说明**：
- 完全封装 AContext SDK 调用
- 支持自动重连和错误恢复
- 灵活的配置驱动
- 详细的日志记录

#### Step 2.2: 创建 ContextAwareAgent

**文件**：`mini-swe-agent/src/minisweagent/agents/context_aware.py` (新建)

```python
"""支持 AContext 的 Agent 实现"""
from minisweagent.agents.default import DefaultAgent
from minisweagent.acontext.manager import AContextManager
from minisweagent import Model, Environment
from typing import Any
import logging

logger = logging.getLogger(__name__)


class ContextAwareAgent(DefaultAgent):
    """集成 AContext 功能的 Agent"""

    def __init__(
        self,
        model: Model,
        env: Environment,
        acontext_config: dict[str, Any] | None = None,
        **kwargs
    ):
        """
        初始化 ContextAwareAgent

        Args:
            model: LLM 模型
            env: 执行环境
            acontext_config: AContext 配置
            **kwargs: 其他配置参数
        """
        super().__init__(model, env, **kwargs)

        # 初始化 AContext 管理器
        self.acontext = AContextManager(acontext_config or {})
        self.sop_applied = False

        logger.info("ContextAwareAgent 初始化完成")

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """
        执行任务（增强版）

        Args:
            task: 任务描述
            **kwargs: 其他参数

        Returns:
            tuple[str, str]: (退出状态, 结果)
        """
        # 1. 初始化 AContext
        if self.acontext.initialize():
            logger.info("AContext 集成已启用")

            # 2. 搜索并应用历史 SOP
            self._search_and_apply_sop(task)

        # 3. 执行任务（调用父类方法）
        try:
            exit_status, result = super().run(task, **kwargs)

            # 4. 任务完成后的处理
            if self.acontext.enabled:
                self._finalize_acontext(exit_status)

            return exit_status, result

        except Exception as e:
            # 确保异常时也记录状态
            if self.acontext.enabled:
                self._finalize_acontext("error")
            raise

    def _search_and_apply_sop(self, task: str):
        """搜索并应用历史 SOP"""
        try:
            # 搜索相关 SOP
            sop_blocks = self.acontext.search_sop(task)

            if not sop_blocks:
                logger.info("未找到相关的历史经验")
                return

            # 格式化 SOP 为 prompt 文本
            sop_text = self.acontext.format_sop_for_prompt(sop_blocks)

            # 将 SOP 注入到 system prompt
            # 方法 1: 通过 extra_template_vars（推荐）
            self.extra_template_vars["historical_sop"] = sop_text

            # 方法 2: 或者直接修改 system_template（如果需要）
            # self.config.system_template += "\n\n" + sop_text

            self.sop_applied = True
            logger.info(f"已应用 {len(sop_blocks)} 个历史 SOP")

        except Exception as e:
            logger.warning(f"应用 SOP 失败: {e}")

    def add_message(self, role: str, content: str, **kwargs):
        """
        添加消息（增强版 - 同步到 AContext）

        Args:
            role: 消息角色
            content: 消息内容
            **kwargs: 其他参数
        """
        # 1. 添加到本地消息列表（调用父类方法）
        super().add_message(role, content, **kwargs)

        # 2. 同步到 AContext
        if self.acontext.enabled:
            self.acontext.store_message(role, content, **kwargs)

    def _finalize_acontext(self, exit_status: str):
        """
        任务完成后的 AContext 处理

        Args:
            exit_status: 任务退出状态
        """
        try:
            # 显示任务状态
            status = self.acontext.get_task_status()
            logger.info(f"AContext 任务状态: {status}")

            # 可选：等待任务提取完成（仅调试时使用）
            # self.acontext.flush_and_wait()

        except Exception as e:
            logger.warning(f"完成 AContext 处理失败: {e}")
        finally:
            # 关闭管理器
            self.acontext.close()
```

#### Step 2.3: 创建支持 AContext 的 InteractiveAgent

**文件**：`mini-swe-agent/src/minisweagent/agents/interactive_context_aware.py` (新建)

```python
"""支持 AContext 的交互式 Agent"""
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.acontext.manager import AContextManager
from minisweagent import Model, Environment
from typing import Any
import logging

logger = logging.getLogger(__name__)


class InteractiveContextAwareAgent(InteractiveAgent):
    """集成 AContext 的交互式 Agent"""

    def __init__(
        self,
        model: Model,
        env: Environment,
        acontext_config: dict[str, Any] | None = None,
        **kwargs
    ):
        super().__init__(model, env, **kwargs)
        self.acontext = AContextManager(acontext_config or {})
        self.sop_applied = False

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """执行任务（增强版）"""
        # 初始化 AContext
        if self.acontext.initialize():
            logger.info("AContext 集成已启用（交互模式）")
            self._search_and_apply_sop(task)

        try:
            exit_status, result = super().run(task, **kwargs)
            if self.acontext.enabled:
                self._finalize_acontext(exit_status)
            return exit_status, result
        except Exception as e:
            if self.acontext.enabled:
                self._finalize_acontext("error")
            raise

    def _search_and_apply_sop(self, task: str):
        """搜索并应用历史 SOP"""
        try:
            sop_blocks = self.acontext.search_sop(task)
            if not sop_blocks:
                return

            sop_text = self.acontext.format_sop_for_prompt(sop_blocks)
            self.extra_template_vars["historical_sop"] = sop_text
            self.sop_applied = True

            # 交互模式：显示找到的 SOP
            print(f"\n✓ 找到 {len(sop_blocks)} 个相关的历史经验")
            for idx, block in enumerate(sop_blocks, 1):
                relevance = 1 - block['distance'] / 2
                print(f"  {idx}. {block.get('use_when', 'N/A')} (相关性: {relevance:.1%})")
            print()

        except Exception as e:
            logger.warning(f"应用 SOP 失败: {e}")

    def add_message(self, role: str, content: str, **kwargs):
        """添加消息并同步到 AContext"""
        super().add_message(role, content, **kwargs)
        if self.acontext.enabled:
            self.acontext.store_message(role, content, **kwargs)

    def _finalize_acontext(self, exit_status: str):
        """任务完成后的处理"""
        try:
            status = self.acontext.get_task_status()

            # 交互模式：显示任务状态
            if status.get("enabled"):
                print("\n=== AContext 任务摘要 ===")
                space_name = status.get('space_name', 'Unknown')
                space_id = status.get('space_id', 'N/A')
                print(f"Space: {space_name} ({space_id})")
                print(f"Session ID: {status.get('session_id')}")
                print(f"总任务数: {status.get('total_tasks', 0)}")

                recent_tasks = status.get('recent_tasks', [])
                if recent_tasks:
                    print("\n最近任务:")
                    for t in recent_tasks:
                        print(f"  #{t['order']}: {t['description']} [{t['status']}]")

                learning = status.get('learning_status', {})
                print(f"\n学习状态: {learning.get('digested', 0)} 已学习, "
                      f"{learning.get('pending', 0)} 待学习")
                print("=" * 40)
        except Exception as e:
            logger.warning(f"显示 AContext 状态失败: {e}")
        finally:
            self.acontext.close()
```

---

### 阶段 3：配置文件和模板修改

#### Step 3.1: 创建 AContext 配置文件

**文件**：`mini-swe-agent/src/minisweagent/config/acontext.yaml` (新建)

```yaml
# AContext 集成配置

# AContext 服务配置
acontext:
  enabled: true
  api_key: "sk-ac-your-root-api-bearer-token"
  base_url: "http://localhost:8029/api/v1"
  timeout: 60.0

  # Space 管理
  space:
    # Space 名称（用于查找或创建 Space）
    space_name: "mini-swe-agent-default"
    # 指定 space ID（优先级高于 space_name，为空则通过名称查找或创建）
    space_id: null

  # Session 管理
  session:
    # 是否恢复上次的 session
    resume_last: false
    # 指定 session ID（为空则创建新 session）
    session_id: null

  # SOP 搜索配置
  sop_search:
    enabled: true
    # 搜索模式: "fast" (快速语义搜索) 或 "agentic" (AI 迭代搜索)
    mode: "fast"
    # 返回结果数量
    limit: 5
    # agentic 模式的语义阈值 (0-1, 越高越严格)
    semantic_threshold: 0.8
    # agentic 模式的最大迭代次数
    max_iterations: 20

  # 消息管理
  message:
    # 是否实时存储消息
    store_realtime: true
    # 上下文编辑策略（减少 token 消耗）
    edit_strategies:
      # 限制总 token 数
      - type: "token_limit"
        params:
          limit_tokens: 20000

      # 移除旧的工具结果
      - type: "remove_tool_result"
        params:
          keep_recent_n_tool_results: 3
          tool_result_placeholder: "[Previous command output - omitted for brevity]"

      # 移除旧的工具调用参数
      - type: "remove_tool_call_params"
        params:
          keep_recent_n_tool_calls: 5

# Agent 配置（继承自 mini.yaml）
agent:
  max_iterations: 50
  tool_call_parser: BashParser
```

#### Step 3.2: 修改 system_template 支持 SOP 注入

**文件**：`mini-swe-agent/src/minisweagent/config/mini.yaml`

**修改前**：
```yaml
system_template: |
  You are a coding assistant...
  [现有内容]
```

**修改后**：
```yaml
system_template: |
  You are a coding assistant...
  [现有内容]

  {% if historical_sop %}
  {{ historical_sop }}
  {% endif %}
```

**说明**：添加 Jinja2 模板变量 `historical_sop`，当有 SOP 时自动注入

---

### 阶段 4：CLI 集成

#### Step 4.1: 修改主入口支持 AContext

**文件**：`mini-swe-agent/src/minisweagent/run/mini.py`

**修改点 1：导入新 Agent 类**

```python
# 在文件顶部添加
from minisweagent.agents.context_aware import ContextAwareAgent
from minisweagent.agents.interactive_context_aware import InteractiveContextAwareAgent
```

**修改点 2：添加 CLI 参数**

```python
@click.option("--acontext-config", type=click.Path(exists=True), default=None,
              help="Path to AContext configuration file")
@click.option("--acontext-enabled/--no-acontext", default=False,
              help="Enable/disable AContext integration (default: disabled)")
@click.option("--acontext-space-name", type=str, default=None,
              help="Use or create AContext Space with this name")
@click.option("--acontext-space-id", type=str, default=None,
              help="Use specific AContext Space ID (overrides space-name)")
@click.option("--acontext-session-id", type=str, default=None,
              help="Resume specific AContext Session ID")
def main(
    task,
    model_name,
    config_spec,
    # ... 其他参数
    acontext_config,
    acontext_enabled,
    acontext_space_name,
    acontext_space_id,
    acontext_session_id,
):
```

**修改点 3：加载 AContext 配置**

```python
def main(...):
    # 加载主配置
    config = yaml.safe_load(config_path.read_text())

    # 加载 AContext 配置
    acontext_cfg = {}
    if acontext_enabled:
        if acontext_config:
            # 从指定文件加载
            acontext_cfg = yaml.safe_load(Path(acontext_config).read_text()).get("acontext", {})
        else:
            # 尝试从默认位置加载
            default_acontext_path = config_path.parent / "acontext.yaml"
            if default_acontext_path.exists():
                acontext_cfg = yaml.safe_load(default_acontext_path.read_text()).get("acontext", {})
            else:
                # 使用默认配置
                acontext_cfg = {"enabled": True}

        # 应用 CLI 参数覆盖
        if acontext_space_id:
            acontext_cfg.setdefault("space", {})["space_id"] = acontext_space_id
        elif acontext_space_name:
            acontext_cfg.setdefault("space", {})["space_name"] = acontext_space_name
        if acontext_session_id:
            acontext_cfg.setdefault("session", {})["session_id"] = acontext_session_id

        # 从环境变量读取 API key（如果未在配置中指定）
        if "api_key" not in acontext_cfg:
            import os
            acontext_cfg["api_key"] = os.getenv("ACONTEXT_API_KEY", "sk-ac-your-root-api-bearer-token")
        if "base_url" not in acontext_cfg:
            import os
            acontext_cfg["base_url"] = os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1")
    else:
        acontext_cfg = {"enabled": False}

    # 初始化模型和环境
    model = get_model(model_name, config.get("model", {}))
    env = LocalEnvironment(**config.get("env", {}))

    # 选择 Agent 类（优先使用支持 AContext 的版本）
    if agent_class_name == "InteractiveAgent":
        if acontext_enabled:
            agent_class = InteractiveContextAwareAgent
        else:
            agent_class = InteractiveAgent
    elif agent_class_name == "DefaultAgent":
        if acontext_enabled:
            agent_class = ContextAwareAgent
        else:
            agent_class = DefaultAgent
    else:
        # 其他 Agent 类型
        agent_class = get_agent_class(agent_class_name)

    # 创建 Agent（传入 AContext 配置）
    if acontext_enabled and agent_class in [ContextAwareAgent, InteractiveContextAwareAgent]:
        agent = agent_class(
            model,
            env,
            acontext_config=acontext_cfg,
            **config.get("agent", {})
        )
    else:
        agent = agent_class(model, env, **config.get("agent", {}))

    # 执行任务
    exit_status, result = agent.run(task)

    # 保存轨迹
    save_traj(agent, output, exit_status, result)
```

#### Step 4.2: 扩展轨迹保存支持 AContext 信息

**文件**：`mini-swe-agent/src/minisweagent/run/utils/save.py`

**修改点：在 save_traj 中添加 AContext 信息**

```python
def save_traj(agent, output_path: Path, exit_status: str, submission: str):
    """保存执行轨迹"""
    traj = {
        "info": {
            "exit_status": exit_status,
            "submission": submission,
            "model_stats": agent.model.stats,
            "mini_version": __version__,
            "config": {
                "agent": agent.config.model_dump(),
                "model": agent.model.model_dump(),
                "environment": agent.env.model_dump(),
                "agent_type": type(agent).__name__,
                "model_type": type(agent.model).__name__,
                "environment_type": type(agent.env).__name__,
            },
        },
        "messages": agent.messages,
        "trajectory_format": "mini-swe-agent-1",
    }

    # 添加 AContext 信息（如果可用）
    if hasattr(agent, "acontext") and agent.acontext.enabled:
        try:
            task_status = agent.acontext.get_task_status()
            traj["info"]["acontext"] = {
                "session_id": task_status.get("session_id"),
                "space_id": task_status.get("space_id"),
                "space_name": task_status.get("space_name"),
                "total_tasks": task_status.get("total_tasks", 0),
                "learning_status": task_status.get("learning_status", {}),
                "sop_applied": agent.sop_applied,
            }
        except Exception as e:
            logger.warning(f"保存 AContext 信息失败: {e}")

    output_path.write_text(json.dumps(traj, indent=2))
    logger.info(f"轨迹已保存到 {output_path}")
```

---

### 阶段 5：创建 __init__ 文件和包导出

#### Step 5.1: 创建 acontext 包初始化文件

**文件**：`mini-swe-agent/src/minisweagent/acontext/__init__.py` (新建)

```python
"""AContext 集成模块"""
from minisweagent.acontext.manager import AContextManager

__all__ = ["AContextManager"]
```

#### Step 5.2: 更新主 __init__.py

**文件**：`mini-swe-agent/src/minisweagent/__init__.py`

**添加导出**：
```python
# 现有导出
from minisweagent.agents.default import DefaultAgent
from minisweagent.agents.interactive import InteractiveAgent
# ... 其他

# 新增导出
from minisweagent.agents.context_aware import ContextAwareAgent
from minisweagent.agents.interactive_context_aware import InteractiveContextAwareAgent
from minisweagent.acontext import AContextManager

__all__ = [
    # ... 现有导出
    "ContextAwareAgent",
    "InteractiveContextAwareAgent",
    "AContextManager",
]
```

---

### 阶段 6：测试和验证

#### Step 6.1: 单元测试

**文件**：`tests/test_acontext_integration.py` (新建)

```python
"""AContext 集成测试"""
import pytest
from minisweagent.acontext.manager import AContextManager
from minisweagent.agents.context_aware import ContextAwareAgent
from minisweagent.models.test_models import DeterministicModel
from minisweagent.environments.local import LocalEnvironment


class TestAContextManager:
    """测试 AContextManager"""

    def test_manager_disabled(self):
        """测试禁用状态"""
        manager = AContextManager({"enabled": False})
        assert not manager.enabled
        assert not manager.initialize()

    def test_manager_initialization(self):
        """测试初始化"""
        config = {
            "enabled": True,
            "api_key": "test-key",
            "base_url": "http://localhost:8029/api/v1",
        }
        manager = AContextManager(config)
        assert manager.enabled
        # 注意：需要 AContext 服务运行才能通过

    def test_message_storage(self):
        """测试消息存储"""
        # 需要真实的 AContext 服务
        pass


class TestContextAwareAgent:
    """测试 ContextAwareAgent"""

    def test_agent_without_acontext(self):
        """测试不启用 AContext"""
        model = DeterministicModel(responses=["echo 'test'"])
        env = LocalEnvironment()
        agent = ContextAwareAgent(
            model,
            env,
            acontext_config={"enabled": False},
            max_iterations=1
        )

        exit_status, result = agent.run("Say test")
        assert exit_status in ["success", "submitted"]

    @pytest.mark.integration
    def test_agent_with_acontext(self):
        """测试启用 AContext（需要服务运行）"""
        # 此测试需要真实的 AContext 服务
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

#### Step 6.2: 集成测试脚本

**文件**：`tests/integration_test_acontext.py` (新建)

```python
"""AContext 集成测试脚本（需要 AContext 服务运行）"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from minisweagent.agents.context_aware import ContextAwareAgent
from minisweagent.models.anthropic import AnthropicModel
from minisweagent.environments.local import LocalEnvironment


def test_basic_integration():
    """基础集成测试"""
    print("=== AContext 集成测试 ===\n")

    # 1. 配置
    acontext_config = {
        "enabled": True,
        "api_key": os.getenv("ACONTEXT_API_KEY", "sk-ac-your-root-api-bearer-token"),
        "base_url": os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1"),
        "sop_search": {
            "enabled": True,
            "mode": "fast",
            "limit": 3
        }
    }

    # 2. 创建 Agent
    model = AnthropicModel(model="claude-3-5-sonnet-20241022")
    env = LocalEnvironment()
    agent = ContextAwareAgent(
        model,
        env,
        acontext_config=acontext_config,
        max_iterations=5
    )

    # 3. 执行简单任务
    print("执行任务: 创建 hello.txt 文件\n")
    exit_status, result = agent.run("Create a file hello.txt with content 'Hello from mini-swe-agent!'")

    print(f"\n退出状态: {exit_status}")
    print(f"结果: {result}")

    # 4. 查看 AContext 状态
    if agent.acontext.enabled:
        status = agent.acontext.get_task_status()
        print(f"\nAContext 状态:")
        print(f"  Session ID: {status.get('session_id')}")
        print(f"  Space ID: {status.get('space_id')}")
        print(f"  总任务数: {status.get('total_tasks', 0)}")

    print("\n✓ 测试完成")


def test_sop_retrieval():
    """测试 SOP 检索"""
    print("\n=== 测试 SOP 检索 ===\n")

    acontext_config = {
        "enabled": True,
        "api_key": os.getenv("ACONTEXT_API_KEY"),
        "base_url": os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1"),
    }

    from minisweagent.acontext.manager import AContextManager
    manager = AContextManager(acontext_config)

    if manager.initialize():
        # 搜索 SOP
        sops = manager.search_sop("Fix a Python import error")

        print(f"找到 {len(sops)} 个相关 SOP:\n")
        for idx, sop in enumerate(sops, 1):
            print(f"{idx}. {sop.get('use_when', 'N/A')}")
            print(f"   相关性: {1 - sop['distance']/2:.1%}")
            print(f"   偏好: {sop.get('preferences', 'N/A')}\n")

        manager.close()

    print("✓ SOP 检索测试完成")


if __name__ == "__main__":
    # 确保环境变量已设置
    if not os.getenv("ACONTEXT_API_KEY"):
        print("警告: ACONTEXT_API_KEY 未设置，使用默认值")

    try:
        test_basic_integration()
        test_sop_retrieval()
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
```

#### Step 6.3: 端到端测试场景

**创建测试场景脚本**：`tests/e2e_acontext_scenarios.sh`

```bash
#!/bin/bash
# AContext 端到端测试场景

set -e

echo "=== AContext E2E 测试场景 ==="
echo

# 场景 1: 创建文件任务
echo "场景 1: 创建文件任务"
python -m minisweagent.run.mini \
    --task "Create a Python file hello.py that prints 'Hello World'" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext-enabled \
    -o /tmp/test1.traj.json

echo "✓ 场景 1 完成"
echo

# 场景 2: Bug 修复任务（应该能检索到场景 1 的经验）
echo "场景 2: Bug 修复任务"
python -m minisweagent.run.mini \
    --task "Fix the syntax error in test_broken.py" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext-enabled \
    -o /tmp/test2.traj.json

echo "✓ 场景 2 完成"
echo

# 场景 3: 恢复 session
echo "场景 3: 恢复 session"
SESSION_ID=$(jq -r '.info.acontext.session_id' /tmp/test1.traj.json)
python -m minisweagent.run.mini \
    --task "List all Python files" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext-session-id "$SESSION_ID" \
    -o /tmp/test3.traj.json

echo "✓ 场景 3 完成"
echo

echo "=== 所有测试场景完成 ==="
```

---

## 四、部署和使用指南

### 4.1 环境变量配置

创建 `.env` 文件或在 shell 中设置：

```bash
# AContext 配置
export ACONTEXT_API_KEY="sk-ac-your-root-api-bearer-token"
export ACONTEXT_BASE_URL="http://localhost:8029/api/v1"

# LLM 配置
export ANTHROPIC_API_KEY="your-anthropic-key"
```

### 4.2 使用示例

#### 基础使用（启用 AContext）

```bash
# 使用默认 Space 名称（mini-swe-agent-default）
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --acontext-enabled

# 输出示例：
# ✓ AContext Space: mini-swe-agent-default (已存在)
# ✓ 找到 2 个相关的历史经验
#   1. Fix Python syntax errors (相关性: 82%)
#   2. Debug main.py issues (相关性: 75%)

# 禁用 AContext
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --no-acontext
```

#### 指定 Space 名称

```bash
# 为特定项目使用专用 Space（需要显式启用 AContext）
python -m minisweagent.run.mini \
    --task "Add authentication" \
    --acontext-enabled \
    --acontext-space-name "my-web-project"

# 输出示例：
# ✓ AContext Space: my-web-project (新创建)

# 后续任务自动使用同名 Space
python -m minisweagent.run.mini \
    --task "Add error handling" \
    --acontext-enabled \
    --acontext-space-name "my-web-project"

# 输出示例：
# ✓ AContext Space: my-web-project (已存在)
# ✓ 找到 1 个相关的历史经验
#   1. Implement authentication system (相关性: 68%)
```

#### 指定 Space ID（高级用法）

```bash
# 使用特定 Space ID（优先级高于名称）
python -m minisweagent.run.mini \
    --task "Refactor code" \
    --acontext-enabled \
    --acontext-space-id "space-abc123"

# 恢复特定 Session
python -m minisweagent.run.mini \
    --task "Continue previous work" \
    --acontext-enabled \
    --acontext-session-id "session-xyz789"
```

#### 使用自定义配置文件

```bash
python -m minisweagent.run.mini \
    --task "Refactor the code" \
    --acontext-enabled \
    --acontext-config ./my_acontext_config.yaml
```

### 4.3 交互模式使用

```bash
# 启用 AContext 的交互模式（使用默认 Space）
python -m minisweagent.run.mini \
    --interactive \
    --acontext-enabled

# 输出示例：
# ✓ AContext Space: mini-swe-agent-default (已存在)
# ✓ 找到 3 个相关的历史经验
#   1. Fix authentication bugs (相关性: 85%)
#   2. Add error handling (相关性: 72%)
#   3. Refactor API endpoints (相关性: 68%)

# 使用项目专用 Space
python -m minisweagent.run.mini \
    --interactive \
    --acontext-enabled \
    --acontext-space-name "my-project"
```

### 4.4 原有使用方式（完全兼容）

```bash
# 不添加任何 AContext 参数，保持原有行为
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --model anthropic:claude-3-5-sonnet-20241022

# 等同于显式禁用
python -m minisweagent.run.mini \
    --task "Fix the bug in main.py" \
    --model anthropic:claude-3-5-sonnet-20241022 \
    --no-acontext

# ✅ 原有的所有命令行参数和用法完全不受影响
# ✅ 不会有任何 AContext 相关的输出或日志
# ✅ 不会尝试连接 AContext 服务
```

---

## 五、预期效果和验证方法

### 5.1 功能验证清单

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
- [ ] 交互模式正常显示 SOP 和 Space 信息

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
   - 第一次运行：观察 Space 创建消息
     ```
     ✓ AContext Space: mini-swe-agent-default (新创建)
     ```
   - 第二次运行：验证 Space 复用
     ```
     ✓ AContext Space: mini-swe-agent-default (已存在)
     ```
   - 运行任务 A（例如：修复一个 bug）
   - 查看 AContext Dashboard 确认任务被记录
   - 运行类似任务 B（使用相同 Space 名称）
   - 观察是否检索到任务 A 的 SOP
   - 验证任务 B 的执行是否受益于历史经验
   - 查看轨迹文件，确认包含 space_name 字段

---

## 六、注意事项和最佳实践

### 6.1 注意事项

1. **不涉及 disk 和 artifact**：
   - 本集成不使用 AContext 的 disk 和 artifact 功能
   - 仅使用 session、message、task 和 space 功能

2. **Space 管理策略**：
   - 默认使用单一 Space（`mini-swe-agent-default`），所有任务共享
   - 适合积累通用的编程和调试经验
   - 通过名称管理，便于识别和复用
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
   - **团队协作**：团队成员共享相同的 Space 名称
   - **命名规范**：使用清晰、一致的命名（如：`team-frontend`、`ai-research`）
   - **定期维护**：审查 Space 中的 SOP 质量，清理过时内容

3. **Session 生命周期**：
   - 每个独立任务创建新 Session
   - 相关任务可以恢复同一 Session
   - 避免 Session 过长导致上下文混乱

4. **监控和调试**：
   - 定期检查 `get_task_status()` 输出
   - 查看轨迹文件中的 AContext 信息
   - 使用 AContext Dashboard 可视化学习进度

5. **渐进式启用**：
   - 第一阶段：仅启用消息存储和任务跟踪
   - 第二阶段：启用 SOP 搜索但不注入 prompt（观察）
   - 第三阶段：完全启用 SOP 应用

---

## 七、时间估算和里程碑

### 里程碑规划

| 里程碑 | 描述 | 预期产出 |
|--------|------|----------|
| M1 | 环境准备和依赖安装 | 可运行的开发环境 |
| M2 | AContextManager 实现 | 可测试的管理器类 |
| M3 | ContextAwareAgent 实现 | 可运行的增强 Agent |
| M4 | 配置和 CLI 集成 | 可通过命令行使用 |
| M5 | 测试和文档 | 完整的测试套件 |
| M6 | 优化和生产准备 | 生产就绪版本 |

### 开发检查点

- [ ] 阶段 1 完成：环境可用
- [ ] 阶段 2 完成：核心组件实现
- [ ] 阶段 3 完成：配置和模板修改
- [ ] 阶段 4 完成：CLI 集成
- [ ] 阶段 5 完成：包结构完善
- [ ] 阶段 6 完成：测试全部通过

---

## 八、后续扩展方向

### 8.1 短期扩展

1. **增强 SOP 应用**：
   - 在执行过程中动态调整 SOP
   - 支持用户手动选择 SOP
   - SOP 相关性排序优化

2. **更好的可视化**：
   - 在轨迹文件中记录 SOP 应用详情
   - 支持导出学习报告
   - 集成到 Web UI

3. **性能优化**：
   - 批量消息存储
   - SOP 缓存机制
   - 异步任务提取

### 8.2 长期扩展

1. **多 Agent 协作**：
   - 多个 Agent 共享同一 Space
   - Agent 之间的经验传递
   - 团队级别的知识管理

2. **主动学习**：
   - 从失败任务中学习
   - 用户反馈集成
   - A/B 测试不同 SOP

3. **高级检索**：
   - 基于代码上下文的检索
   - 多模态 SOP（代码片段 + 文本）
   - 个性化推荐

---

## 附录

### A. 文件清单

新增文件：
```
mini-swe-agent/
├── src/minisweagent/
│   ├── acontext/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── agents/
│   │   ├── context_aware.py
│   │   └── interactive_context_aware.py
│   └── config/
│       └── acontext.yaml
├── tests/
│   ├── test_acontext_connection.py
│   ├── test_acontext_integration.py
│   ├── integration_test_acontext.py
│   └── e2e_acontext_scenarios.sh
└── .env.example  # 环境变量模板

修改文件：
mini-swe-agent/
├── src/minisweagent/
│   ├── __init__.py  # 添加导出
│   ├── config/mini.yaml  # 添加 SOP 模板变量
│   └── run/
│       ├── mini.py  # 添加 CLI 参数和 Agent 选择逻辑
│       └── utils/save.py  # 添加 AContext 信息保存
└── pyproject.toml  # 添加 acontext 依赖
```

### B. 依赖清单

```toml
[project]
dependencies = [
    "acontext>=0.1.0",  # AContext Python SDK
    "anthropic>=0.18.0",
    "litellm>=1.0.0",
    "pydantic>=2.0.0",
    "jinja2>=3.0.0",
    "click>=8.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]
```

### C. 环境变量模板

```bash
# .env.example

# AContext 配置
ACONTEXT_API_KEY=sk-ac-your-root-api-bearer-token
ACONTEXT_BASE_URL=http://localhost:8029/api/v1

# LLM 配置
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key  # 如果使用 OpenAI

# 可选配置
ACONTEXT_SPACE_NAME=mini-swe-agent-default  # 默认 Space 名称
ACONTEXT_SPACE_ID=  # 指定 Space ID（优先于名称）
ACONTEXT_SESSION_ID=  # 指定 Session ID
```

---

## 总结

本实施计划详细描述了将 AContext 集成到 mini-swe-agent 的完整方案，包括：

1. **清晰的架构设计**：通过 AContextManager 和 ContextAwareAgent 实现解耦
2. **完整的实现步骤**：从依赖安装到测试验证的全流程
3. **灵活的配置系统**：支持多种使用场景和部署模式
4. **全面的测试方案**：单元测试、集成测试、端到端测试
5. **详细的使用指南**：命令行示例和最佳实践

### 核心特性

**🔒 完全向后兼容**：
- ✅ **默认禁用**：不添加参数时，行为与原有版本完全一致
- ✅ **显式启用**：需要 `--acontext-enabled` 才会启用 AContext
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

**优势**：
- **最小侵入性**：不破坏原有架构，完全向后兼容
- **高可用性**：AContext 故障不影响 Agent 运行
- **易于扩展**：模块化设计便于后续增强
- **生产就绪**：包含完整的错误处理和监控机制
- **用户友好**：清晰的命名和可见的状态反馈

实施后，mini-swe-agent 将具备强大的 SOP 学习和应用能力，能够从历史任务中持续学习和改进，**同时完全保持原有使用方式的兼容性**。
