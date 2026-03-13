from __future__ import annotations

import json
import sqlite3
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.agents.animation_artist import animation_artist_agent
from app.agents.character_designer import character_designer_agent
from app.agents.scriptwriter import scriptwriter_agent
from app.agents.storyboard_artist import storyboard_artist_agent
from app.graph.routing import (
    NODE_ANIMATION_ARTIST,
    NODE_CHARACTER_DESIGNER,
    NODE_SCRIPTWRITER,
    NODE_STORYBOARD_ARTIST,
)
from app.graph.state import ManjuState, create_initial_state
from app.services.intent_router_policy import get_intent_router_policy, normalize_intent_router_policy
from app.services.manager_agent import ManagerAgent
from app.services.review_gateway import ReviewGateway
from app.services.tool_executor import ToolizedAgentExecutor
from app.tools.mcp_client import generate_intent_decision_tool, generate_structured_role_reply_tool

AGENT_SEQUENCE = [
    (NODE_SCRIPTWRITER, scriptwriter_agent, "分镜拆解"),
    (NODE_CHARACTER_DESIGNER, character_designer_agent, "角色生成"),
    (NODE_STORYBOARD_ARTIST, storyboard_artist_agent, "分镜图生成"),
    (NODE_ANIMATION_ARTIST, animation_artist_agent, "视频生成"),
]

NODE_COST = {
    NODE_SCRIPTWRITER: 0.8,
    NODE_CHARACTER_DESIGNER: 2.8,
    NODE_STORYBOARD_ARTIST: 2.6,
    NODE_ANIMATION_ARTIST: 4.2,
}

NODE_ETA = {
    NODE_SCRIPTWRITER: "00:02:40",
    NODE_CHARACTER_DESIGNER: "00:03:30",
    NODE_STORYBOARD_ARTIST: "00:02:50",
    NODE_ANIMATION_ARTIST: "00:04:20",
}

STAGE_TO_INDEX = {stage[0]: idx for idx, stage in enumerate(AGENT_SEQUENCE)}
NODE_LABELS = {stage[0]: stage[2] for stage in AGENT_SEQUENCE}
NODE_ACTORS = {
    NODE_SCRIPTWRITER: "分镜师",
    NODE_CHARACTER_DESIGNER: "角色设计师",
    NODE_STORYBOARD_ARTIST: "分镜画师",
    NODE_ANIMATION_ARTIST: "动画师",
}


def _build_asset_preview(asset: Dict[str, object], kind: str) -> Dict[str, object]:
    source_uri = str(asset.get("uri") or "")
    asset_id = str(asset.get("asset_id") or "preview")
    if source_uri.startswith("http://") or source_uri.startswith("https://"):
        preview_uri = source_uri
    elif kind == "video":
        preview_uri = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
    else:
        preview_uri = f"https://picsum.photos/seed/{asset_id}/960/540"
    return {
        "assetId": asset_id,
        "kind": kind,
        "sourceUri": source_uri,
        "previewUri": preview_uri,
    }


@dataclass
class ProjectRuntime:
    state: ManjuState
    current_index: int = 0
    status: str = "running"
    awaiting_review: bool = False
    step_count: int = 0
    last_advanced_at: float = 0.0
    history: List[str] = field(default_factory=list)
    review_logs: List[Dict[str, str]] = field(default_factory=list)
    chat_logs: List[Dict[str, str]] = field(default_factory=list)
    activity_logs: List[Dict[str, object]] = field(default_factory=list)
    conversation_round: int = 1
    round_history: List[Dict[str, object]] = field(default_factory=list)


class ProjectOrchestrator:
    def __init__(self) -> None:
        self._store: Dict[str, ProjectRuntime] = {}
        self._lock = Lock()
        self._manager_agent = ManagerAgent()
        self._tool_executor = ToolizedAgentExecutor()
        self._review_gateway = ReviewGateway()
        self._json_storage_path = (
            Path(__file__).resolve().parents[1] / "static" / "data" / "projects_runtime.json"
        )
        self._db_path = (
            Path(__file__).resolve().parents[1] / "static" / "data" / "projects_runtime.db"
        )
        with self._lock:
            self._init_db_locked()
            self._load_store_locked()

    def _allowed_chat_intents(self) -> List[str]:
        return [
            "reject_project",
            "approve_review",
            "revise_style",
            "revise_existing",
            "revise_script",
            "new_creation",
            "continue_pipeline",
            "prompt_update",
            "chat_only",
        ]

    def _runtime_intent_router_policy(self, runtime: ProjectRuntime) -> Dict[str, Any]:
        policy = runtime.state.get("intent_router_policy")
        if isinstance(policy, dict):
            normalized = normalize_intent_router_policy(policy)
            runtime.state["intent_router_policy"] = normalized
            return normalized
        default_policy = normalize_intent_router_policy(get_intent_router_policy())
        runtime.state["intent_router_policy"] = default_policy
        return default_policy

    def _serialize_runtime(self, runtime: ProjectRuntime) -> Dict[str, Any]:
        return {
            "state": runtime.state,
            "current_index": runtime.current_index,
            "status": runtime.status,
            "awaiting_review": runtime.awaiting_review,
            "step_count": runtime.step_count,
            "last_advanced_at": runtime.last_advanced_at,
            "history": runtime.history,
            "review_logs": runtime.review_logs,
            "chat_logs": runtime.chat_logs,
            "activity_logs": runtime.activity_logs,
            "conversation_round": runtime.conversation_round,
            "round_history": runtime.round_history,
        }

    def _deserialize_runtime(self, payload: Dict[str, Any]) -> Optional[ProjectRuntime]:
        state = payload.get("state")
        if not isinstance(state, dict):
            return None
        project_id = state.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            return None
        return ProjectRuntime(
            state=state,
            current_index=int(payload.get("current_index", 0)),
            status=str(payload.get("status", "running")),
            awaiting_review=bool(payload.get("awaiting_review", False)),
            step_count=int(payload.get("step_count", 0)),
            last_advanced_at=float(payload.get("last_advanced_at", 0.0)),
            history=list(payload.get("history", [])),
            review_logs=list(payload.get("review_logs", [])),
            chat_logs=list(payload.get("chat_logs", [])),
            activity_logs=list(payload.get("activity_logs", [])),
            conversation_round=max(1, int(payload.get("conversation_round", 1))),
            round_history=list(payload.get("round_history", [])),
        )

    def _db_connect_locked(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self._db_path))
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _init_db_locked(self) -> None:
        connection = self._db_connect_locked()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects_runtime (
                    project_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _load_json_store_locked(self) -> Dict[str, ProjectRuntime]:
        if not self._json_storage_path.exists():
            return {}
        try:
            payload = json.loads(self._json_storage_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        projects = payload.get("projects") if isinstance(payload, dict) else None
        if not isinstance(projects, dict):
            return {}
        loaded: Dict[str, ProjectRuntime] = {}
        for project_id, runtime_payload in projects.items():
            if not isinstance(project_id, str) or not isinstance(runtime_payload, dict):
                continue
            runtime = self._deserialize_runtime(runtime_payload)
            if runtime is not None:
                loaded[project_id] = runtime
        return loaded

    def _persist_store_locked(self) -> None:
        records = [
            (
                project_id,
                json.dumps(self._serialize_runtime(runtime), ensure_ascii=False),
                time.time(),
            )
            for project_id, runtime in self._store.items()
        ]
        connection = self._db_connect_locked()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM projects_runtime")
            if records:
                connection.executemany(
                    """
                    INSERT INTO projects_runtime (project_id, payload, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    records,
                )
            connection.commit()
        finally:
            connection.close()

    def _load_store_locked(self) -> None:
        loaded: Dict[str, ProjectRuntime] = {}
        connection = self._db_connect_locked()
        try:
            rows = connection.execute(
                "SELECT project_id, payload FROM projects_runtime ORDER BY updated_at DESC"
            ).fetchall()
        finally:
            connection.close()
        for project_id, payload_text in rows:
            try:
                runtime_payload = json.loads(payload_text)
            except Exception:
                continue
            if not isinstance(project_id, str) or not isinstance(runtime_payload, dict):
                continue
            runtime = self._deserialize_runtime(runtime_payload)
            if runtime is not None:
                loaded[project_id] = runtime
        if not loaded:
            loaded = self._load_json_store_locked()
            if loaded:
                self._store = loaded
                self._persist_store_locked()
                return
        if loaded:
            self._store = loaded

    def create_project(self, user_prompt: str) -> str:
        with self._lock:
            state = create_initial_state(user_prompt=user_prompt)
            runtime = ProjectRuntime(state=state)
            runtime.state["intent_router_policy"] = normalize_intent_router_policy(get_intent_router_policy())
            self._append_history(runtime, "project_created")
            self._append_chat_log(runtime, "用户", user_prompt)
            self._append_chat_log(runtime, "Agent", self._agent_guidance(runtime))
            self._store[state["project_id"]] = runtime
            self._persist_store_locked()
            return state["project_id"]

    def get_runtime(self, project_id: str) -> Optional[ProjectRuntime]:
        with self._lock:
            return self._store.get(project_id)

    def get_project_intent_router_policy(self, project_id: str) -> Dict[str, Any]:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            policy = self._runtime_intent_router_policy(runtime)
            self._persist_store_locked()
            return json.loads(json.dumps(policy))

    def set_project_intent_router_policy(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            existing = self._runtime_intent_router_policy(runtime)
            merged = {**existing, **(payload if isinstance(payload, dict) else {})}
            merged_rules = dict(existing.get("rules", {}))
            incoming_rules = payload.get("rules") if isinstance(payload, dict) else None
            if isinstance(incoming_rules, dict):
                merged_rules.update(incoming_rules)
            merged["rules"] = merged_rules
            normalized = normalize_intent_router_policy(merged)
            runtime.state["intent_router_policy"] = normalized
            self._persist_store_locked()
            return json.loads(json.dumps(normalized))

    def list_project_ids(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def project_stats(self) -> Dict[str, int]:
        with self._lock:
            status_counts = {
                "running": 0,
                "waiting_review": 0,
                "completed": 0,
                "rejected": 0,
                "failed": 0,
            }
            for runtime in self._store.values():
                status = runtime.status
                if status in status_counts:
                    status_counts[status] += 1
            return {
                "total": len(self._store),
                "running": status_counts["running"],
                "waiting_review": status_counts["waiting_review"],
                "completed": status_counts["completed"],
                "rejected": status_counts["rejected"],
                "failed": status_counts["failed"],
            }

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            if project_id not in self._store:
                return False
            del self._store[project_id]
            self._persist_store_locked()
            return True

    def delete_projects(self, project_ids: List[str]) -> int:
        with self._lock:
            deleted_count = 0
            for project_id in project_ids:
                if project_id in self._store:
                    del self._store[project_id]
                    deleted_count += 1
            if deleted_count > 0:
                self._persist_store_locked()
            return deleted_count

    def _mark_approval_resolved(self, runtime: ProjectRuntime) -> None:
        runtime.state["approval_required"] = False
        runtime.state["approval_stage"] = None
        runtime.state["pending_feedback"] = []
        runtime.awaiting_review = False

    def _next_node(self, runtime: ProjectRuntime) -> Optional[str]:
        if runtime.current_index >= len(AGENT_SEQUENCE):
            return None
        return AGENT_SEQUENCE[runtime.current_index][0]

    def _execution_plan(self, runtime: ProjectRuntime) -> List[Dict[str, object]]:
        plan: List[Dict[str, object]] = []
        timing_ms = runtime.state.get("timing_ms") or {}
        timing_last_ms = runtime.state.get("timing_last_ms") or {}
        for index, (node, _, label) in enumerate(AGENT_SEQUENCE):
            if runtime.status == "completed":
                status = "completed"
            elif runtime.awaiting_review and index == runtime.current_index:
                status = "review"
            elif index < runtime.current_index:
                status = "completed"
            elif index == runtime.current_index:
                status = "next"
            else:
                status = "queued"
            plan.append(
                {
                    "node": node,
                    "label": label,
                    "status": status,
                    "actualDurationMs": int(timing_ms.get(node, 0)),
                    "lastDurationMs": int(timing_last_ms.get(node, 0)),
                    "runCount": runtime.history.count(node),
                }
            )
        return plan

    def _storyboard_table(self, state: ManjuState) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        script_data = state.get("script_data") or {}
        script_history = state.get("script_history") or []
        scene_groups: List[List[Dict[str, Any]]] = []
        if isinstance(script_history, list):
            for item in script_history:
                if not isinstance(item, dict):
                    continue
                scenes = item.get("scenes")
                if isinstance(scenes, list) and scenes:
                    scene_groups.append(scenes)
        if isinstance(script_data, dict):
            scenes = script_data.get("scenes")
            if isinstance(scenes, list) and scenes:
                if not scene_groups or scene_groups[-1] is not scenes:
                    scene_groups.append(scenes)
        shot_index = 1
        for scenes in scene_groups:
            for scene in scenes:
                if not isinstance(scene, dict):
                    continue
                beat = str(
                    scene.get("summary")
                    or scene.get("beat")
                    or scene.get("description")
                    or f"镜头 {shot_index}"
                )
                visual = str(scene.get("visual") or scene.get("composition") or beat)
                dialogue = str(scene.get("dialogue") or scene.get("voiceover") or "")
                duration = str(scene.get("duration") or "3s")
                rows.append(
                    {
                        "shotNo": str(shot_index),
                        "beat": beat[:80],
                        "visual": visual[:100],
                        "dialogue": dialogue[:80],
                        "duration": duration,
                    }
                )
                shot_index += 1
        if rows:
            return rows
        raw = script_data.get("raw")
        resolved_prompt = ""
        if isinstance(raw, dict):
            metadata = raw.get("metadata")
            if isinstance(metadata, dict):
                params = metadata.get("params")
                if isinstance(params, dict):
                    resolved_prompt = str(params.get("resolved_prompt") or "")
        lines = [line.strip(" -•\t") for line in resolved_prompt.splitlines() if line.strip()]
        for index, line in enumerate(lines[:10], start=1):
            rows.append(
                {
                    "shotNo": str(index),
                    "beat": line[:80],
                    "visual": line[:100],
                    "dialogue": "",
                    "duration": "3s",
                }
            )
        if rows:
            return rows
        has_script_attempt = bool(script_data) or bool(script_history) or state.get("route_reason") == NODE_SCRIPTWRITER
        if not has_script_attempt:
            return rows
        prompt = str(state.get("user_prompt") or "").strip()
        core = prompt[:36] if prompt else "主角展开日常行动"
        return [
            {
                "shotNo": "1",
                "beat": f"开场设定：{core}",
                "visual": "全景交代环境与人物关系",
                "dialogue": "",
                "duration": "4s",
            },
            {
                "shotNo": "2",
                "beat": f"动作推进：{core}",
                "visual": "中景呈现关键动作与互动",
                "dialogue": "",
                "duration": "4s",
            },
            {
                "shotNo": "3",
                "beat": f"情绪特写：{core}",
                "visual": "特写强化情绪和细节表达",
                "dialogue": "",
                "duration": "3s",
            },
        ]

    def _execution_plan_summary(self, runtime: ProjectRuntime) -> str:
        plan = self._execution_plan(runtime)
        if runtime.status == "completed":
            return "执行计划已全部完成。"
        if runtime.status == "rejected":
            return "项目已终止，当前计划不再继续。"
        visible = [step for step in plan if step["status"] in {"review", "next", "queued"}][:3]
        if not visible:
            return "当前没有待执行节点。"
        titles = " → ".join(step["label"] for step in visible)
        return f"执行计划：{titles}"

    def _suggested_commands(self, runtime: ProjectRuntime) -> List[str]:
        if runtime.status == "completed":
            return ["重做分镜图，镜头更有张力", "重做视频，动作更流畅", "重做角色，风格更统一"]
        if runtime.status == "rejected":
            return ["新建项目，输入小说文本并开始生成"]
        if runtime.awaiting_review:
            return ["确认风格，继续生成", "修改风格为赛博朋克霓虹", "修改风格为水墨东方"]
        node = self._next_node(runtime)
        if node == NODE_SCRIPTWRITER:
            return ["开始分镜拆解", "重做分镜拆解，节奏更快", "分镜拆解偏电影感"]
        if node == NODE_CHARACTER_DESIGNER:
            return ["开始角色生成", "重做角色，风格更统一", "角色更年轻化，线条更干净"]
        if node == NODE_STORYBOARD_ARTIST:
            return ["开始分镜图生成", "重做分镜图，镜头更有冲击力", "分镜图增加近景特写"]
        if node == NODE_ANIMATION_ARTIST:
            return ["开始视频生成", "重做视频，动作更流畅", "视频节奏更紧凑"]
        return ["开始下一阶段", "重做当前阶段", "按默认参数继续"]

    def _target_node_options(self) -> List[Dict[str, str]]:
        return [
            {"node": NODE_SCRIPTWRITER, "label": "分镜拆解"},
            {"node": NODE_CHARACTER_DESIGNER, "label": "角色设计"},
            {"node": NODE_STORYBOARD_ARTIST, "label": "分镜图"},
            {"node": NODE_ANIMATION_ARTIST, "label": "视频"},
        ]

    def _agent_guidance(self, runtime: ProjectRuntime) -> str:
        plan_summary = self._execution_plan_summary(runtime)
        suggestions = " / ".join(self._suggested_commands(runtime)[:3])
        if runtime.status == "completed":
            return f"成片已生成，可继续提出优化意见。{plan_summary} 建议指令：{suggestions}。"
        if runtime.status == "rejected":
            return f"项目已结束。{plan_summary} 建议指令：{suggestions}。"
        if runtime.awaiting_review:
            return (
                f"角色风格已生成，请先确认风格再进入下一阶段。{plan_summary} "
                f"建议指令：{suggestions}。"
            )
        node = self._next_node(runtime)
        if not node:
            return f"流程已结束，等待你下一步指令。{plan_summary}"
        return (
            f"下一步将执行 {NODE_LABELS.get(node, node)}。"
            f"{plan_summary} 建议指令：{suggestions}。"
        )

    def _agent_chat_reply(self, runtime: ProjectRuntime, user_message: str) -> str:
        preferred_node = self._next_node(runtime)
        decision = self._manager_agent.decide(
            status=runtime.status,
            awaiting_review=runtime.awaiting_review,
            current_index=runtime.current_index,
            sequence=AGENT_SEQUENCE,
            preferred_node=preferred_node,
            history_tail=runtime.history[-6:],
        )
        stage = runtime.state.get("approval_stage") or NODE_LABELS.get(preferred_node or "", "流程调度")
        if decision.action == "execute":
            target_node = decision.next_node or preferred_node
            target_actor = self._actor_name(target_node)
            target_label = NODE_LABELS.get(target_node or "", target_node or "未知节点")
            basis = (
                f"当前状态为{runtime.status}，且未被审核门禁阻断。"
                f"Manager判定执行路径为{target_label}。"
            )
            dispatch = f"我将派工给{target_actor}，执行「{target_label}」。"
            next_commands = " / ".join(self._suggested_commands(runtime)[:3])
            return (
                f"收到，已确认需求：{user_message}。\n"
                f"决策依据：{basis}\n"
                f"派工对象：{dispatch}\n"
                f"下一步指令：{next_commands}"
            )
        if decision.action == "await_review":
            next_commands = " / ".join(self._suggested_commands(runtime)[:3])
            return (
                f"收到，已确认需求：{user_message}。\n"
                f"决策依据：当前处于{stage}审核门禁，需先完成审核。\n"
                f"派工对象：暂不派工，等待项目操作员审批。\n"
                f"下一步指令：{next_commands}"
            )
        if decision.action == "complete":
            return (
                f"收到，已确认需求：{user_message}。\n"
                f"决策依据：全部关键节点已完成，流程进入完成态。\n"
                f"派工对象：无需派工。\n"
                "下一步指令：可提出重做或风格优化指令。"
            )
        return (
            f"收到，已确认需求：{user_message}。\n"
            f"决策依据：当前状态为{runtime.status}，流程保持不变。\n"
            f"派工对象：无。\n"
            f"下一步指令：{' / '.join(self._suggested_commands(runtime)[:3])}"
        )

    def _worker_chat_reply(self, runtime: ProjectRuntime, user_message: str, node_name: str) -> str:
        actor = self._actor_name(node_name)
        node_label = NODE_LABELS.get(node_name, node_name)
        suggestions = self._suggested_commands(runtime)[:3]
        llm_payload = generate_structured_role_reply_tool(
            role=actor,
            user_message=user_message,
            target_label=node_label,
            target_actor=actor,
            suggested_commands=suggestions,
            context=self._agent_guidance(runtime),
            stage="scriptwriter",
        )
        return (
            f"{llm_payload['ack']}\n"
            f"当前动作：{llm_payload['action']}\n"
            f"执行重点：按当前项目风格与目标优先完成该节点。\n"
            f"下一步指令：{llm_payload['next']}"
        )

    def _director_dispatch_reply(self, runtime: ProjectRuntime, user_message: str, node_name: str) -> str:
        actor = self._actor_name(node_name)
        label = NODE_LABELS.get(node_name, node_name)
        suggestions = self._suggested_commands(runtime)[:3]
        llm_payload = generate_structured_role_reply_tool(
            role="导演",
            user_message=user_message,
            target_label=label,
            target_actor=actor,
            suggested_commands=suggestions,
            context=self._agent_guidance(runtime),
            stage="scriptwriter",
        )
        return (
            f"{llm_payload['ack']}\n"
            f"决策依据：{llm_payload['basis']}\n"
            f"派工对象：{llm_payload['dispatch']}\n"
            f"下一步指令：{llm_payload['next']}"
        )

    def _actor_name(self, node_name: Optional[str]) -> str:
        if not node_name:
            return "导演"
        return NODE_ACTORS.get(node_name, node_name)

    def _manager_thought(self, runtime: ProjectRuntime, action: str, next_node: Optional[str]) -> str:
        if action == "await_review":
            stage = runtime.state.get("approval_stage") or "当前阶段"
            return f"检测到审批门禁未解除，需要先进行{stage}审核。"
        if action == "complete":
            return "全部关键节点已执行完成，项目可以进入完成态。"
        if action == "execute":
            node_label = NODE_LABELS.get(next_node or "", next_node or "未知节点")
            return f"当前无阻塞，调度下一个最优节点：{node_label}。"
        return "保持当前状态，等待下一步条件满足。"

    def _manager_reply(self, action: str, next_node: Optional[str]) -> str:
        if action == "execute":
            node_label = NODE_LABELS.get(next_node or "", next_node or "未知节点")
            return f"我将派发任务给{node_label}。"
        if action == "await_review":
            return "当前流程进入审核等待，请先完成审核指令。"
        if action == "complete":
            return "项目流程已全部完成。"
        return "当前流程保持不变。"

    def _tool_thought(self, node_name: str) -> str:
        label = NODE_LABELS.get(node_name, node_name)
        return f"接收到导演调度，开始执行{label}任务并生成产物。"

    def _tool_reply(self, runtime: ProjectRuntime, node_name: str) -> str:
        state = runtime.state
        if node_name == NODE_SCRIPTWRITER:
            scenes = state.get("script_data", {}).get("scenes", [])
            count = len(scenes) if isinstance(scenes, list) else 0
            return f"分镜拆解完成，已生成{count}个镜头段落。"
        if node_name == NODE_CHARACTER_DESIGNER:
            assets = state.get("character_assets", {})
            count = len(assets) if isinstance(assets, dict) else 0
            return f"角色设计完成，已输出{count}个角色资产。"
        if node_name == NODE_STORYBOARD_ARTIST:
            frames = state.get("storyboard_frames", [])
            count = len(frames) if isinstance(frames, list) else 0
            return f"分镜图生成完成，已输出{count}帧关键画面。"
        if node_name == NODE_ANIMATION_ARTIST:
            clips = state.get("video_clips", [])
            count = len(clips) if isinstance(clips, list) else 0
            return f"视频生成完成，已输出{count}段视频素材。"
        return "节点执行完成。"

    def _append_chat_log(self, runtime: ProjectRuntime, role: str, message: str) -> None:
        payload = {
            "role": role,
            "message": message,
            "stage": runtime.state.get("approval_stage") or "",
            "node": runtime.state.get("current_node") or "",
        }
        runtime.chat_logs.append(payload)
        self._append_activity(runtime, "chat", payload)

    def _append_review_log(self, runtime: ProjectRuntime, payload: Dict[str, str]) -> None:
        runtime.review_logs.append(payload)
        self._append_activity(runtime, "review", payload)

    def _append_history(self, runtime: ProjectRuntime, event: str, actor: Optional[str] = None) -> None:
        runtime.history.append(event)
        payload: Dict[str, object] = {"event": event}
        if actor:
            payload["actor"] = actor
        self._append_activity(runtime, "history", payload)

    def _append_activity(self, runtime: ProjectRuntime, kind: str, payload: Dict[str, object]) -> None:
        runtime.activity_logs.append(
            {
                "index": len(runtime.activity_logs),
                "kind": kind,
                "payload": payload,
            }
        )

    def _infer_target_node(self, message: str) -> Optional[str]:
        text = message.lower()
        if "拆解" in message or "小说" in message or "script" in text:
            return NODE_SCRIPTWRITER
        if "角色" in message or "character" in text:
            return NODE_CHARACTER_DESIGNER
        if "分镜图" in message or "storyboard image" in text:
            return NODE_STORYBOARD_ARTIST
        if "分镜" in message or "storyboard" in text:
            return NODE_SCRIPTWRITER
        if "视频" in message or "动画" in message or "animation" in text or "video" in text:
            return NODE_ANIMATION_ARTIST
        return None

    def _contains_any(self, text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _is_new_creation_intent(self, text: str) -> bool:
        lower = text.lower()
        keywords = [
            "新剧本",
            "新的剧本",
            "新故事",
            "新剧情",
            "创建",
            "新建",
            "重新开始",
            "从头开始",
            "开一个新",
            "开个新",
            "重启创作",
            "写一段",
            "写个剧本",
            "写一个剧本",
            "再来一段",
            "new script",
            "new story",
            "create script",
        ]
        return self._contains_any(text, keywords) or self._contains_any(lower, keywords)

    def _control_keywords(self) -> List[str]:
        return [
            "开始下一阶段",
            "开始",
            "继续",
            "继续生成",
            "执行当前阶段",
            "确认",
            "通过",
            "重做",
            "返修",
            "修改",
            "风格",
            "放弃项目",
            "终止项目",
        ]

    def _intent_confidence(self, intent: str) -> float:
        confidence_map = {
            "reject_project": 0.99,
            "approve_review": 0.94,
            "revise_style": 0.93,
            "revise_existing": 0.9,
            "revise_script": 0.9,
            "new_creation": 0.92,
            "continue_pipeline": 0.88,
            "prompt_update": 0.86,
            "chat_only": 0.72,
        }
        return confidence_map.get(intent, 0.7)

    def _llm_refine_intent(
        self,
        runtime: ProjectRuntime,
        text: str,
        rule_intent: str,
        rule_target: Optional[str],
        rule_confidence: float,
    ) -> Dict[str, object]:
        policy = self._runtime_intent_router_policy(runtime)
        rules = policy.get("rules", {}) if isinstance(policy, dict) else {}
        mode = str(rules.get("mode", "hybrid"))
        try:
            llm_min_confidence = float(rules.get("llmMinConfidence", 0.75))
        except Exception:
            llm_min_confidence = 0.75
        llm_min_confidence = max(0.0, min(llm_min_confidence, 1.0))
        try:
            rule_bypass_threshold = float(rules.get("ruleHighConfidenceBypass", 0.91))
        except Exception:
            rule_bypass_threshold = 0.91
        rule_bypass_threshold = max(0.0, min(rule_bypass_threshold, 1.0))
        force_rule_when_awaiting_review = bool(rules.get("forceRuleWhenAwaitingReview", True))
        if mode == "rule_only":
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "policy_rule_only",
                "source": "rule_router_v2",
            }
        if runtime.awaiting_review and force_rule_when_awaiting_review:
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "policy_force_rule_awaiting_review",
                "source": "rule_router_v2",
            }
        if mode != "model_first" and rule_confidence >= rule_bypass_threshold:
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "rule_high_confidence",
                "source": "rule_router_v2",
            }
        if len(text) <= 1:
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "message_too_short",
                "source": "rule_router_v2",
            }
        current_stage = ""
        if 0 <= runtime.current_index < len(AGENT_SEQUENCE):
            current_stage = AGENT_SEQUENCE[runtime.current_index][0]
        model_result = generate_intent_decision_tool(
            user_message=text,
            status=runtime.status,
            awaiting_review=runtime.awaiting_review,
            current_stage=current_stage,
            allowed_intents=self._allowed_chat_intents(),
            available_nodes=list(STAGE_TO_INDEX.keys()),
        )
        model_intent = model_result.get("intent")
        if not isinstance(model_intent, str) or model_intent not in self._allowed_chat_intents():
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "llm_invalid_result",
                "source": "rule_router_v2",
            }
        model_target = model_result.get("target_node")
        if not isinstance(model_target, str) or model_target not in STAGE_TO_INDEX:
            model_target = None
        try:
            model_confidence = float(model_result.get("confidence") or 0.0)
        except Exception:
            model_confidence = 0.0
        model_confidence = max(0.0, min(model_confidence, 1.0))
        if model_confidence < llm_min_confidence:
            return {
                "intent": rule_intent,
                "target": rule_target,
                "confidence": rule_confidence,
                "reason": "llm_low_confidence",
                "source": "rule_router_v2",
            }
        model_reason = str(model_result.get("reason") or "llm_intent")
        return {
            "intent": model_intent,
            "target": model_target,
            "confidence": model_confidence,
            "reason": model_reason,
            "source": "hybrid_router_v3",
        }

    def _classify_chat_intent(self, runtime: ProjectRuntime, text: str) -> Dict[str, object]:
        selected_intent = "chat_only"
        selected_target: Optional[str] = None
        reason = "default_chat_fallback"
        if self._contains_any(text, ["放弃项目", "终止项目"]):
            selected_intent = "reject_project"
            reason = "matched_reject_keywords"
        elif runtime.awaiting_review and self._contains_any(text, ["确认风格", "确认", "通过", "继续"]):
            selected_intent = "approve_review"
            reason = "awaiting_review_with_approve_keywords"
        elif runtime.awaiting_review and self._contains_any(text, ["修改风格", "风格", "改成", "换成"]):
            selected_intent = "revise_style"
            selected_target = NODE_CHARACTER_DESIGNER
            reason = "awaiting_review_with_style_keywords"
        elif self._contains_any(text, ["重做", "返修", "修改"]):
            selected_intent = "revise_existing"
            selected_target = self._infer_target_node(text)
            reason = "matched_revise_keywords"
        elif (
            not runtime.awaiting_review
            and runtime.current_index == STAGE_TO_INDEX[NODE_CHARACTER_DESIGNER]
            and self._contains_any(text, ["电影感", "镜头", "运镜", "构图", "节奏", "分镜"])
        ):
            selected_intent = "revise_script"
            selected_target = NODE_SCRIPTWRITER
            reason = "character_stage_with_script_feedback"
        elif self._is_new_creation_intent(text):
            selected_intent = "new_creation"
            selected_target = NODE_SCRIPTWRITER
            reason = "matched_new_creation_keywords"
        elif (
            not runtime.awaiting_review
            and self._contains_any(text, ["开始下一阶段", "开始", "继续", "继续生成", "执行当前阶段"])
        ):
            selected_intent = "continue_pipeline"
            selected_target = self._next_node(runtime) or NODE_SCRIPTWRITER
            reason = "matched_continue_keywords"
        elif (
            not runtime.awaiting_review
            and runtime.current_index == STAGE_TO_INDEX[NODE_SCRIPTWRITER]
            and not self._contains_any(text, self._control_keywords())
        ):
            selected_intent = "prompt_update"
            selected_target = NODE_SCRIPTWRITER
            reason = "script_stage_free_text_prompt"
        base_result = {
            "intent": selected_intent,
            "target": selected_target,
            "confidence": self._intent_confidence(selected_intent),
            "reason": reason,
            "source": "rule_router_v2",
        }
        return self._llm_refine_intent(
            runtime=runtime,
            text=text,
            rule_intent=str(base_result["intent"]),
            rule_target=base_result["target"] if isinstance(base_result["target"], str) else None,
            rule_confidence=float(base_result["confidence"]),
        )

    def _start_new_creation_cycle(self, runtime: ProjectRuntime, prompt: str, operator_id: str) -> None:
        previous_round_record = {
            "round": runtime.conversation_round,
            "prompt": runtime.state.get("user_prompt", ""),
            "status": runtime.status,
            "stepCount": runtime.step_count,
            "endedAt": time.time(),
        }
        runtime.round_history.append(previous_round_record)
        runtime.conversation_round += 1
        runtime.state["user_prompt"] = prompt
        runtime.state["current_node"] = ""
        runtime.state["route_reason"] = None
        runtime.state["pending_feedback"] = []
        runtime.state["approval_required"] = False
        runtime.state["approval_stage"] = None
        runtime.state["retry_count_by_node"] = {}
        runtime.state["iteration_count"] = 0
        runtime.state["errors"] = []
        runtime.current_index = STAGE_TO_INDEX[NODE_SCRIPTWRITER]
        runtime.status = "running"
        runtime.awaiting_review = False
        runtime.step_count = 0
        runtime.last_advanced_at = 0.0
        self._append_review_log(
            runtime,
            {
                "action": "restart",
                "operator_id": operator_id,
                "stage": "script",
                "issue_type": "chat_new_creation",
                "priority": "high",
                "message": prompt,
                "target_node": NODE_SCRIPTWRITER,
            },
        )
        self._append_history(runtime, "chat_new_cycle_started")

    def submit_review(
        self,
        project_id: str,
        action: str,
        target_node: Optional[str],
        message: Optional[str],
        stage: Optional[str] = None,
        issue_type: Optional[str] = None,
        priority: str = "medium",
        operator_id: str = "anonymous",
    ) -> ProjectRuntime:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            if action in {"approve", "revise", "reject"} and not runtime.awaiting_review:
                raise ValueError("review_not_required")
            if action == "approve":
                resolved_stage = stage or runtime.state.get("approval_stage") or ""
                self._mark_approval_resolved(runtime)
                runtime.current_index = min(runtime.current_index + 1, len(AGENT_SEQUENCE))
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "approve",
                        "operator_id": operator_id,
                        "stage": resolved_stage,
                        "issue_type": issue_type or "manual_review",
                        "priority": priority,
                        "message": message or "",
                    },
                )
                self._append_history(runtime, "review_approved")
            elif action == "revise":
                if not target_node or target_node not in STAGE_TO_INDEX:
                    raise ValueError("invalid_target_node")
                runtime.current_index = STAGE_TO_INDEX[target_node]
                self._mark_approval_resolved(runtime)
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "revise",
                        "operator_id": operator_id,
                        "stage": stage or runtime.state.get("approval_stage") or "",
                        "issue_type": issue_type or "manual_feedback",
                        "priority": priority,
                        "message": message or "",
                        "target_node": target_node,
                    },
                )
                self._append_history(runtime, f"review_revise:{target_node}")
            elif action == "reject":
                runtime.status = "rejected"
                runtime.awaiting_review = False
                runtime.state["approval_required"] = False
                runtime.state["approval_stage"] = None
                self._append_review_log(
                    runtime,
                    {
                        "action": "reject",
                        "operator_id": operator_id,
                        "stage": stage or "",
                        "issue_type": issue_type or "manual_reject",
                        "priority": priority,
                        "message": message or "rejected_by_user",
                    },
                )
                runtime.state["errors"].append(
                    {"node": "Director_Agent", "error": message or "rejected_by_user"}
                )
                self._append_history(runtime, "review_rejected")
            else:
                raise ValueError("invalid_action")
            self._persist_store_locked()
            return runtime

    def chat_and_operate(self, project_id: str, message: str, operator_id: str = "anonymous") -> ProjectRuntime:
        text = (message or "").strip()
        if not text:
            raise ValueError("empty_message")
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            assistant_target_node: Optional[str] = None
            director_dispatch_required = False
            self._append_chat_log(runtime, operator_id, text)
            intent_result = self._classify_chat_intent(runtime, text)
            intent = str(intent_result.get("intent") or "chat_only")
            confidence = float(intent_result.get("confidence") or 0.0)
            reason = str(intent_result.get("reason") or "")
            source = str(intent_result.get("source") or "rule_router_v2")
            self._append_activity(
                runtime,
                "intent_router",
                {
                    "actor": "意图路由",
                    "intent": intent,
                    "confidence": confidence,
                    "reason": reason,
                    "source": source,
                    "round": runtime.conversation_round,
                },
            )
            if intent == "reject_project":
                runtime.status = "rejected"
                runtime.awaiting_review = False
                runtime.state["approval_required"] = False
                runtime.state["approval_stage"] = None
                self._append_review_log(
                    runtime,
                    {
                        "action": "reject",
                        "operator_id": operator_id,
                        "stage": runtime.state.get("approval_stage") or "",
                        "issue_type": "chat_reject",
                        "priority": "high",
                        "message": text,
                    },
                )
                runtime.state["errors"].append({"node": "Director_Agent", "error": text})
                self._append_history(runtime, "chat_rejected")
            elif intent == "new_creation":
                self._start_new_creation_cycle(runtime, text, operator_id)
                assistant_target_node = NODE_SCRIPTWRITER
                director_dispatch_required = True
            elif intent == "prompt_update":
                runtime.state["user_prompt"] = text
                runtime.state["errors"] = []
                runtime.current_index = STAGE_TO_INDEX[NODE_SCRIPTWRITER]
                runtime.status = "running"
                runtime.awaiting_review = False
                runtime.state["approval_required"] = False
                runtime.state["approval_stage"] = None
                self._append_history(runtime, "chat_update_prompt")
                assistant_target_node = NODE_SCRIPTWRITER
                director_dispatch_required = True
            elif intent == "revise_script":
                runtime.state["global_style"]["script_feedback"] = text
                runtime.current_index = STAGE_TO_INDEX[NODE_SCRIPTWRITER]
                self._mark_approval_resolved(runtime)
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "revise",
                        "operator_id": operator_id,
                        "stage": "script",
                        "issue_type": "chat_script_feedback",
                        "priority": "high",
                        "message": text,
                        "target_node": NODE_SCRIPTWRITER,
                    },
                )
                self._append_history(runtime, "chat_revise_script")
                assistant_target_node = NODE_SCRIPTWRITER
                director_dispatch_required = True
            elif intent == "approve_review":
                resolved_stage = runtime.state.get("approval_stage") or ""
                self._mark_approval_resolved(runtime)
                runtime.current_index = min(runtime.current_index + 1, len(AGENT_SEQUENCE))
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "approve",
                        "operator_id": operator_id,
                        "stage": resolved_stage,
                        "issue_type": "chat_review",
                        "priority": "medium",
                        "message": text,
                    },
                )
                self._append_history(runtime, "chat_approved")
                assistant_target_node = self._next_node(runtime)
                director_dispatch_required = assistant_target_node is not None
            elif intent == "revise_style":
                runtime.state["global_style"]["user_feedback"] = text
                runtime.current_index = STAGE_TO_INDEX[NODE_CHARACTER_DESIGNER]
                self._mark_approval_resolved(runtime)
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "revise",
                        "operator_id": operator_id,
                        "stage": "style",
                        "issue_type": "chat_style_feedback",
                        "priority": "high",
                        "message": text,
                        "target_node": NODE_CHARACTER_DESIGNER,
                    },
                )
                self._append_history(runtime, "chat_revise_style")
                assistant_target_node = NODE_CHARACTER_DESIGNER
                director_dispatch_required = True
            elif intent == "revise_existing":
                target = intent_result.get("target")
                if not isinstance(target, str) or target not in STAGE_TO_INDEX:
                    target = self._next_node(runtime) or NODE_STORYBOARD_ARTIST
                runtime.current_index = STAGE_TO_INDEX[target]
                self._mark_approval_resolved(runtime)
                runtime.status = "running"
                self._append_review_log(
                    runtime,
                    {
                        "action": "revise",
                        "operator_id": operator_id,
                        "stage": runtime.state.get("approval_stage") or "",
                        "issue_type": "chat_feedback",
                        "priority": "high",
                        "message": text,
                        "target_node": target,
                    },
                )
                self._append_history(runtime, f"chat_revise:{target}")
                assistant_target_node = target
                director_dispatch_required = True
            elif intent == "continue_pipeline":
                runtime.status = "running"
                target = intent_result.get("target")
                if not isinstance(target, str) or target not in STAGE_TO_INDEX:
                    target = self._next_node(runtime) or NODE_SCRIPTWRITER
                assistant_target_node = target
                director_dispatch_required = True
            elif runtime.status not in {"completed", "rejected", "failed"}:
                runtime.status = "running"
            if assistant_target_node:
                if director_dispatch_required:
                    self._append_chat_log(
                        runtime,
                        "导演",
                        self._director_dispatch_reply(runtime, text, assistant_target_node),
                    )
                assistant_message = self._worker_chat_reply(runtime, text, assistant_target_node)
                self._append_chat_log(runtime, self._actor_name(assistant_target_node), assistant_message)
            else:
                assistant_message = self._agent_chat_reply(runtime, text)
                self._append_chat_log(runtime, "导演", assistant_message)
            self._persist_store_locked()
            return runtime

    def advance(self, project_id: str, force: bool = False) -> ProjectRuntime:
        selected_index: Optional[int] = None
        node_name: Optional[str] = None
        handler = None
        execute_state: Optional[ManjuState] = None
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            if runtime.status in {"completed", "rejected", "failed"}:
                self._persist_store_locked()
                return runtime
            now = time.time()
            if not force and now - runtime.last_advanced_at < 1.2:
                self._persist_store_locked()
                return runtime
            runtime.last_advanced_at = now
            preferred_node = None
            if runtime.current_index < len(AGENT_SEQUENCE):
                preferred_node = AGENT_SEQUENCE[runtime.current_index][0]
            decision = self._manager_agent.decide(
                status=runtime.status,
                awaiting_review=runtime.awaiting_review,
                current_index=runtime.current_index,
                sequence=AGENT_SEQUENCE,
                preferred_node=preferred_node,
                history_tail=runtime.history[-6:],
            )
            self._append_activity(
                runtime,
                "manager_decision",
                {
                    "actor": "导演",
                    "action": decision.action,
                    "next_node": decision.next_node,
                    "reason": decision.reason,
                    "thought": self._manager_thought(runtime, decision.action, decision.next_node),
                    "reply": self._manager_reply(decision.action, decision.next_node),
                    "metadata": decision.metadata,
                },
            )
            if decision.action == "await_review":
                runtime.status = "waiting_review"
                self._persist_store_locked()
                return runtime
            if decision.action == "complete":
                runtime.status = "completed"
                runtime.awaiting_review = False
                runtime.current_index = len(AGENT_SEQUENCE)
                self._persist_store_locked()
                return runtime
            if decision.action != "execute" or not decision.next_node:
                self._persist_store_locked()
                return runtime
            selected_index = STAGE_TO_INDEX.get(decision.next_node, runtime.current_index)
            node_name, handler, _ = AGENT_SEQUENCE[selected_index]
            runtime.current_index = selected_index
            runtime.awaiting_review = False
            runtime.status = "running"
            runtime.state["current_node"] = node_name
            execute_state = deepcopy(runtime.state)
            self._persist_store_locked()
        try:
            execute_started_at = time.perf_counter()
            execution = self._tool_executor.execute(
                node_name=node_name,
                handler=handler,
                state=execute_state,
            )
            elapsed_ms = int((time.perf_counter() - execute_started_at) * 1000)
        except Exception as exc:
            with self._lock:
                runtime = self._store.get(project_id)
                if runtime is None:
                    raise KeyError(project_id)
                runtime.status = "failed"
                runtime.awaiting_review = False
                runtime.state["errors"].append({"node": node_name, "error": str(exc)})
                self._persist_store_locked()
                return runtime
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            runtime.state = execution.state
            timing_ms = runtime.state.setdefault("timing_ms", {})
            timing_ms[node_name] = int(timing_ms.get(node_name, 0)) + max(elapsed_ms, 0)
            timing_last_ms = runtime.state.setdefault("timing_last_ms", {})
            timing_last_ms[node_name] = max(elapsed_ms, 0)
            self._append_activity(
                runtime,
                "tool_execution",
                {
                    **execution.metadata,
                    "actor": self._actor_name(node_name),
                    "thought": self._tool_thought(node_name),
                    "reply": self._tool_reply(runtime, node_name),
                },
            )
            self._append_chat_log(runtime, self._actor_name(node_name), self._tool_reply(runtime, node_name))
            runtime.current_index = selected_index
            runtime.step_count += 1
            self._append_history(runtime, node_name, actor=self._actor_name(node_name))
            runtime.state["cost_usage"][node_name] = runtime.state["cost_usage"].get(
                node_name, 0.0
            ) + NODE_COST[node_name]
            gateway_decision = self._review_gateway.evaluate_after_execute(
                node_name=node_name,
                current_index=runtime.current_index,
                total_nodes=len(AGENT_SEQUENCE),
                state=runtime.state,
            )
            self._append_activity(
                runtime,
                "review_gateway",
                {
                    "actor": "审核网关",
                    "status": gateway_decision.status,
                    "awaiting_review": gateway_decision.awaiting_review,
                    "next_index": gateway_decision.next_index,
                    "reason": gateway_decision.reason,
                    "thought": "根据审核策略评估成本、质量与风险门禁。",
                    "reply": f"网关判定为{gateway_decision.status}。",
                    "metadata": gateway_decision.metadata,
                },
            )
            runtime.awaiting_review = gateway_decision.awaiting_review
            runtime.status = gateway_decision.status
            runtime.current_index = gateway_decision.next_index
            if runtime.state["iteration_count"] > runtime.state["max_iterations"]:
                runtime.status = "failed"
                runtime.state["errors"].append(
                    {"node": "Director_Agent", "error": "max_iterations_exceeded"}
                )
            self._persist_store_locked()
            return runtime

    def snapshot(self, project_id: str) -> Dict[str, object]:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            state = runtime.state
            current_node = state.get("current_node") or AGENT_SEQUENCE[0][0]
            current_stage_name = "已完成" if runtime.status == "completed" else "Queued"
            if runtime.status != "completed" and runtime.current_index < len(AGENT_SEQUENCE):
                current_stage_name = AGENT_SEQUENCE[runtime.current_index][2]
            if runtime.awaiting_review and state.get("approval_stage"):
                current_stage_name = f"{state['approval_stage'].title()} Review"
            quality_pass = 4 if runtime.status != "completed" else 5
            quality_total = 5
            render_cost = round(sum(state["cost_usage"].values()), 2)
            eta = NODE_ETA.get(current_node, "00:00:20")
            timing_ms = state.get("timing_ms") or {}
            timing_last_ms = state.get("timing_last_ms") or {}
            node_metrics = []
            for idx, (node_name, _, display_name) in enumerate(AGENT_SEQUENCE):
                run_count = runtime.history.count(node_name)
                if runtime.status == "completed":
                    node_status = "completed"
                elif runtime.awaiting_review and idx == runtime.current_index:
                    node_status = "review"
                elif idx < runtime.current_index:
                    node_status = "completed"
                elif idx == runtime.current_index:
                    node_status = "running"
                else:
                    node_status = "queued"
                node_metrics.append(
                    {
                        "node": node_name,
                        "label": display_name,
                        "status": node_status,
                        "runCount": run_count,
                        "cost": round(state["cost_usage"].get(node_name, 0.0), 2),
                        "durationMs": int(timing_ms.get(node_name, 0)),
                        "lastDurationMs": int(timing_last_ms.get(node_name, 0)),
                    }
                )
            assets = {
                "scriptReady": bool(state.get("script_data")),
                "styleReady": bool(state.get("global_style")),
                "characterCount": len(state.get("character_assets", {})),
                "storyboardCount": len(state.get("storyboard_frames", [])),
                "videoCount": len(state.get("video_clips", [])),
                "audioCount": len(state.get("audio_tracks", {})),
                "finalVideoUri": (
                    state["final_video"]["uri"] if state.get("final_video") else None
                ),
            }
            character_gallery = [
                _build_asset_preview(asset, "character")
                for asset in state.get("character_assets", {}).values()
            ]
            storyboard_gallery = [
                _build_asset_preview(asset, "storyboard")
                for asset in state.get("storyboard_frames", [])
            ]
            video_gallery = [
                _build_asset_preview(asset, "video")
                for asset in state.get("video_clips", [])
            ]
            if state.get("final_video"):
                video_gallery.append(_build_asset_preview(state["final_video"], "video"))
            asset_gallery = {
                "characters": character_gallery,
                "storyboards": storyboard_gallery,
                "videos": video_gallery,
            }
            execution_plan = self._execution_plan(runtime)
            suggested_commands = self._suggested_commands(runtime)
            intent_router_policy = self._runtime_intent_router_policy(runtime)
            intent_logs = [
                item["payload"]
                for item in runtime.activity_logs
                if item.get("kind") == "intent_router" and isinstance(item.get("payload"), dict)
            ]
            return {
                "projectId": state["project_id"],
                "prompt": state["user_prompt"],
                "stage": current_stage_name,
                "mode": "Human-in-the-loop",
                "status": runtime.status,
                "qualityPass": quality_pass,
                "qualityTotal": quality_total,
                "renderCost": render_cost,
                "eta": eta,
                "approvalRequired": runtime.awaiting_review,
                "approvalStage": state.get("approval_stage"),
                "currentNode": current_node,
                "finalVideoUri": (
                    state["final_video"]["uri"] if state.get("final_video") else None
                ),
                "assets": assets,
                "assetGallery": asset_gallery,
                "storyboardTable": self._storyboard_table(state),
                "nodeMetrics": node_metrics,
                "latestReview": runtime.review_logs[-1] if runtime.review_logs else None,
                "reviewLogs": list(runtime.review_logs),
                "chatLogs": list(runtime.chat_logs),
                "activityLogs": list(runtime.activity_logs),
                "executionPlan": execution_plan,
                "executionPlanSummary": self._execution_plan_summary(runtime),
                "suggestedCommands": suggested_commands,
                "targetNodeOptions": self._target_node_options(),
                "conversationRound": runtime.conversation_round,
                "roundHistory": list(runtime.round_history),
                "intentRouterPolicy": intent_router_policy,
                "intentLogs": intent_logs[-20:],
                "history": list(runtime.history),
                "errors": list(state["errors"]),
            }

    def sse_event(self, project_id: str) -> str:
        payload = self.snapshot(project_id)
        return f"event: snapshot\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


orchestrator = ProjectOrchestrator()
