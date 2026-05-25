import unittest

from client.safety.risk_policy import (
    LOCAL_PROTECTION_PREFIX,
    REVIEW_CONFIDENCE_CAP,
    apply_deterministic_risk_downgrade,
    apply_deterministic_risk_downgrades,
)


class RiskPolicyTestCase(unittest.TestCase):
    def test_important_document_name_caps_high_confidence(self):
        result = apply_deterministic_risk_downgrade(
            {
                "file_id": "f1",
                "filename": "diploma-final.pdf",
                "extension": ".pdf",
                "parent_dir": "C:/Users/Alice/Documents",
            },
            {
                "file_id": "f1",
                "confidence": 0.96,
                "category": "document",
                "reason": "Старый документ",
            },
        )

        self.assertEqual(result["confidence"], REVIEW_CONFIDENCE_CAP)
        self.assertIn(LOCAL_PROTECTION_PREFIX, result["reason"])

    def test_database_extension_caps_high_confidence(self):
        result = apply_deterministic_risk_downgrade(
            {
                "file_id": "db1",
                "filename": "local-index.sqlite",
                "extension": ".sqlite",
                "parent_dir": "D:/demo/databases",
            },
            {
                "file_id": "db1",
                "confidence": 0.91,
                "category": "database",
                "reason": "Старая база",
            },
        )

        self.assertEqual(result["confidence"], REVIEW_CONFIDENCE_CAP)
        self.assertIn("расширение .sqlite", result["reason"])

    def test_code_category_caps_even_without_risky_extension(self):
        result = apply_deterministic_risk_downgrade(
            {
                "file_id": "code1",
                "filename": "legacy-snippet.txt",
                "extension": ".txt",
                "parent_dir": "D:/Projects/archive",
            },
            {
                "file_id": "code1",
                "confidence": 0.88,
                "category": "code",
                "reason": "Похож на старый файл",
            },
        )

        self.assertEqual(result["confidence"], REVIEW_CONFIDENCE_CAP)
        self.assertIn("категория code", result["reason"])

    def test_safe_installer_is_not_downgraded(self):
        result = apply_deterministic_risk_downgrade(
            {
                "file_id": "setup1",
                "filename": "old-driver-installer.msi",
                "extension": ".msi",
                "parent_dir": "C:/Users/Alice/Downloads",
            },
            {
                "file_id": "setup1",
                "confidence": 0.93,
                "category": "installer",
                "reason": "Старый установщик",
            },
        )

        self.assertEqual(result["confidence"], 0.93)
        self.assertNotIn(LOCAL_PROTECTION_PREFIX, result["reason"])

    def test_existing_low_confidence_is_not_raised(self):
        result = apply_deterministic_risk_downgrade(
            {
                "file_id": "contract1",
                "filename": "contract.pdf",
                "extension": ".pdf",
                "parent_dir": "C:/Users/Alice/Documents",
            },
            {
                "file_id": "contract1",
                "confidence": 0.2,
                "category": "document",
                "reason": "Важный документ",
            },
        )

        self.assertEqual(result["confidence"], 0.2)

    def test_batch_policy_matches_classifications_by_file_id(self):
        results = apply_deterministic_risk_downgrades(
            [
                {
                    "file_id": "a",
                    "filename": "passport-scan.jpg",
                    "extension": ".jpg",
                    "parent_dir": "D:/Photos",
                },
                {
                    "file_id": "b",
                    "filename": "setup.msi",
                    "extension": ".msi",
                    "parent_dir": "D:/Downloads",
                },
            ],
            [
                {
                    "file_id": "b",
                    "confidence": 0.9,
                    "category": "installer",
                    "reason": "ok",
                },
                {
                    "file_id": "a",
                    "confidence": 0.9,
                    "category": "media",
                    "reason": "ok",
                },
            ],
        )

        by_id = {item["file_id"]: item for item in results}
        self.assertEqual(by_id["a"]["confidence"], REVIEW_CONFIDENCE_CAP)
        self.assertEqual(by_id["b"]["confidence"], 0.9)


if __name__ == "__main__":
    unittest.main()
