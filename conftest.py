"""Ensure the repository root is importable regardless of pytest's rootdir detection."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
