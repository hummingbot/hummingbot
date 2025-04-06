"""
Make `python -m ptpython` an alias for running `./ptpython`.
"""

from __future__ import annotations

from .entry_points.run_ptpython import run

run()
