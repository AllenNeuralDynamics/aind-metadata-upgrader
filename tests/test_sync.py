"""Tests for the sync module helpers."""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from aind_metadata_upgrader import sync


class TestGetCacheRow(unittest.TestCase):
    """Tests for _get_cache_row."""

    def setUp(self):
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
        row = sync._get_cache_row(self.df, "rec1")
        self.assertEqual(row["v2_id"], "v2_1")
        self.assertEqual(row["status"], "success")

    def test_returns_empty_dict_when_not_found(self):
        row = sync._get_cache_row(self.df, "nonexistent")
        self.assertEqual(row, {})


class TestMakeFailureResult(unittest.TestCase):
    """Tests for _make_failure_result."""

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.2.3")
    def test_builds_correct_failure_dict(self):
        data = {"_id": "rec1", "last_modified": "2024-06-01"}
        result = sync._make_failure_result(data)
        self.assertEqual(result["v1_id"], "rec1")
        self.assertIsNone(result["v2_id"])
        self.assertEqual(result["upgrader_version"], "1.2.3")
        self.assertEqual(result["last_modified"], "2024-06-01")
        self.assertEqual(result["status"], "failed")

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_missing_last_modified_is_none(self):
        result = sync._make_failure_result({"_id": "rec1"})
        self.assertIsNone(result["last_modified"])


class TestUpgradeRecord(unittest.TestCase):
    """Tests for upgrade_record."""

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_model_dump_for_new_record(self, mock_upgrade_class):
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance

        result = sync.upgrade_record({"_id": "rec1"})

        mock_upgrade_class.assert_called_once_with({"_id": "rec1"})
        self.assertEqual(result, {"field": "value"})

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_sets_id_and_strips_qc_for_existing_record(self, mock_upgrade_class):
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value", "quality_control": {"some": "data"}}
        mock_upgrade_class.return_value = mock_instance

        result = sync.upgrade_record({"_id": "rec1"}, existing_v2_id="v2_abc")

        self.assertEqual(result["_id"], "v2_abc")
        self.assertNotIn("quality_control", result)

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_none_when_upgrade_is_falsy(self, mock_upgrade_class):
        mock_upgrade_class.return_value = None
        result = sync.upgrade_record({"_id": "rec1"})
        self.assertIsNone(result)


class TestAttemptUpgrade(unittest.TestCase):
    """Tests for _attempt_upgrade."""

    @patch("aind_metadata_upgrader.sync.Upgrade")
    def test_returns_model_on_success(self, mock_upgrade_class):
        mock_instance = MagicMock()
        mock_instance.metadata.model_dump.return_value = {"field": "value"}
        mock_upgrade_class.return_value = mock_instance

        model, failure = sync._attempt_upgrade({"_id": "rec1", "location": "loc1"}, None)

        self.assertIsNotNone(model)
        self.assertIsNone(failure)

    @patch("aind_metadata_upgrader.sync.Upgrade")
    @patch("aind_metadata_upgrader.sync.client_v2")
    def test_returns_failure_and_deletes_v2_on_exception(self, mock_v2_client, mock_upgrade_class):
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
        mock_upgrade_class.side_effect = RuntimeError("boom")

        model, failure = sync._attempt_upgrade({"_id": "rec1"}, None)

        self.assertIsNone(model)
        mock_v2_client.delete_one_record.assert_not_called()


class TestProcessRecord(unittest.TestCase):
    """Tests for _process_record — core skip/insert/upsert logic."""

    def _empty_df(self):
        return pd.DataFrame(columns=sync._ZS_COLUMNS)

    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_skips_up_to_date_record(self):
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
        mock_v2_client.upsert_one_docdb_record.side_effect = RuntimeError("db error")
        model = {"_id": "v2_1"}
        data = {"_id": "rec1", "last_modified": "2024-01-01"}
        results = []

        sync._flush_pending_upserts([(model, "loc1", "rec1", data)], results)

        self.assertEqual(results[0]["status"], "failed")

    def test_noop_when_empty(self):
        results = []
        sync._flush_pending_upserts([], results)
        self.assertEqual(results, [])


class TestBuildUpgradeSet(unittest.TestCase):
    """Tests for _build_upgrade_set — identifies which records need upgrading."""

    @patch("aind_metadata_upgrader.sync.client_v1")
    @patch("aind_metadata_upgrader.sync.upgrader_version", "1.0.0")
    def test_excludes_up_to_date_records(self, mock_v1_client):
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
        mock_v1_client.retrieve_docdb_records.return_value = [
            {"_id": "rec1", "last_modified": "2024-01-01"},
        ]
        result = sync._build_upgrade_set(["rec1"], pd.DataFrame(columns=sync._ZS_COLUMNS))
        self.assertEqual(result, ["rec1"])


class TestSaveResults(unittest.TestCase):
    """Tests for _save_results."""

    @patch("aind_metadata_upgrader.sync.custom")
    def test_insert_new_record(self, mock_custom):
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
