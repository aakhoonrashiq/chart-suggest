"""
CSV service — load, validate, and store uploaded CSV files.
"""
from __future__ import annotations

import io
import logging
import uuid
from typing import Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# In-memory dataset store: dataset_id → (DataFrame, filename)
_DATASET_STORE: Dict[str, Tuple[pd.DataFrame, str]] = {}

MAX_BYTES = 50 * 1024 * 1024  # 50 MB hard limit


class CSVValidationError(Exception):
    pass


def load_csv(content: bytes, filename: str) -> str:
    """
    Validate and load a CSV from raw bytes. Returns a dataset_id.
    Raises CSVValidationError with a helpful message on failure.
    """
    if len(content) == 0:
        raise CSVValidationError("Uploaded file is empty.")
    if len(content) > MAX_BYTES:
        raise CSVValidationError(
            f"File exceeds 50 MB limit ({len(content) / 1_048_576:.1f} MB). "
            "Please reduce file size."
        )

    # Try multiple encodings
    df = None
    last_err = None
    for encoding in ["utf-8", "latin-1", "utf-16", "cp1252"]:
        try:
            df = pd.read_csv(
                io.BytesIO(content),
                encoding=encoding,
                on_bad_lines="skip",
                low_memory=False,
            )
            logger.info(f"CSV decoded with encoding={encoding}")
            break
        except Exception as exc:
            last_err = exc
            continue

    if df is None:
        raise CSVValidationError(f"Could not parse CSV: {last_err}")

    if df.empty:
        raise CSVValidationError("CSV file has no data rows.")

    if len(df.columns) == 0:
        raise CSVValidationError("CSV file has no columns.")

    # Detect headerless files: if all columns look like "Unnamed: N"
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if len(unnamed) == len(df.columns):
        raise CSVValidationError(
            "CSV appears to have no header row. "
            "Please add column names as the first row."
        )

    # Deduplicate column names
    cols = list(df.columns)
    seen: Dict[str, int] = {}
    new_cols = []
    for c in cols:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    dataset_id = str(uuid.uuid4())
    _DATASET_STORE[dataset_id] = (df, filename)
    logger.info(
        f"CSV loaded: id={dataset_id} rows={len(df)} cols={len(df.columns)} file={filename}"
    )
    return dataset_id


def get_dataset(dataset_id: str) -> Tuple[pd.DataFrame, str]:
    """Return (DataFrame, filename) for a dataset_id."""
    if dataset_id not in _DATASET_STORE:
        raise KeyError(f"Dataset '{dataset_id}' not found. It may have expired.")
    return _DATASET_STORE[dataset_id]


def list_datasets() -> Dict[str, str]:
    """Return {dataset_id: filename} for all loaded datasets."""
    return {did: fname for did, (_, fname) in _DATASET_STORE.items()}
