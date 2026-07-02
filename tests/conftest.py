"""
pytest 公共配置：把 backend/ 加入 sys.path，使 `import okx_client` / `import app`
能在仓库根目录直接 `pytest` 时正常工作（与 app.py 里 `import okx_client as okx` 一致）。
"""
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))
