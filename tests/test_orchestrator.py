import unittest
from unittest.mock import patch

from app.graph.routing import NODE_CHARACTER_DESIGNER, NODE_STORYBOARD_ARTIST
from app.graph.state import create_initial_state
from app.services.manager_agent import ManagerAgent
from app.services.orchestrator import ProjectOrchestrator, orchestrator
from app.services.intent_router_policy import get_intent_router_policy, set_intent_router_policy
from app.services.review_gateway_policy import (
    get_review_gateway_policy,
    set_review_gateway_policy,
)
from app.services.tool_executor import ToolizedAgentExecutor


class OrchestratorTests(unittest.TestCase):
    def test_project_can_progress_and_review(self):
        project_id = orchestrator.create_project("测试 prompt")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertIn(runtime.status, {"running", "waiting_review"})
        for _ in range(8):
            runtime = orchestrator.advance(project_id, force=True)
            if runtime.awaiting_review:
                break
        self.assertTrue(runtime.awaiting_review)
        runtime = orchestrator.submit_review(
            project_id=project_id,
            action="approve",
            target_node=None,
            message=None,
        )
        self.assertFalse(runtime.awaiting_review)

    def test_revise_route_back(self):
        project_id = orchestrator.create_project("revise test")
        for _ in range(8):
            runtime = orchestrator.advance(project_id, force=True)
            if runtime.awaiting_review:
                break
        runtime = orchestrator.submit_review(
            project_id=project_id,
            action="revise",
            target_node=NODE_STORYBOARD_ARTIST,
            message="回到分镜",
        )
        self.assertEqual(runtime.current_index, 2)

    def test_chat_command_flow(self):
        project_id = orchestrator.create_project("做一个机甲动漫")
        first_snapshot = orchestrator.snapshot(project_id)
        self.assertGreaterEqual(len(first_snapshot["executionPlan"]), 1)
        self.assertGreaterEqual(len(first_snapshot["suggestedCommands"]), 1)
        self.assertIn("storyboardTable", first_snapshot)
        self.assertGreaterEqual(len(first_snapshot["storyboardTable"]), 0)
        self.assertIn("执行计划", first_snapshot["executionPlanSummary"])
        runtime = orchestrator.advance(project_id, force=True)
        self.assertEqual(runtime.current_index, 1)
        runtime = orchestrator.advance(project_id, force=True)
        self.assertTrue(runtime.awaiting_review)
        self.assertEqual(runtime.state["approval_stage"], "style")
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="修改风格为赛博朋克霓虹",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.current_index, 1)
        runtime = orchestrator.advance(project_id, force=True)
        self.assertTrue(runtime.awaiting_review)
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="确认风格，继续生成",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.current_index, 2)
        self.assertFalse(runtime.awaiting_review)
        self.assertEqual(runtime.status, "running")
        snapshot = orchestrator.snapshot(project_id)
        self.assertGreaterEqual(len(snapshot["chatLogs"]), 4)
        self.assertGreaterEqual(len(snapshot["targetNodeOptions"]), 1)
        self.assertGreaterEqual(len(snapshot["activityLogs"]), 4)
        self.assertGreaterEqual(len(snapshot["intentLogs"]), 1)
        self.assertIsInstance(snapshot["storyboardTable"], list)
        indices = [item["index"] for item in snapshot["activityLogs"]]
        self.assertEqual(indices, list(range(len(indices))))
        self.assertIn(NODE_CHARACTER_DESIGNER, [item["node"] for item in snapshot["executionPlan"]])

    def test_chat_updates_prompt_before_script_run(self):
        project_id = orchestrator.create_project("旧题材")
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="小明穿越到古代是养狗大户",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.state["user_prompt"], "小明穿越到古代是养狗大户")
        self.assertEqual(runtime.chat_logs[-2]["role"], "导演")
        self.assertEqual(runtime.chat_logs[-1]["role"], "分镜师")
        runtime = orchestrator.advance(project_id, force=True)
        scenes = runtime.state.get("script_data", {}).get("scenes", [])
        self.assertGreaterEqual(len(scenes), 2)
        self.assertNotEqual(scenes[0].get("summary"), "主线冲突建立")

    def test_completed_project_supports_new_creation_dialogue(self):
        project_id = orchestrator.create_project("旧故事")
        runtime = orchestrator.get_runtime(project_id)
        self.assertIsNotNone(runtime)
        while runtime and runtime.status != "completed":
            if runtime.awaiting_review:
                runtime = orchestrator.submit_review(
                    project_id=project_id,
                    action="approve",
                    target_node=None,
                    message="通过",
                )
            else:
                runtime = orchestrator.advance(project_id, force=True)
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.status, "completed")
        before_character_count = len(runtime.state.get("character_assets", {}))
        before_storyboard_count = len(runtime.state.get("storyboard_frames", []))
        before_video_count = len(runtime.state.get("video_clips", []))
        before_script_count = len(runtime.state.get("script_history", []))
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="你好我需要创建一段新的剧本，主角是太空快递员",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.status, "running")
        self.assertEqual(runtime.current_index, 0)
        self.assertEqual(runtime.state.get("user_prompt"), "你好我需要创建一段新的剧本，主角是太空快递员")
        self.assertEqual(runtime.chat_logs[-2]["role"], "导演")
        self.assertEqual(runtime.chat_logs[-1]["role"], "分镜师")
        self.assertEqual(runtime.history[-1], "chat_new_cycle_started")
        self.assertEqual(runtime.conversation_round, 2)
        snapshot = orchestrator.snapshot(project_id)
        self.assertEqual(snapshot["conversationRound"], 2)
        self.assertGreaterEqual(len(snapshot["roundHistory"]), 1)
        self.assertGreaterEqual(len(snapshot["intentLogs"]), 1)
        while runtime and runtime.status != "completed":
            if runtime.awaiting_review:
                runtime = orchestrator.submit_review(
                    project_id=project_id,
                    action="approve",
                    target_node=None,
                    message="通过",
                )
            else:
                runtime = orchestrator.advance(project_id, force=True)
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.status, "completed")
        self.assertGreater(len(runtime.state.get("character_assets", {})), before_character_count)
        self.assertGreater(len(runtime.state.get("storyboard_frames", [])), before_storyboard_count)
        self.assertGreater(len(runtime.state.get("video_clips", [])), before_video_count)
        self.assertGreater(len(runtime.state.get("script_history", [])), before_script_count)

    def test_completed_project_generic_chat_keeps_state(self):
        project_id = orchestrator.create_project("旧故事")
        runtime = orchestrator.get_runtime(project_id)
        self.assertIsNotNone(runtime)
        while runtime and runtime.status != "completed":
            if runtime.awaiting_review:
                runtime = orchestrator.submit_review(
                    project_id=project_id,
                    action="approve",
                    target_node=None,
                    message="通过",
                )
            else:
                runtime = orchestrator.advance(project_id, force=True)
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.status, "completed")
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="你好",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.status, "completed")
        self.assertEqual(runtime.chat_logs[-1]["role"], "导演")
        snapshot = orchestrator.snapshot(project_id)
        self.assertEqual(snapshot["conversationRound"], 1)

    def test_storyboard_table_fallback_after_script_attempt(self):
        project_id = orchestrator.create_project("小明喂狗")
        runtime = orchestrator.get_runtime(project_id)
        self.assertIsNotNone(runtime)
        runtime.state["script_data"] = {}
        runtime.state["route_reason"] = "Scriptwriter_Agent"
        snapshot = orchestrator.snapshot(project_id)
        self.assertGreaterEqual(len(snapshot["storyboardTable"]), 1)
        self.assertIn("小明喂狗", snapshot["storyboardTable"][0]["beat"])

    def test_script_feedback_at_character_stage_routes_back_to_scriptwriter(self):
        project_id = orchestrator.create_project("未来城市守护者")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertEqual(runtime.current_index, 1)
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="分镜偏电影感，运镜再强一点",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.current_index, 0)
        self.assertEqual(runtime.history[-1], "chat_revise_script")

    def test_hybrid_intent_router_can_override_rule_result(self):
        project_id = orchestrator.create_project("默认题材")
        with patch(
            "app.services.orchestrator.generate_intent_decision_tool",
            return_value={
                "intent": "continue_pipeline",
                "target_node": NODE_CHARACTER_DESIGNER,
                "confidence": 0.93,
                "reason": "llm_override",
            },
        ):
            runtime = orchestrator.chat_and_operate(
                project_id=project_id,
                message="我希望节奏更紧凑一些",
                operator_id="测试用户",
            )
        self.assertEqual(runtime.state["user_prompt"], "默认题材")
        self.assertEqual(runtime.chat_logs[-1]["role"], "角色设计师")
        snapshot = orchestrator.snapshot(project_id)
        self.assertEqual(snapshot["intentLogs"][-1]["source"], "hybrid_router_v3")
        self.assertEqual(snapshot["intentLogs"][-1]["intent"], "continue_pipeline")

    def test_hybrid_intent_router_falls_back_when_llm_confidence_low(self):
        project_id = orchestrator.create_project("默认题材")
        with patch(
            "app.services.orchestrator.generate_intent_decision_tool",
            return_value={
                "intent": "continue_pipeline",
                "target_node": NODE_CHARACTER_DESIGNER,
                "confidence": 0.5,
                "reason": "uncertain",
            },
        ):
            runtime = orchestrator.chat_and_operate(
                project_id=project_id,
                message="太空歌剧，主角是外卖骑手",
                operator_id="测试用户",
            )
        self.assertEqual(runtime.state["user_prompt"], "太空歌剧，主角是外卖骑手")
        self.assertEqual(runtime.chat_logs[-1]["role"], "分镜师")
        snapshot = orchestrator.snapshot(project_id)
        self.assertEqual(snapshot["intentLogs"][-1]["source"], "rule_router_v2")
        self.assertEqual(snapshot["intentLogs"][-1]["reason"], "llm_low_confidence")

    def test_intent_router_policy_rule_only_forces_rule_result(self):
        previous = get_intent_router_policy()
        try:
            set_intent_router_policy(
                {
                    "version": 2,
                    "rules": {
                        "mode": "rule_only",
                        "llmMinConfidence": 0.2,
                        "ruleHighConfidenceBypass": 0.0,
                        "forceRuleWhenAwaitingReview": False,
                    },
                }
            )
            project_id = orchestrator.create_project("默认题材")
            with patch(
                "app.services.orchestrator.generate_intent_decision_tool",
                return_value={
                    "intent": "continue_pipeline",
                    "target_node": NODE_CHARACTER_DESIGNER,
                    "confidence": 0.99,
                    "reason": "llm_override",
                },
            ):
                runtime = orchestrator.chat_and_operate(
                    project_id=project_id,
                    message="太空歌剧，主角是外卖骑手",
                    operator_id="测试用户",
                )
            self.assertEqual(runtime.state["user_prompt"], "太空歌剧，主角是外卖骑手")
            snapshot = orchestrator.snapshot(project_id)
            self.assertEqual(snapshot["intentLogs"][-1]["source"], "rule_router_v2")
            self.assertEqual(snapshot["intentLogs"][-1]["reason"], "policy_rule_only")
            self.assertEqual(snapshot["intentRouterPolicy"]["rules"]["mode"], "rule_only")
        finally:
            set_intent_router_policy(previous)

    def test_intent_router_policy_model_first_prefers_llm(self):
        previous = get_intent_router_policy()
        try:
            set_intent_router_policy(
                {
                    "version": 2,
                    "rules": {
                        "mode": "model_first",
                        "llmMinConfidence": 0.6,
                        "ruleHighConfidenceBypass": 0.99,
                        "forceRuleWhenAwaitingReview": False,
                    },
                }
            )
            project_id = orchestrator.create_project("默认题材")
            with patch(
                "app.services.orchestrator.generate_intent_decision_tool",
                return_value={
                    "intent": "continue_pipeline",
                    "target_node": NODE_CHARACTER_DESIGNER,
                    "confidence": 0.93,
                    "reason": "llm_override",
                },
            ):
                runtime = orchestrator.chat_and_operate(
                    project_id=project_id,
                    message="太空歌剧，主角是外卖骑手",
                    operator_id="测试用户",
                )
            self.assertEqual(runtime.state["user_prompt"], "默认题材")
            snapshot = orchestrator.snapshot(project_id)
            self.assertEqual(snapshot["intentLogs"][-1]["source"], "hybrid_router_v3")
            self.assertEqual(snapshot["intentRouterPolicy"]["rules"]["mode"], "model_first")
        finally:
            set_intent_router_policy(previous)

    def test_intent_router_policy_settings_roundtrip(self):
        previous = get_intent_router_policy()
        try:
            updated = set_intent_router_policy(
                {
                    "version": 3,
                    "rules": {
                        "mode": "hybrid",
                        "llmMinConfidence": 0.81,
                        "ruleHighConfidenceBypass": 0.95,
                        "forceRuleWhenAwaitingReview": True,
                    },
                }
            )
            self.assertEqual(updated.get("version"), 3)
            self.assertEqual(updated["rules"]["mode"], "hybrid")
            self.assertEqual(updated["rules"]["llmMinConfidence"], 0.81)
            self.assertEqual(updated["rules"]["ruleHighConfidenceBypass"], 0.95)
            loaded = get_intent_router_policy()
            self.assertEqual(loaded["rules"]["mode"], "hybrid")
        finally:
            set_intent_router_policy(previous)

    def test_project_level_intent_policy_isolated_between_projects(self):
        first_project = orchestrator.create_project("项目A")
        second_project = orchestrator.create_project("项目B")
        first_policy = orchestrator.set_project_intent_router_policy(
            first_project,
            {
                "rules": {
                    "mode": "model_first",
                    "llmMinConfidence": 0.66,
                    "ruleHighConfidenceBypass": 0.93,
                    "forceRuleWhenAwaitingReview": False,
                }
            },
        )
        second_policy = orchestrator.get_project_intent_router_policy(second_project)
        self.assertEqual(first_policy["rules"]["mode"], "model_first")
        self.assertEqual(first_policy["rules"]["llmMinConfidence"], 0.66)
        self.assertNotEqual(second_policy["rules"]["mode"], "model_first")

    def test_project_level_policy_drives_intent_router(self):
        project_id = orchestrator.create_project("规则优先项目")
        orchestrator.set_project_intent_router_policy(
            project_id,
            {
                "rules": {
                    "mode": "rule_only",
                    "llmMinConfidence": 0.2,
                    "ruleHighConfidenceBypass": 0.0,
                    "forceRuleWhenAwaitingReview": False,
                }
            },
        )
        with patch(
            "app.services.orchestrator.generate_intent_decision_tool",
            return_value={
                "intent": "continue_pipeline",
                "target_node": NODE_CHARACTER_DESIGNER,
                "confidence": 0.99,
                "reason": "llm_override",
            },
        ):
            runtime = orchestrator.chat_and_operate(
                project_id=project_id,
                message="太空歌剧，主角是外卖骑手",
                operator_id="测试用户",
            )
        self.assertEqual(runtime.state["user_prompt"], "太空歌剧，主角是外卖骑手")
        snapshot = orchestrator.snapshot(project_id)
        self.assertEqual(snapshot["intentRouterPolicy"]["rules"]["mode"], "rule_only")
        self.assertEqual(snapshot["intentLogs"][-1]["reason"], "policy_rule_only")

    def test_runtime_persisted_to_sqlite(self):
        local = ProjectOrchestrator()
        project_id = local.create_project("持久化测试")
        restored = ProjectOrchestrator()
        self.assertIn(project_id, restored.list_project_ids())

    def test_manager_tool_gateway_activity_pipeline(self):
        project_id = orchestrator.create_project("企业级编排测试")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertIn(runtime.status, {"running", "waiting_review"})
        snapshot = orchestrator.snapshot(project_id)
        kinds = [item["kind"] for item in snapshot["activityLogs"]]
        self.assertIn("manager_decision", kinds)
        self.assertIn("tool_execution", kinds)
        self.assertIn("review_gateway", kinds)

    def test_node_completion_has_actor_and_tool_chat(self):
        project_id = orchestrator.create_project("节点角色展示测试")
        orchestrator.advance(project_id, force=True)
        snapshot = orchestrator.snapshot(project_id)
        history_events = [
            item for item in snapshot["activityLogs"] if item["kind"] == "history" and item["payload"].get("event")
        ]
        self.assertGreaterEqual(len(history_events), 2)
        self.assertEqual(history_events[-1]["payload"]["event"], "Scriptwriter_Agent")
        self.assertEqual(history_events[-1]["payload"].get("actor"), "分镜师")
        chat_roles = [item["role"] for item in snapshot["chatLogs"]]
        self.assertIn("分镜师", chat_roles)

    def test_start_next_stage_chat_uses_worker_role(self):
        project_id = orchestrator.create_project("开始下一阶段角色测试")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertEqual(runtime.current_index, 1)
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="开始下一阶段",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.chat_logs[-2]["role"], "导演")
        self.assertEqual(runtime.chat_logs[-1]["role"], "角色设计师")

    def test_chat_approve_generates_director_dispatch_and_worker_reply(self):
        project_id = orchestrator.create_project("审批后双对话测试")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertEqual(runtime.current_index, 1)
        runtime = orchestrator.advance(project_id, force=True)
        self.assertTrue(runtime.awaiting_review)
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="确认风格，继续生成",
            operator_id="测试用户",
        )
        self.assertEqual(runtime.chat_logs[-2]["role"], "导演")
        self.assertEqual(runtime.chat_logs[-1]["role"], "分镜画师")

    def test_manager_llm_invalid_action_fallback_to_rule(self):
        manager = ManagerAgent()
        with patch(
            "app.services.manager_agent.generate_manager_decision_tool",
            return_value={"action": "unknown", "next_node": "Scriptwriter_Agent", "reason": "bad"},
        ):
            decision = manager.decide(
                status="running",
                awaiting_review=False,
                current_index=0,
                sequence=[("Scriptwriter_Agent", object(), "分镜拆解")],
                preferred_node="Scriptwriter_Agent",
                history_tail=["project_created"],
            )
        self.assertEqual(decision.action, "execute")
        self.assertEqual(decision.next_node, "Scriptwriter_Agent")
        self.assertEqual(decision.metadata.get("fallback"), "invalid_llm_action")

    def test_review_gateway_cost_policy_can_force_review(self):
        previous = get_review_gateway_policy()
        try:
            updated = set_review_gateway_policy(
                {
                    "version": 2,
                    "rules": {
                        "maxRenderCostBeforeApproval": 0.1,
                        "manualApprovalNodes": [],
                        "minQaScoreByNode": {},
                        "forceApprovalOnErrors": False,
                    },
                }
            )
            self.assertEqual(updated.get("version"), 2)
            project_id = orchestrator.create_project("成本网关测试")
            runtime = orchestrator.advance(project_id, force=True)
            self.assertTrue(runtime.awaiting_review)
            self.assertEqual(runtime.state.get("approval_stage"), "cost")
            snapshot = orchestrator.snapshot(project_id)
            gateway_events = [item for item in snapshot["activityLogs"] if item["kind"] == "review_gateway"]
            self.assertGreaterEqual(len(gateway_events), 1)
            self.assertEqual(gateway_events[-1]["payload"]["reason"], "cost_gate")
        finally:
            set_review_gateway_policy(previous)

    def test_storyboard_generation_requires_review(self):
        previous = get_review_gateway_policy()
        try:
            set_review_gateway_policy(
                {
                    "version": 3,
                    "rules": {
                        "maxRenderCostBeforeApproval": None,
                        "manualApprovalNodes": [],
                        "minQaScoreByNode": {},
                        "forceApprovalOnErrors": False,
                    },
                }
            )
            project_id = orchestrator.create_project("分镜审核必经测试")
            runtime = orchestrator.get_runtime(project_id)
            self.assertIsNotNone(runtime)
            for _ in range(12):
                runtime = orchestrator.get_runtime(project_id)
                if runtime is None:
                    break
                if runtime.awaiting_review:
                    runtime = orchestrator.submit_review(
                        project_id=project_id,
                        action="approve",
                        target_node=None,
                        message="通过",
                    )
                    continue
                runtime = orchestrator.advance(project_id, force=True)
                if runtime.history and runtime.history[-1] == NODE_STORYBOARD_ARTIST:
                    break
            runtime = orchestrator.get_runtime(project_id)
            self.assertIsNotNone(runtime)
            self.assertTrue(runtime.awaiting_review)
            self.assertEqual(runtime.state.get("approval_stage"), "storyboard")
            snapshot = orchestrator.snapshot(project_id)
            gateway_events = [item for item in snapshot["activityLogs"] if item["kind"] == "review_gateway"]
            self.assertGreaterEqual(len(gateway_events), 1)
            self.assertEqual(gateway_events[-1]["payload"]["reason"], "storyboard_mandatory_review")
        finally:
            set_review_gateway_policy(previous)

    def test_state_version_increments_across_writes(self):
        project_id = orchestrator.create_project("版本测试")
        initial_version = orchestrator.snapshot(project_id)["stateVersion"]
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message="你好",
            operator_id="测试用户",
        )
        after_chat = runtime.state.get("version", 0)
        self.assertGreater(after_chat, initial_version)
        runtime = orchestrator.advance(project_id, force=True)
        self.assertGreater(runtime.state.get("version", 0), after_chat)

    def test_state_events_cover_script_asset_review(self):
        project_id = orchestrator.create_project("事件日志测试")
        runtime = orchestrator.advance(project_id, force=True)
        self.assertIn(runtime.status, {"running", "waiting_review"})
        runtime = orchestrator.advance(project_id, force=True)
        self.assertTrue(runtime.awaiting_review)
        runtime = orchestrator.submit_review(
            project_id=project_id,
            action="approve",
            target_node=None,
            message="通过",
        )
        snapshot = orchestrator.snapshot(project_id)
        state_events = [
            item["payload"]["event"]
            for item in snapshot["activityLogs"]
            if item.get("kind") == "state_event" and isinstance(item.get("payload"), dict)
        ]
        self.assertIn("script_generated", state_events)
        self.assertIn("asset_added", state_events)
        self.assertIn("review_action", state_events)

    def test_field_level_write_permission_blocks_unauthorized_changes(self):
        executor = ToolizedAgentExecutor()
        state = create_initial_state("权限测试")

        def invalid_storyboard_handler(current_state):
            next_state = dict(current_state)
            next_state["character_assets"] = {
                "main_character_1": {
                    "asset_id": "char_1",
                    "uri": "https://example.com/char.png",
                    "version": 1,
                    "seed": 42,
                    "model_name": "test",
                    "params": {},
                    "qa_score": 0.9,
                }
            }
            return next_state

        with self.assertRaises(ValueError):
            executor.execute(
                node_name=NODE_STORYBOARD_ARTIST,
                handler=invalid_storyboard_handler,
                state=state,
                allowed_write_fields={"storyboard_frames"},
            )

    def test_compact_snapshot_omits_heavy_logs(self):
        project_id = orchestrator.create_project("轻量快照测试")
        orchestrator.advance(project_id, force=True)
        compact = orchestrator.snapshot(project_id, compact=True)
        full = orchestrator.snapshot(project_id)
        self.assertEqual(compact["projectId"], full["projectId"])
        self.assertEqual(compact["status"], full["status"])
        self.assertEqual(compact["activityLogs"], [])
        self.assertEqual(compact["chatLogs"], [])
        self.assertEqual(compact["reviewLogs"], [])
        self.assertEqual(compact["assetGallery"]["characters"], [])
        self.assertEqual(compact["storyboardTable"], [])


if __name__ == "__main__":
    unittest.main()
