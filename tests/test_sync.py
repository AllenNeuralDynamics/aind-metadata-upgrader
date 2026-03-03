"""Tests for the sync module."""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from aind_metadata_upgrader import sync


class TestSync(unittest.TestCase):
    """Test class for sync module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_v1_client = MagicMock()
        self.mock_v2_client = MagicMock()
        self.mock_upgrade = MagicMock()

        # Sample test data
        self.sample_v1_records = [{"_id": "record1"}, {"_id": "record2"}, {"_id": "record3"}]

        self.sample_cached_records = [
            {"_id": "record1", "name": "test1", "location": "loc1", "last_modified": "2023-01-01"},
            {"_id": "record2", "name": "test2", "location": "loc2", "last_modified": "2023-01-02"},
            {"_id": "record3", "name": "test3", "location": "loc3", "last_modified": "2023-01-03"},
        ]

        self.sample_upgrade_results = [
            {"v1_id": "record1", "v2_id": "v2_record1", "upgrader_version": "1.0.0", "status": "success"},
            {"v1_id": "record2", "v2_id": "v2_record2", "upgrader_version": "1.0.0", "status": "success"},
        ]

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_successful_upgrade_no_existing_table(
        self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom
    ):
        """Test successful upgrade with no existing cache table."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            self.sample_v1_records,  # First call for record IDs
            self.sample_cached_records[:1],  # Second call for cached records
        ]

        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]

        # Mock upgrade instance
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance

        # Mock v2 client responses
        mock_v2_client.retrieve_docdb_records.side_effect = [
            [],  # No existing record
            [{"_id": "new_v2_id"}],  # New record after insertion
        ]

        sync.run()

        mock_v1_client.retrieve_docdb_records.assert_any_call(filter_query={}, projection={"_id": 1})
        mock_upgrade_class.assert_called_once()
        mock_v2_client.insert_one_docdb_record.assert_called_once()
        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertGreater(len(store_calls), 0)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_with_existing_successful_record(
        self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom
    ):
        """Test that already successfully upgraded records are skipped."""
        existing_df = pd.DataFrame(
            [
                {
                    "v1_id": "record1",
                    "v2_id": "v2_record1",
                    "upgrader_version": "1.0.0",
                    "status": "success",
                    "last_modified": "2023-01-01",
                }
            ]
        )
        mock_custom.return_value = existing_df

        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],  # Record IDs
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],  # Cached records
        ]

        sync.run()

        mock_upgrade_class.assert_not_called()
        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 0)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_upgrade_failure(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test handling of upgrade failures."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_class.side_effect = Exception("Upgrade failed")

        sync.run()

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 1)
        df = store_calls[0].kwargs["df"]
        self.assertEqual(df.iloc[0]["status"], "failed")
        self.assertEqual(df.iloc[0]["v1_id"], "record1")
        self.assertIsNone(df.iloc[0]["v2_id"])

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_upgrade_returns_none(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test handling when upgrade returns None."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_class.return_value = None

        sync.run()

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 1)
        df = store_calls[0].kwargs["df"]
        self.assertEqual(df.iloc[0]["status"], "failed")
        self.assertEqual(df.iloc[0]["v1_id"], "record1")
        self.assertIsNone(df.iloc[0]["v2_id"])

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_existing_v2_record(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test handling when v2 record already exists."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        sync.run()

        mock_v2_client.insert_one_docdb_record.assert_not_called()
        mock_v2_client.upsert_list_of_docdb_records.assert_called_once()

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    @patch("aind_metadata_upgrader.sync.BATCH_SIZE", 2)  # Small batch size for testing
    def test_run_batch_processing(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test that batch processing works correctly."""
        records = [{"_id": f"record{i}"} for i in range(1, 4)]
        cached_records_batch1 = [
            {"_id": f"record{i}", "location": f"loc{i}", "last_modified": f"2023-01-0{i}"} for i in range(1, 3)
        ]
        cached_records_batch2 = [{"_id": "record3", "location": "loc3", "last_modified": "2023-01-03"}]
        mock_v1_client.retrieve_docdb_records.side_effect = [
            records,
            cached_records_batch1,
            cached_records_batch2,
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        sync.run()

        self.assertGreaterEqual(mock_v1_client.retrieve_docdb_records.call_count, 3)
        self.assertEqual(mock_v2_client.upsert_list_of_docdb_records.call_count, 2)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_filters_stale_rows_from_original_df(
        self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom
    ):
        """Test that rows whose v1_id no longer exists in the v1 DB are wiped."""
        existing_df = pd.DataFrame([
            {"v1_id": "record1", "v2_id": "v2_record1", "upgrader_version": "1.0.0",
             "status": "success", "last_modified": "2023-01-01"},
            {"v1_id": "stale_record", "v2_id": "v2_stale", "upgrader_version": "1.0.0",
             "status": "success", "last_modified": "2022-01-01"},
        ])
        mock_custom.return_value = existing_df
        # Only record1 exists in v1 DB; stale_record has been deleted
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],
        ]

        sync.run()

        # record1 is up-to-date so no upgrade; stale_record silently filtered out
        mock_upgrade_class.assert_not_called()

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.logging")
    def test_run_no_records(self, mock_logging, mock_v1_client, mock_v2_client, mock_custom):
        """Test handling when no records are found."""
        mock_v1_client.retrieve_docdb_records.return_value = []
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]

        sync.run()

        mock_logging.info.assert_called_with("(METADATA VALIDATOR) No upgrade results to write to RDS")

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    def test_run_invalid_existing_table(self, mock_v1_client, mock_v2_client, mock_custom):
        """Test handling when existing cache table is missing required columns."""
        invalid_df = pd.DataFrame([{"wrong_column": "value"}])
        mock_custom.return_value = invalid_df
        mock_v1_client.retrieve_docdb_records.return_value = []

        sync.run()

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_successful(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test run_one with successful upgrade and existing v2 record."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        sync.run_one("record1")

        mock_v2_client.upsert_one_docdb_record.assert_called_once()
        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertGreater(len(store_calls), 0)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    def test_run_one_record_not_found(self, mock_v1_client, mock_v2_client, mock_custom):
        """Test run_one when record doesn't exist."""
        mock_v1_client.retrieve_docdb_records.return_value = []

        with self.assertRaises(ValueError):
            sync.run_one("nonexistent")

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_skip_condition(self, mock_v1_client, mock_v2_client, mock_custom):
        """Test run_one skips already upgraded records."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        existing_df = pd.DataFrame([{
            "v1_id": "record1", "v2_id": "v2_record1",
            "upgrader_version": "1.0.0", "status": "success", "last_modified": "2023-01-01",
        }])
        mock_custom.return_value = existing_df

        sync.run_one("record1")

        mock_v2_client.upsert_one_docdb_record.assert_not_called()
        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 0)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_upgrade_failure(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_custom):
        """Test run_one handles upgrade failures."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]
        mock_upgrade_class.side_effect = Exception("Upgrade failed")

        sync.run_one("record1")

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertGreater(len(store_calls), 0)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "2.5.0")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_insert_new_record(self, mock_custom):
        """Test that update_rds_tracking correctly inserts a new record."""
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]

        result = {
            "v1_id": "test_v1_id_123",
            "v2_id": "test_v2_id_456",
            "upgrader_version": "2.5.0",
            "last_modified": "2024-12-15T10:30:00",
            "status": "success",
        }

        sync.update_rds_tracking("test_v1_id_123", result, None)

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 1)
        df = store_calls[0].kwargs["df"]
        self.assertEqual(df.iloc[0]["v1_id"], "test_v1_id_123")
        self.assertEqual(df.iloc[0]["v2_id"], "test_v2_id_456")
        self.assertEqual(df.iloc[0]["status"], "success")
        self.assertEqual(df.iloc[0]["last_modified"], "2024-12-15T10:30:00")

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "3.1.4")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_update_existing_record(self, mock_custom):
        """Test that update_rds_tracking correctly overwrites an existing record."""
        existing_df = pd.DataFrame([{
            "v1_id": "old_v1_id_789", "v2_id": "old_v2_id",
            "upgrader_version": "1.0.0", "last_modified": "2023-01-01", "status": "success",
        }])
        mock_custom.side_effect = lambda *a, **kw: kw["df"] if kw.get("force_update") else existing_df

        result = {
            "v1_id": "old_v1_id_789",
            "v2_id": "new_v2_id_999",
            "upgrader_version": "3.1.4",
            "last_modified": "2025-06-20T14:45:30",
            "status": "success",
        }

        sync.update_rds_tracking("old_v1_id_789", result, [{"existing": "row"}])

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 1)
        df = store_calls[0].kwargs["df"]
        row = df[df["v1_id"] == "old_v1_id_789"].iloc[0]
        self.assertEqual(row["v2_id"], "new_v2_id_999")
        self.assertEqual(row["last_modified"], "2025-06-20T14:45:30")
        self.assertEqual(row["status"], "success")
        self.assertEqual(len(df[df["v1_id"] == "old_v1_id_789"]), 1)

    @patch("aind_metadata_upgrader.sync.custom")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.2.3")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_failed_status(self, mock_custom):
        """Test that update_rds_tracking correctly handles failed upgrades with None v2_id."""
        mock_custom.side_effect = lambda *a, **kw: (_ for _ in ()).throw(ValueError("empty")) if not kw.get("force_update") else kw["df"]

        result = {
            "v1_id": "failed_v1_id_555",
            "v2_id": None,
            "upgrader_version": "1.2.3",
            "last_modified": "2024-03-10T08:00:00",
            "status": "failed",
        }

        sync.update_rds_tracking("failed_v1_id_555", result, None)

        store_calls = [c for c in mock_custom.call_args_list if c.kwargs.get("force_update")]
        self.assertEqual(len(store_calls), 1)
        df = store_calls[0].kwargs["df"]
        self.assertEqual(df.iloc[0]["v1_id"], "failed_v1_id_555")
        self.assertIsNone(df.iloc[0]["v2_id"])
        self.assertEqual(df.iloc[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
