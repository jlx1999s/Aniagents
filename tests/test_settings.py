import unittest

from app.services.review_gateway_policy import (
    get_review_gateway_policy,
    set_review_gateway_policy,
)


class SettingsTests(unittest.TestCase):
    def test_review_gateway_policy_roundtrip(self):
        previous = get_review_gateway_policy()
        try:
            payload = {
                "version": 3,
                "updatedAt": "2026-03-13T00:00:00Z",
                "rules": {
                    "maxRenderCostBeforeApproval": 5.5,
                    "manualApprovalNodes": ["Animation_Artist_Agent"],
                    "minQaScoreByNode": {"Storyboard_Artist_Agent": 0.92},
                    "forceApprovalOnErrors": True,
                },
            }
            updated = set_review_gateway_policy(payload)
            self.assertEqual(updated["version"], 3)
            self.assertEqual(updated["rules"]["manualApprovalNodes"], ["Animation_Artist_Agent"])
            self.assertEqual(updated["rules"]["minQaScoreByNode"]["Storyboard_Artist_Agent"], 0.92)
        finally:
            set_review_gateway_policy(previous)


if __name__ == "__main__":
    unittest.main()
