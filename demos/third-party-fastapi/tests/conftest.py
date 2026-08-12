"""
Pytest config for importing backend modules from this demo directory.
"""
import os
import sys

os.environ.setdefault("OKX_FASTAPI_DEMO_SKIP_DOTENV", "1")

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
