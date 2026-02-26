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
        self.mock_rds_client = MagicMock()
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

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_successful_upgrade_no_existing_table(
        self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client
    ):
        """Test successful upgrade with no existing RDS table."""
        # Setup mocks
        mock_v1_client.retrieve_docdb_records.side_effect = [
            self.sample_v1_records,  # First call for record IDs
            self.sample_cached_records[:1],  # Second call for cached records
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

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

        # Run the function
        sync.run()

        # Verify calls
        mock_v1_client.retrieve_docdb_records.assert_any_call(filter_query={}, projection={"_id": 1})
        mock_upgrade_class.assert_called_once()
        mock_v2_client.insert_one_docdb_record.assert_called_once()
        mock_rds_client.overwrite_table_with_df.assert_called_once()

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_with_existing_successful_record(
        self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client
    ):
        """Test that already successfully upgraded records are skipped."""
        # Setup existing RDS data with successful upgrade
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
        mock_rds_client.read_table.return_value = existing_df

        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],  # Record IDs
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],  # Cached records
        ]

        # Run the function
        sync.run()

        # Verify that upgrade was not called since record was already successful
        mock_upgrade_class.assert_not_called()
        # Should NOT write to RDS when there are no upgrade results
        mock_rds_client.overwrite_table_with_df.assert_not_called()

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_upgrade_failure(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test handling of upgrade failures."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],  # Record IDs
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],  # Cached records
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Mock upgrade to raise exception
        mock_upgrade_class.side_effect = Exception("Upgrade failed")

        # Run the function
        sync.run()

        # Verify that failure was recorded
        mock_rds_client.overwrite_table_with_df.assert_called_once()
        call_args = mock_rds_client.overwrite_table_with_df.call_args[0]
        df = call_args[0]
        self.assertEqual(df.iloc[0]["status"], "failed")
        self.assertEqual(df.iloc[0]["v1_id"], "record1")
        self.assertIsNone(df.iloc[0]["v2_id"])

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_upgrade_returns_none(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test handling when upgrade returns None."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],  # Record IDs
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],  # Cached records
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Mock upgrade to return None
        mock_upgrade_class.return_value = None

        # Run the function
        sync.run()

        # Verify that failure was recorded
        mock_rds_client.overwrite_table_with_df.assert_called_once()
        call_args = mock_rds_client.overwrite_table_with_df.call_args[0]
        df = call_args[0]
        self.assertEqual(df.iloc[0]["status"], "failed")
        self.assertEqual(df.iloc[0]["v1_id"], "record1")
        self.assertIsNone(df.iloc[0]["v2_id"])

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_existing_v2_record(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test handling when v2 record already exists."""
        mock_v1_client.retrieve_docdb_records.side_effect = [
            [{"_id": "record1"}],  # Record IDs
            [{"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}],  # Cached records
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Mock upgrade instance
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance

        # Mock existing v2 record
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        # Run the function
        sync.run()

        # Verify that record was added to batch update list
        mock_v2_client.insert_one_docdb_record.assert_not_called()
        # Since batch size is 100 and we only have 1 record, upsert should be called at the end
        mock_v2_client.upsert_list_of_docdb_records.assert_called_once()

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    @patch("aind_metadata_upgrader.sync.BATCH_SIZE", 2)  # Small batch size for testing
    def test_run_batch_processing(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test that batch processing works correctly."""
        # Setup multiple records
        records = [{"_id": f"record{i}"} for i in range(1, 4)]
        cached_records_batch1 = [
            {"_id": f"record{i}", "location": f"loc{i}", "last_modified": f"2023-01-0{i}"} for i in range(1, 3)
        ]
        cached_records_batch2 = [{"_id": "record3", "location": "loc3", "last_modified": "2023-01-03"}]

        mock_v1_client.retrieve_docdb_records.side_effect = [
            records,  # Record IDs
            cached_records_batch1,  # First batch
            cached_records_batch2,  # Second batch
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Mock upgrade instances
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance

        # Mock v2 client to return existing records (for batch update)
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        # Run the function
        sync.run()

        # Verify batch processing occurred
        # Should have 2 calls for batched records plus calls for v2 record checks
        self.assertGreaterEqual(mock_v1_client.retrieve_docdb_records.call_count, 3)
        # Should call upsert twice - once for the full batch and once for remaining records
        self.assertEqual(mock_v2_client.upsert_list_of_docdb_records.call_count, 2)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    @patch("aind_metadata_upgrader.sync.CHUNK_SIZE", 2)  # Small chunk size for testing
    def test_run_rds_chunking(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test that RDS chunking works correctly."""
        # Setup multiple records to exceed chunk size
        records = [{"_id": f"record{i}"} for i in range(1, 4)]
        cached_records = [
            {"_id": f"record{i}", "location": f"loc{i}", "last_modified": f"2023-01-0{i}"} for i in range(1, 4)
        ]

        mock_v1_client.retrieve_docdb_records.side_effect = [
            records,  # Record IDs
            cached_records,  # All cached records
        ]

        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Mock upgrade instances
        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance

        # Mock v2 client
        mock_v2_client.retrieve_docdb_records.side_effect = [
            [],  # No existing record for first
            [{"_id": "new_v2_id1"}],  # New record after insertion
            [],  # No existing record for second
            [{"_id": "new_v2_id2"}],  # New record after insertion
            [],  # No existing record for third
            [{"_id": "new_v2_id3"}],  # New record after insertion
        ]

        # Run the function
        sync.run()

        # Verify chunking occurred
        mock_rds_client.overwrite_table_with_df.assert_called_once()  # First chunk
        mock_rds_client.append_df_to_table.assert_called_once()  # Second chunk

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.logging")
    def test_run_no_records(self, mock_logging, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test handling when no records are found."""
        mock_v1_client.retrieve_docdb_records.return_value = []
        mock_rds_client.read_table.side_effect = Exception("Table not found")

        # Run the function
        sync.run()

        # Verify early return with logging
        mock_logging.info.assert_called_with("(METADATA VALIDATOR) No upgrade results to write to RDS")

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    def test_run_invalid_existing_table(self, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test handling when existing RDS table is invalid."""
        # Return a DataFrame without required columns
        invalid_df = pd.DataFrame([{"wrong_column": "value"}])
        mock_rds_client.read_table.return_value = invalid_df

        mock_v1_client.retrieve_docdb_records.return_value = []

        # Run the function
        sync.run()

        # Should treat as no existing table and continue

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_successful(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test run_one with successful upgrade and existing v2 record."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        # Mock no existing row in RDS
        mock_rds_client.execute_query.return_value = []

        mock_upgrade_instance = MagicMock()
        mock_upgrade_instance.metadata.location = "test_location"
        mock_upgrade_instance.metadata.name = "test_name"
        mock_upgrade_instance.metadata.model_dump.return_value = {"test": "data"}
        mock_upgrade_class.return_value = mock_upgrade_instance

        # Mock existing v2 record so upgrade_record returns a record to upsert
        mock_v2_client.retrieve_docdb_records.return_value = [{"_id": "existing_v2_id"}]

        sync.run_one("record1")

        mock_v2_client.upsert_one_docdb_record.assert_called_once()
        # Should call execute_query at least twice: once for SELECT, once for INSERT
        self.assertGreaterEqual(mock_rds_client.execute_query.call_count, 2)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    def test_run_one_record_not_found(self, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test run_one when record doesn't exist."""
        mock_v1_client.retrieve_docdb_records.return_value = []

        with self.assertRaises(ValueError):
            sync.run_one("nonexistent")

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_skip_condition(self, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test run_one skips already upgraded records."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        # Mock existing row with matching version and last_modified
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                _mapping={
                    "v1_id": "record1",
                    "v2_id": "v2_record1",
                    "upgrader_version": "1.0.0",
                    "status": "success",
                    "last_modified": "2023-01-01",
                }
            )
        ]
        mock_rds_client.execute_query.return_value = mock_result

        sync.run_one("record1")

        mock_v2_client.upsert_one_docdb_record.assert_not_called()
        # Should only call execute_query once for the SELECT check
        self.assertEqual(mock_rds_client.execute_query.call_count, 1)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_run_one_upgrade_failure(self, mock_upgrade_class, mock_v1_client, mock_v2_client, mock_rds_client):
        """Test run_one handles upgrade failures."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "record1", "location": "loc1", "last_modified": "2023-01-01"}
        ]
        # Mock no existing row in RDS
        mock_rds_client.execute_query.return_value = []
        mock_upgrade_class.side_effect = Exception("Upgrade failed")

        sync.run_one("record1")

        # Should call execute_query at least twice: once for SELECT, once for INSERT
        self.assertGreaterEqual(mock_rds_client.execute_query.call_count, 2)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "2.5.0")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_insert_new_record(self, mock_rds_client):
        """Test that update_rds_tracking correctly inserts a new record with all field values."""
        # Mock no existing row
        existing_row = None

        result = {
            "v1_id": "test_v1_id_123",
            "v2_id": "test_v2_id_456",
            "upgrader_version": "2.5.0",
            "last_modified": "2024-12-15T10:30:00",
            "status": "success",
        }

        sync.update_rds_tracking("test_v1_id_123", result, existing_row)

        # Verify execute_query was called once
        mock_rds_client.execute_query.assert_called_once()

        # Get the actual SQL query that was executed
        actual_query = mock_rds_client.execute_query.call_args[0][0]

        # Verify the query structure and content
        self.assertIn("INSERT INTO test_table", actual_query)
        self.assertIn("(v1_id, v2_id, upgrader_version, last_modified, status)", actual_query)
        self.assertIn("VALUES", actual_query)

        # Verify all values are correctly inserted
        self.assertIn("'test_v1_id_123'", actual_query)
        self.assertIn("'test_v2_id_456'", actual_query)
        self.assertIn("'2.5.0'", actual_query)
        self.assertIn("'2024-12-15T10:30:00'", actual_query)
        self.assertIn("'success'", actual_query)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "3.1.4")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_update_existing_record(self, mock_rds_client):
        """Test that update_rds_tracking correctly updates an existing record with all field values."""
        # Mock existing row
        existing_row = [
            {
                "v1_id": "old_v1_id_789",
                "v2_id": "old_v2_id",
                "upgrader_version": "1.0.0",
                "last_modified": "2023-01-01",
                "status": "success",
            }
        ]

        result = {
            "v1_id": "old_v1_id_789",
            "v2_id": "new_v2_id_999",
            "upgrader_version": "3.1.4",
            "last_modified": "2025-06-20T14:45:30",
            "status": "success",
        }

        sync.update_rds_tracking("old_v1_id_789", result, existing_row)

        # Verify execute_query was called once
        mock_rds_client.execute_query.assert_called_once()

        # Get the actual SQL query that was executed
        actual_query = mock_rds_client.execute_query.call_args[0][0]

        # Verify the query structure
        self.assertIn("UPDATE test_table", actual_query)
        self.assertIn("SET", actual_query)
        self.assertIn("WHERE v1_id = 'old_v1_id_789'", actual_query)

        # Verify all updated values are present in the SET clause
        self.assertIn("v2_id = 'new_v2_id_999'", actual_query)
        self.assertIn("upgrader_version = '3.1.4'", actual_query)
        self.assertIn("last_modified = '2025-06-20T14:45:30'", actual_query)
        self.assertIn("status = 'success'", actual_query)

    @patch("aind_metadata_upgrader.sync.rds_client")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.2.3")
    @patch("aind_metadata_upgrader.sync.REDSHIFT_TABLE_NAME", "test_table")
    def test_update_rds_tracking_failed_status(self, mock_rds_client):
        """Test that update_rds_tracking correctly handles failed upgrades with None v2_id."""
        existing_row = None

        result = {
            "v1_id": "failed_v1_id_555",
            "v2_id": None,
            "upgrader_version": "1.2.3",
            "last_modified": "2024-03-10T08:00:00",
            "status": "failed",
        }

        sync.update_rds_tracking("failed_v1_id_555", result, existing_row)

        # Verify execute_query was called
        mock_rds_client.execute_query.assert_called_once()

        # Get the actual SQL query
        actual_query = mock_rds_client.execute_query.call_args[0][0]

        # Verify INSERT structure
        self.assertIn("INSERT INTO test_table", actual_query)

        # Verify all values including None for v2_id and 'failed' status
        self.assertIn("'failed_v1_id_555'", actual_query)
        self.assertIn("'None'", actual_query)  # v2_id should be 'None' as string
        self.assertIn("'1.2.3'", actual_query)
        self.assertIn("'2024-03-10T08:00:00'", actual_query)
        self.assertIn("'failed'", actual_query)


if __name__ == "__main__":
    unittest.main()
