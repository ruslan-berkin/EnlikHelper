import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
from agent_tools import create_ticket_draft, get_equipment_snapshot
from database import (
    approve_maintenance_ticket,
    get_manual_chunks,
    get_equipment_profile,
    initialize_database,
    list_manual_documents,
    save_manual_document,
    save_readings,
    set_equipment_profile,
    set_equipment_thresholds,
)
from knowledge_service import (
    _chunk_text,
    _cosine_similarity,
    index_manual,
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
        self.assertEqual(snapshot["profile"]["equipment_id"], "MOTOR-TEST")

    def test_equipment_profile_is_saved_and_returned(self) -> None:
        profile = set_equipment_profile(
            "MOTOR-TEST", "ABB", "M2B", "SERIAL-001"
        )
        self.assertEqual(profile["manufacturer"], "ABB")
        self.assertEqual(profile["model"], "M2B")
        self.assertEqual(
            get_equipment_profile("MOTOR-TEST")["serial_number"],
            "SERIAL-001",
        )

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

    def test_manual_storage_is_idempotent(self) -> None:
        chunks = [
            {
                "page_number": 2,
                "chunk_index": 0,
                "content": "Проверить крепление двигателя.",
                "embedding": [1.0, 0.0],
            }
        ]

        first_document, first_created = save_manual_document(
            equipment_id="MOTOR-TEST",
            filename="manual.pdf",
            sha256="same-file",
            page_count=3,
            chunks=chunks,
        )
        second_document, second_created = save_manual_document(
            equipment_id="MOTOR-TEST",
            filename="renamed.pdf",
            sha256="same-file",
            page_count=3,
            chunks=chunks,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(
            first_document["document_id"],
            second_document["document_id"],
        )
        self.assertEqual(len(list_manual_documents("MOTOR-TEST")), 1)
        self.assertEqual(len(get_manual_chunks("MOTOR-TEST")), 1)

    def test_chunking_and_similarity(self) -> None:
        long_text = " ".join(["датчик"] * 400)
        chunks = _chunk_text(long_text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 1600 for chunk in chunks))
        self.assertAlmostEqual(
            _cosine_similarity([1.0, 0.0], [1.0, 0.0]),
            1.0,
        )
        self.assertAlmostEqual(
            _cosine_similarity([1.0, 0.0], [0.0, 1.0]),
            0.0,
        )

    def test_duplicate_manual_skips_embedding_api(self) -> None:
        manual_path = Path(self.temporary_directory.name) / "manual.pdf"
        manual_path.write_bytes(b"same-pdf-content")

        save_manual_document(
            equipment_id="MOTOR-TEST",
            filename="manual.pdf",
            sha256=(
                "7f5618feca25e4325c2dfad8d13488b0"
                "77018c26da4bf1ecbe2e231c3ef5e704"
            ),
            page_count=1,
            chunks=[
                {
                    "page_number": 1,
                    "chunk_index": 0,
                    "content": "Проверить датчик.",
                    "embedding": [1.0, 0.0],
                }
            ],
        )

        with patch(
            "knowledge_service._create_embeddings",
            side_effect=AssertionError("API should not be called"),
        ):
            result = index_manual(
                equipment_id="MOTOR-TEST",
                file_path=manual_path,
                filename="manual.pdf",
            )

        self.assertFalse(result["created"])


if __name__ == "__main__":
    unittest.main()
