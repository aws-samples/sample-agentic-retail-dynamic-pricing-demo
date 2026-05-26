"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Add project directories to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "cdk"))
