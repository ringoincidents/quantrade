import unittest

from quantrade.capabilities.research_preflight import (
    DependencyCheck,
    ResearchPreflightInput,
    evaluate_research_preflight,
)


def check(
    dependency_id,
    status,
    *,
    required=True,
    kind="fixture",
):
    return DependencyCheck(
        dependency_id=dependency_id,
        dependency_kind=kind,
        required=required,
        status=status,
        detail=f"fixture {status}",
        source_ref=f"fixture://{dependency_id}",
        checked_at="2026-10-09T12:00:00+09:00",
    )


class ResearchPreflightTests(unittest.TestCase):
    def test_all_required_available_is_ready(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-READY",
                checks=(
                    check("secret", "AVAILABLE"),
                    check("identity", "VERIFIED_CACHE"),
                    check("source", "VERIFIED"),
                ),
            )
        )
        self.assertEqual("READY", result.status)
        self.assertTrue(result.execute_allowed)
        self.assertEqual((), result.blockers)

    def test_maintenance_blocks_without_generic_retry_authority(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-MAINT",
                checks=(
                    check(
                        "dart-corp-code",
                        "MAINTENANCE",
                        kind="external_service",
                    ),
                ),
            )
        )
        self.assertEqual("BLOCKED", result.status)
        self.assertFalse(result.execute_allowed)
        self.assertEqual(
            ("EXTERNAL_UNAVAILABLE",),
            result.failure_classes,
        )
        self.assertFalse(
            result.validation["generic_retry_authorized"]
        )

    def test_unregistered_is_distinct_from_missing(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-TAXONOMY",
                checks=(
                    check("issuer-id", "UNREGISTERED"),
                    check("source-doc", "MISSING"),
                ),
            )
        )
        self.assertEqual(
            ("MATERIAL_ABSENT", "UNREGISTERED"),
            result.failure_classes,
        )
        self.assertEqual(
            {"UNREGISTERED", "MISSING"},
            {item["status"] for item in result.blockers},
        )

    def test_access_denied_is_not_material_absent(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-ACCESS",
                checks=(
                    check("private-source", "ACCESS_DENIED"),
                ),
            )
        )
        self.assertEqual(
            ("ACCESS_DENIED",),
            result.failure_classes,
        )

    def test_optional_failure_becomes_warning(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-WARN",
                checks=(
                    check("primary", "AVAILABLE"),
                    check(
                        "secondary",
                        "NETWORK_UNAVAILABLE",
                        required=False,
                    ),
                ),
            )
        )
        self.assertEqual("READY_WITH_WARNINGS", result.status)
        self.assertTrue(result.execute_allowed)
        self.assertEqual(1, len(result.warnings))
        self.assertEqual((), result.failure_classes)

    def test_founder_approval_does_not_grant_tool_permission(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-GOV",
                checks=(
                    check("secret", "ACCESS_DENIED"),
                ),
            )
        )
        self.assertFalse(
            result.validation[
                "founder_approval_interpreted_as_tool_permission"
            ]
        )
        self.assertFalse(
            result.authority["tool_permission_granted"]
        )
        self.assertFalse(
            result.authority["secret_access_granted"]
        )

    def test_no_execution_authority(self):
        result = evaluate_research_preflight(
            ResearchPreflightInput(
                mission_id="MIS-SAFE",
                checks=(check("primary", "AVAILABLE"),),
            )
        )
        self.assertFalse(result.authority["paper_authorized"])
        self.assertFalse(result.authority["execution_authorized"])
        self.assertFalse(result.authority["live_order_possible"])


if __name__ == "__main__":
    unittest.main()
