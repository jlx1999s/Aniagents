import unittest

from app.graph.routing import (
    NODE_ANIMATION_ARTIST,
    NODE_ART_DIRECTOR,
    NODE_CHARACTER_DESIGNER,
    NODE_COMPOSITOR,
    NODE_DIRECTOR,
    NODE_SCRIPTWRITER,
    NODE_SOUND_DIRECTOR,
    NODE_STORYBOARD_ARTIST,
    route_from_director,
)
from app.graph.state import create_initial_state


class RoutingTests(unittest.TestCase):
    def test_feedback_routes_to_target(self):
        state = create_initial_state("test")
        state["pending_feedback"] = [
            {
                "stage": "character",
                "issue_type": "style",
                "message": "fix",
                "target_node": NODE_CHARACTER_DESIGNER,
                "priority": "high",
                "round_id": 1,
            }
        ]
        self.assertEqual(route_from_director(state), NODE_CHARACTER_DESIGNER)

    def test_approval_required_returns_director(self):
        state = create_initial_state("test")
        state["approval_required"] = True
        self.assertEqual(route_from_director(state), NODE_DIRECTOR)

    def test_sequence_routes_forward(self):
        state = create_initial_state("test")
        self.assertEqual(route_from_director(state), NODE_SCRIPTWRITER)
        state["route_reason"] = NODE_SCRIPTWRITER
        self.assertEqual(route_from_director(state), NODE_ART_DIRECTOR)
        state["route_reason"] = NODE_ART_DIRECTOR
        self.assertEqual(route_from_director(state), NODE_CHARACTER_DESIGNER)
        state["route_reason"] = NODE_CHARACTER_DESIGNER
        self.assertEqual(route_from_director(state), NODE_STORYBOARD_ARTIST)
        state["route_reason"] = NODE_STORYBOARD_ARTIST
        self.assertEqual(route_from_director(state), NODE_ANIMATION_ARTIST)
        state["route_reason"] = NODE_ANIMATION_ARTIST
        self.assertEqual(route_from_director(state), NODE_SOUND_DIRECTOR)
        state["route_reason"] = NODE_SOUND_DIRECTOR
        self.assertEqual(route_from_director(state), NODE_COMPOSITOR)


if __name__ == "__main__":
    unittest.main()
