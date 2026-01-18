"""
Pytest configuration for xeno-agent tests.
"""

import sys
from pathlib import Path

# Add src to path so we can import packages
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
