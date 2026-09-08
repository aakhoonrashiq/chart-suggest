"""Tests for the data profiler."""
import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from services.profiler import profile_dataset

DATA_DIR = os.path.join(os.path.dirname(__file__), "test_datasets")


def load(fname):
    return pd.read_csv(os.path.join(DATA_DIR, fname))


class TestDataset1Categorical:
    def test_basic(self):
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "test1", "dataset1_categorical.csv")
        assert p.rows == 5
        assert p.columns == 2
        assert p.has_categorical
        assert p.has_numeric
        assert not p.has_datetime
        assert not p.has_geo_latlon

    def test_column_types(self):
        df = load("dataset1_categorical.csv")
        p = profile_dataset(df, "test1", "dataset1_categorical.csv")
        assert "Product" in p.categorical_cols
        assert "Sales" in p.numeric_cols


class TestDataset2TimeSeries:
    def test_datetime_detected(self):
        df = load("dataset2_timeseries.csv")
        p = profile_dataset(df, "test2", "dataset2_timeseries.csv")
        assert p.has_datetime
        assert p.has_numeric
        assert len(p.datetime_cols) >= 1

    def test_revenue_numeric(self):
        df = load("dataset2_timeseries.csv")
        p = profile_dataset(df, "test2", "dataset2_timeseries.csv")
        assert "Revenue" in p.numeric_cols


class TestDataset3Numeric:
    def test_two_numerics(self):
        df = load("dataset3_numeric.csv")
        p = profile_dataset(df, "test3", "dataset3_numeric.csv")
        assert len(p.numeric_cols) == 2
        assert not p.has_datetime
        assert not p.has_categorical


class TestDataset4ThreeD:
    def test_three_numerics(self):
        df = load("dataset4_3d.csv")
        p = profile_dataset(df, "test4", "dataset4_3d.csv")
        assert len(p.numeric_cols) == 3


class TestDataset5Geographic:
    def test_geo_detected(self):
        df = load("dataset5_geographic.csv")
        p = profile_dataset(df, "test5", "dataset5_geographic.csv")
        assert p.has_geo_latlon
        assert len(p.geo_lat_cols) >= 1
        assert len(p.geo_lon_cols) >= 1


class TestDataset6Hierarchical:
    def test_hierarchy_detected(self):
        df = load("dataset6_hierarchical.csv")
        p = profile_dataset(df, "test6", "dataset6_hierarchical.csv")
        assert len(p.categorical_cols) >= 2
        assert p.has_hierarchy


class TestDataset7Flow:
    def test_flow_detected(self):
        df = load("dataset7_flow.csv")
        p = profile_dataset(df, "test7", "dataset7_flow.csv")
        assert p.has_flow
        assert len(p.flow_source_cols) >= 1
        assert len(p.flow_target_cols) >= 1


class TestDataset8Large:
    def test_large_detected(self):
        df = load("dataset8_large.csv")
        p = profile_dataset(df, "test8", "dataset8_large.csv")
        assert p.row_count_class == "large"
        assert len(p.numeric_cols) >= 2


class TestEdgeCases:
    def test_empty_csv(self):
        df = pd.DataFrame()
        # Should not crash — returns an empty profile
        p = profile_dataset(df, "empty", "empty.csv")
        assert p.rows == 0
        assert p.columns == 0

    def test_single_column(self):
        df = pd.DataFrame({"value": [1, 2, 3]})
        p = profile_dataset(df, "sc", "single.csv")
        assert p.columns == 1
        assert len(p.numeric_cols) == 1

    def test_missing_values(self):
        df = pd.DataFrame({
            "Product": ["A", None, "C", "D"],
            "Sales": [100, 200, None, 400],
        })
        p = profile_dataset(df, "mv", "missing.csv")
        assert p.column_profiles["Product"].missing_count == 1
        assert p.column_profiles["Sales"].missing_count == 1

    def test_constant_column(self):
        df = pd.DataFrame({"A": [1, 1, 1], "B": [1, 2, 3]})
        p = profile_dataset(df, "const", "const.csv")
        assert p.column_profiles["A"].is_constant

    def test_boolean_column(self):
        df = pd.DataFrame({"active": [True, False, True, False]})
        p = profile_dataset(df, "bool", "bool.csv")
        assert p.column_profiles["active"].semantic_type == "boolean"
