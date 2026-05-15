"""Tests for the sync module helpers."""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from aind_metadata_upgrader import sync


class TestGetCacheRow(unittest.TestCase):
    """Tests for _get_cache_row."""

    def setUp(self):
        """Sets up a sample DataFrame for testing."""
        self.df = pd.DataFrame(
            [
                {
                    "v1_id": "rec1",
                    "v2_id": "v2_1",
                    "upgrader_version": "1.0.0",
                    "status": "success",
                    "last_modified": "2024-01-01",
                },
                {
                    "v1_id": "rec2",
                    "v2_id": None,
                    "upgrader_version": "1.0.0",
                    "status": "failed",
                    "last_modified": "2024-01-02",
                },
            ]
        )

    def test_returns_matching_row(self):
        """Tests that the correct row is returned for a given v1_id."""
        row = sync._get_cache_row(self.df, "rec1")
        self.assertEqual(row["v2_id"], "v2_1")
        self.assertEqual(row["status"], "success")

    def test_returns_empty_dict_when_not_found(self):
        """Tests that an empty dict is returned when no matching v1_id is found."""
        row = sync._get_cache_row(self.df, "nonexistent")
        self.assertEqual(row, {})


class TestMakeFailureResult(unittest.TestCase):
    """Tests for _make_failure_result."""

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.2.3")
    def test_builds_correct_failure_dict(self):
        """Tests that the failure dict is built correctly from input data."""
        data = {"_id": "rec1", "last_modified": "2024-06-01"}
        result = sync._make_failure_result(data)
        self.assertEqual(result["v1_id"], "rec1")
        self.assertIsNone(result["v2_id"])
        self.assertEqual(result["upgrader_version"], "1.2.3")
        self.assertEqual(result["last_modified"], "2024-06-01")
        self.assertEqual(result["status"], "failed")

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_missing_last_modified_is_none(self):
        """Tests that if last_modified is missing from input data, it is set to None in the result."""
        result = sync._make_failure_result({"_id": "rec1"})
        self.assertIsNone(result["last_modified"])


class TestUpgradeRecord(unittest.TestCase):
    """Tests for upgrade_record."""

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_model_dump_for_new_record(self, mock_upgrade_class):
        """Tests that for a new record, the model_dump of the Upgrade instance is returned."""
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance

        result = sync.upgrade_record({"_id": "rec1"})

        mock_upgrade_class.assert_called_once_with({"_id": "rec1"})
        self.assertEqual(result, {"field": "value"})

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_sets_id_and_strips_qc_for_existing_record(self, mock_upgrade_class):
        """Tests that for an existing record"""
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value", "quality_control": {"some": "data"}}
        mock_upgrade_class.return_value = mock_instance

        result = sync.upgrade_record({"_id": "rec1"}, existing_v2_id="v2_abc")

        self.assertEqual(result["_id"], "v2_abc")
        self.assertNotIn("quality_control", result)

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_none_when_upgrade_is_falsy(self, mock_upgrade_class):
        """Tests that if the Upgrade instance is falsy (e.g. None), upgrade_record returns None."""
        mock_upgrade_class.return_value = None
        result = sync.upgrade_record({"_id": "rec1"})
        self.assertIsNone(result)


class TestAttemptUpgrade(unittest.TestCase):
    """Tests for _attempt_upgrade."""

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_model_on_success(self, mock_upgrade_class):
        """Tests that a successful upgrade returns the model and no failure result."""
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance

        model, failure = sync._attempt_upgrade({"_id": "rec1", "location": "loc1"}, None)

        self.assertIsNotNone(model)
        self.assertIsNone(failure)

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.client_v2")
    def test_returns_failure_and_deletes_v2_on_exception(self, mock_v2_client, mock_upgrade_class):
        """Tests that when upgrade raises an exception, a failure result is returned and the V2 record is deleted."""
        mock_upgrade_class.side_effect = RuntimeError("boom")
        mock_v2_client.retrieve_docdb_records.return_value = []
        existing_v2 = {"_id": "v2_1"}

        model, failure = sync._attempt_upgrade({"_id": "rec1", "location": "loc1"}, existing_v2)

        self.assertIsNone(model)
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(failure["v1_id"], "rec1")
        mock_v2_client.delete_one_record.assert_called_once_with("v2_1")

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.client_v2")
    def test_no_v2_delete_when_no_location(self, mock_v2_client, mock_upgrade_class):
        """Tests that V2 deletion is skipped when the record has no location field."""
        mock_upgrade_class.side_effect = RuntimeError("boom")

        model, failure = sync._attempt_upgrade({"_id": "rec1"}, None)

        self.assertIsNone(model)
        mock_v2_client.delete_one_record.assert_not_called()


class TestProcessRecord(unittest.TestCase):
    """Tests for _process_record — core skip/insert/upsert logic."""

    def _empty_df(self):
        """Returns an empty DataFrame with the ZS tracking columns."""
        return pd.DataFrame(columns=sync._ZS_COLUMNS)

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_skips_up_to_date_record(self):
        """Tests that a record already upgraded with the current version and same last_modified is skipped."""
        df = pd.DataFrame(
            [
                {
                    "v1_id": "rec1",
                    "v2_id": "v2_1",
                    "upgrader_version": "1.0.0",
                    "status": "success",
                    "last_modified": "2024-01-01",
                }
            ]
        )
        data = {"_id": "rec1", "last_modified": "2024-01-01"}
        results, upserts = [], []
        status = sync._process_record(data, df, results, upserts)
        self.assertEqual(status, "skipped")
        self.assertEqual(results, [])
        self.assertEqual(upserts, [])

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_inserts_new_record(self, mock_v2_client, mock_upgrade_class):
        """Tests that a new record (no existing V2) is inserted and a success result is appended."""
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance
        mock_v2_client.retrieve_docdb_records.return_value = []
        mock_v2_client.insert_one_docdb_record.return_value.json.return_value = {"insertedId": "new_v2"}

        data = {"_id": "rec1", "location": "loc1", "last_modified": "2024-01-01"}
        results, upserts = [], []
        status = sync._process_record(data, self._empty_df(), results, upserts)

        self.assertEqual(status, "inserted")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["v2_id"], "new_v2")

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_queues_upsert_for_existing_v2(self, mock_upgrade_class):
        """Tests that when a V2 record already exists, the upgrade is queued for upsert rather than inserted."""
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance

        data = {"_id": "rec1", "location": "loc1", "last_modified": "2024-01-01"}
        existing_v2 = {"_id": "existing_v2"}
        results, upserts = [], []
        status = sync._process_record(data, self._empty_df(), results, upserts, v2_record=existing_v2)

        self.assertEqual(status, "queued_upsert")
        self.assertEqual(len(upserts), 1)
        self.assertEqual(results, [])

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_returns_failed_on_upgrade_error(self, mock_v2_client, mock_upgrade_class):
        """Tests that a failed upgrade results in a 'failed' status being appended to results."""
        mock_upgrade_class.side_effect = RuntimeError("fail")
        mock_v2_client.retrieve_docdb_records.return_value = []

        data = {"_id": "rec1", "location": "loc1", "last_modified": "2024-01-01"}
        results, upserts = [], []
        status = sync._process_record(data, self._empty_df(), results, upserts)

        self.assertEqual(status, "failed")
        self.assertEqual(results[0]["status"], "failed")


class TestFlushPendingUpserts(unittest.TestCase):
    """Tests for _flush_pending_upserts."""

    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_upserts_each_record_and_records_success(self, mock_v2_client):
        """Tests that each pending record is upserted and a success result is recorded."""
        model = {"_id": "v2_1", "field": "val"}
        data = {"_id": "rec1", "last_modified": "2024-01-01"}
        pending = [(model, "loc1", "rec1", data)]
        results = []

        sync._flush_pending_upserts(pending, results)

        mock_v2_client.upsert_one_docdb_record.assert_called_once_with(record=model)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["v1_id"], "rec1")
        self.assertEqual(results[0]["v2_id"], "v2_1")

    @patch("aind_metadata_upgrader.sync.client_v2")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_records_failure_on_upsert_exception(self, mock_v2_client):
        """Tests that a failed upsert is recorded as a failure result rather than raising."""
        mock_v2_client.upsert_one_docdb_record.side_effect = RuntimeError("db error")
        model = {"_id": "v2_1"}
        data = {"_id": "rec1", "last_modified": "2024-01-01"}
        results = []

        sync._flush_pending_upserts([(model, "loc1", "rec1", data)], results)

        self.assertEqual(results[0]["status"], "failed")

    def test_noop_when_empty(self):
        """Tests that passing an empty pending list does nothing."""
        results = []
        sync._flush_pending_upserts([], results)
        self.assertEqual(results, [])


class TestBuildUpgradeSet(unittest.TestCase):
    """Tests for _build_upgrade_set — identifies which records need upgrading."""

    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_excludes_up_to_date_records(self, mock_v1_client):
        """Tests that records already at the current upgrader version"""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "rec1", "last_modified": "2024-01-01"},
            {"_id": "rec2", "last_modified": "2024-01-02"},
        ]
        df = pd.DataFrame(
            [
                {"v1_id": "rec1", "upgrader_version": "1.0.0", "last_modified": "2024-01-01", "status": "success"},
            ]
        )
        result = sync._build_upgrade_set(["rec1", "rec2"], df)
        self.assertNotIn("rec1", result)
        self.assertIn("rec2", result)

    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_includes_all_when_cache_empty(self, mock_v1_client):
        """Tests that all records are included in the upgrade set when the cache is empty."""
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "rec1", "last_modified": "2024-01-01"},
        ]
        result = sync._build_upgrade_set(["rec1"], pd.DataFrame(columns=sync._ZS_COLUMNS))
        self.assertEqual(result, ["rec1"])


class TestSaveResults(unittest.TestCase):
    """Tests for _save_results."""

    @patch("aind_metadata_upgrader.sync.custom")
    def test_insert_new_record(self, mock_custom):
        """Tests that a new result row is written to the ZS table."""
        mock_custom.side_effect = lambda *a, **kw: kw["df"] if kw.get("df") is not None else None
        base_df = pd.DataFrame(columns=sync._ZS_COLUMNS)
        result = {
            "v1_id": "rec1",
            "v2_id": "v2_1",
            "upgrader_version": "1.0.0",
            "last_modified": "2024-01-01",
            "status": "success",
        }
        sync._save_results(base_df, [result])
        df = mock_custom.call_args.kwargs["df"]
        self.assertEqual(df.iloc[0]["v1_id"], "rec1")
        self.assertEqual(df.iloc[0]["status"], "success")

    @patch("aind_metadata_upgrader.sync.custom")
    def test_overwrites_existing_row_by_v1_id(self, mock_custom):
        """Tests that an existing row for the same v1_id is replaced rather than duplicated."""
        mock_custom.side_effect = lambda *a, **kw: kw["df"] if kw.get("df") is not None else None
        base_df = pd.DataFrame(
            [
                {
                    "v1_id": "rec1",
                    "v2_id": "old_v2",
                    "upgrader_version": "0.9.0",
                    "last_modified": "2023-01-01",
                    "status": "success",
                }
            ]
        )
        result = {
            "v1_id": "rec1",
            "v2_id": "new_v2",
            "upgrader_version": "1.0.0",
            "last_modified": "2024-01-01",
            "status": "success",
        }
        sync._save_results(base_df, [result])
        df = mock_custom.call_args.kwargs["df"]
        self.assertEqual(len(df[df["v1_id"] == "rec1"]), 1)
        self.assertEqual(df[df["v1_id"] == "rec1"].iloc[0]["v2_id"], "new_v2")

    @patch("aind_metadata_upgrader.sync.custom")
    def test_failed_record_has_none_v2_id(self, mock_custom):
        """Tests that a failed result is stored with a None v2_id and 'failed' status."""
        mock_custom.side_effect = lambda *a, **kw: kw["df"] if kw.get("df") is not None else None
        base_df = pd.DataFrame(columns=sync._ZS_COLUMNS)
        result = {
            "v1_id": "rec1",
            "v2_id": None,
            "upgrader_version": "1.0.0",
            "last_modified": "2024-01-01",
            "status": "failed",
        }
        sync._save_results(base_df, [result])
        df = mock_custom.call_args.kwargs["df"]
        self.assertIsNone(df.iloc[0]["v2_id"])
        self.assertEqual(df.iloc[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
