import tempfile
import unittest
from pathlib import Path

import database
from agent_tools import create_ticket_draft, get_equipment_snapshot
from database import (
    approve_maintenance_ticket,
    initialize_database,
    save_readings,
    set_equipment_thresholds,
)


class AgentToolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_file = database.DATABASE_FILE
        database.DATABASE_FILE = (
            Path(self.temporary_directory.name) / "maintenance.db"
        )

        initialize_database()
        save_readings(
            [
                {
                    "equipment_id": "MOTOR-TEST",
                    "timestamp": "2026-10-01 09:00:00",
                    "temperature_c": 68.0,
                    "vibration_mm_s": 4.2,
                    "rpm": 1500,
                },
                {
                    "equipment_id": "MOTOR-TEST",
                    "timestamp": "2026-10-01 09:05:00",
                    "temperature_c": 72.0,
                    "vibration_mm_s": 5.1,
                    "rpm": 1498,
                },
            ]
        )
        set_equipment_thresholds("MOTOR-TEST", 70.0, 4.5)

    def tearDown(self) -> None:
        database.DATABASE_FILE = self.original_database_file
        self.temporary_directory.cleanup()

    def test_snapshot_uses_configured_thresholds(self) -> None:
        snapshot = get_equipment_snapshot("MOTOR-TEST")

        self.assertEqual(snapshot["status"], "attention")
        self.assertEqual(snapshot["summary"]["readings_count"], 2)
        self.assertEqual(len(snapshot["latest_alerts"]), 1)

    def test_ticket_workflow_is_idempotent(self) -> None:
        first_result = create_ticket_draft("MOTOR-TEST")
        second_result = create_ticket_draft("MOTOR-TEST")

        self.assertTrue(first_result["created"])
        self.assertFalse(second_result["created"])
        self.assertEqual(
            first_result["ticket"]["ticket_id"],
            second_result["ticket"]["ticket_id"],
        )
        self.assertEqual(first_result["ticket"]["priority"], "high")

        approved_ticket, changed = approve_maintenance_ticket(
            first_result["ticket"]["ticket_id"]
        )
        same_ticket, changed_again = approve_maintenance_ticket(
            first_result["ticket"]["ticket_id"]
        )

        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(approved_ticket["status"], "approved")
        self.assertEqual(same_ticket["status"], "approved")


if __name__ == "__main__":
    unittest.main()
