import unittest

from app.graph.routing import NODE_STORYBOARD_ARTIST
from app.services.orchestrator import orchestrator


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
        self.assertEqual(runtime.current_index, 3)


if __name__ == "__main__":
    unittest.main()
