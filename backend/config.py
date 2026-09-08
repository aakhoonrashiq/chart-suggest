"""
Centralized configuration for Chart Suggest API.
Allows backend configuration of Top-N defaults and limits.
"""
import os

DEFAULT_TOP_N: int = int(os.getenv("DEFAULT_TOP_N", 5))
MAX_TOP_N: int = int(os.getenv("MAX_TOP_N", 30))
MIN_TOP_N: int = int(os.getenv("MIN_TOP_N", 1))

# Minimum chart suitability score (0-100) a chart must achieve to be recommended.
# This is a backend-controlled constant — it is NOT user-configurable.
# Charts scoring strictly below this value are always excluded.
MIN_SCORE: int = 60
