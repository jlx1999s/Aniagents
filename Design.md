# 漫剧生成平台 (Manju Platform) - 最优实践设计文档

<project_context>
## 1. 项目目标与边界
本项目是一个基于 LangGraph 与 MCP 的多 Agent 漫剧生成平台，目标是将一句话创意稳定转化为可发布的视频成片。

平台必须同时满足以下约束：
- 支持人工介入（Human-in-the-loop）与可控重绘
- 支持失败重试、断点恢复、任务追踪
- 保证角色一致性、分镜一致性与音画同步
- 可观测（质量、耗时、成本）并可持续优化
</project_context>

<tech_stack>
## 2. 技术栈与工程约束
- **核心语言**: Python 3.11+
- **Agent 编排**: LangGraph, LangChain Core
- **工具协议**: Model Context Protocol (MCP)
- **服务层**: FastAPI + SSE（进度流与人工审批）
- **数据模型**: Pydantic v2 + TypedDict（图状态）
- **任务系统**: 推荐接入 Redis + Celery/RQ（用于耗时渲染与异步任务）
- **存储**: 对象存储（S3/OSS） + PostgreSQL（元数据）+ Redis（短期状态）
</tech_stack>

<architecture>
## 3. 全局状态最优实践 (Graph State)
图状态不要只存 URL，必须包含产物版本、质量结果与执行元数据，便于回溯和重跑。

```python
from typing import TypedDict, List, Dict, Any, Optional, Literal

class FeedbackItem(TypedDict):
    stage: Literal[
        "script", "style", "character", "storyboard", "animation", "audio", "compositor"
    ]
    issue_type: str
    message: str
    target_node: str
    priority: Literal["low", "medium", "high"]
    round_id: int

class AssetMeta(TypedDict):
    asset_id: str
    uri: str
    version: int
    seed: Optional[int]
    model_name: str
    params: Dict[str, Any]
    qa_score: Optional[float]

class ManjuState(TypedDict):
    project_id: str
    user_prompt: str
    current_node: str
    route_reason: Optional[str]

    script_data: Dict[str, Any]
    global_style: Dict[str, Any]
    character_assets: Dict[str, AssetMeta]
    storyboard_frames: List[AssetMeta]
    video_clips: List[AssetMeta]
    audio_tracks: Dict[str, AssetMeta]
    final_video: Optional[AssetMeta]

    pending_feedback: List[FeedbackItem]
    approval_required: bool
    approval_stage: Optional[str]

    retry_count_by_node: Dict[str, int]
    max_retry_by_node: Dict[str, int]
    iteration_count: int
    max_iterations: int

    cost_usage: Dict[str, float]
    timing_ms: Dict[str, int]
    errors: List[Dict[str, Any]]
```
</architecture>

<agent_definitions>
## 4. 节点定义（开发一致性版）
采用 8 个图节点，确保“节点定义”和“路由定义”完全一致。

1. **Director_Agent**
   - 职责：路由中枢、人工审批入口、反馈解析、重试判定、失败降级决策。
2. **Scriptwriter_Agent**
   - 职责：输出结构化剧本（场景、角色、对白、镜头意图、时长建议）。
3. **Art_Director_Agent**
   - 职责：产出风格规范（色板、镜头语言、材质、光照、负面词模板）。
4. **Character_Designer_Agent**
   - 职责：生成角色设定图与一致性特征（seed/reference embedding）。
5. **Storyboard_Artist_Agent**
   - 职责：按镜头生成分镜，绑定角色与台词，输出镜头级参数。
6. **Animation_Artist_Agent**
   - 职责：分镜转视频片段，保持角色与构图连续性。
7. **Sound_Director_Agent**
   - 职责：生成配音、音效、BGM，并输出时间轴对齐信息。
8. **Compositor_Agent**
   - 职责：合成音视频，完成字幕/混音/响度规范化并输出成片。
</agent_definitions>

<workflow_routing>
## 5. 路由与重绘最优实践
推荐主路径：

1. `START -> Director -> Scriptwriter -> Art_Director -> Character_Designer`
2. `Character_Designer -> Director`（人工审批点 A）
3. 审批通过：`Director -> Storyboard_Artist -> Director`（人工审批点 B）
4. 审批通过：`Director -> (Animation_Artist || Sound_Director) -> Compositor -> Director`
5. 最终审批通过：`Director -> END`

重绘与重编策略：
- `pending_feedback` 为空：进入下一阶段
- `pending_feedback` 非空：Director 根据 `target_node` 回路到指定节点
- 单节点超过 `max_retry_by_node[node]`：触发降级策略（换模型/降低分辨率/缩短镜头）
- `iteration_count > max_iterations`：强制终止并返回可解释错误
</workflow_routing>

<human_in_loop>
## 6. 人工介入与反馈结构化
必须把人工反馈从“自由文本”升级为“结构化反馈”：

- **输入格式**：`stage + issue_type + message + target_node + priority`
- **解析策略**：规则优先（关键词映射）+ LLM 补充
- **审批动作**：`approve` / `revise` / `reject`
- **审计要求**：每次审批记录 `operator_id`、时间戳、前后版本差异

关键词映射示例：
- “角色衣服不对” -> `target_node=Character_Designer_Agent`
- “镜头顺序不流畅” -> `target_node=Storyboard_Artist_Agent`
- “口型对不上” -> `target_node=Animation_Artist_Agent`
</human_in_loop>

<mcp_integration>
## 7. MCP 工具集成规范
Agent 只做决策，不写第三方 API 细节。所有外部能力统一走 MCP Tool 层。

最低工具集合：
- `generate_script_tool`
- `generate_image_tool`
- `generate_video_tool`
- `synthesize_tts_tool`
- `generate_bgm_tool`
- `compose_timeline_tool`
- `quality_check_tool`

工具返回必须统一：
- `status`、`result_uri`、`metadata`、`cost`、`latency_ms`、`error`
</mcp_integration>

<quality_gates>
## 8. 质量门禁（必须落地）
每一阶段必须有可执行的自动检查，未通过不得进入下一阶段。

- **角色一致性**：同角色跨镜头 embedding 相似度阈值
- **文本一致性**：台词与字幕字数、标点、时间轴一致
- **音频质量**：响度标准化（LUFS）、削波检测、静音段检测
- **视频质量**：分辨率/帧率/时长阈值、黑帧检测、抖动检测
- **成片检查**：音画对齐、片头片尾完整性、文件可播放性
</quality_gates>

<observability>
## 9. 可观测与成本治理
必须把“效果问题”与“成本问题”可视化，否则平台无法持续优化。

- 记录每节点成功率、平均耗时、重试率、失败原因 TopN
- 记录每次生成 token 消耗、模型调用成本、素材渲染成本
- 为每个 `project_id` 提供执行轨迹（trace_id）
- 提供项目级仪表盘：质量分、耗时分布、成本构成
</observability>

<security>
## 10. 安全与合规
- 密钥全部放入环境变量或密钥管理系统，不落盘
- 外部素材 URL 需签名和过期策略
- 用户上传素材需病毒扫描与类型校验
- 审批与下载接口必须有鉴权和项目级权限隔离
</security>

<project_structure>
## 11. 推荐工程目录（第一阶段）
```text
app/
  api/
    routers/
    schemas/
  graph/
    graph.py
    state.py
    routing.py
    checkpoints.py
  agents/
    director.py
    scriptwriter.py
    art_director.py
    character_designer.py
    storyboard_artist.py
    animation_artist.py
    sound_director.py
    compositor.py
  tools/
    mcp_client.py
    adapters/
  services/
    qa_service.py
    asset_service.py
    task_service.py
  infra/
    config.py
    logger.py
tests/
```
</project_structure>

<task_for_ai>
## 12. 开发准备任务（按优先级）
1. 创建 `app/graph/state.py`，先落地强类型 `ManjuState` 与反馈模型。
2. 创建 `app/graph/routing.py`，实现 Director 的条件路由与重试保护。
3. 创建 `app/graph/graph.py`，注册全部节点、并行边与 Checkpointer。
4. 为每个 Agent 创建空壳函数，统一输入输出契约。
5. 接入最小 MCP mock 工具集，先跑通完整流程。
6. 增加最小化测试：路由测试、反馈回路测试、最大迭代保护测试。
</task_for_ai>
