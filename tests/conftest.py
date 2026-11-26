import os
import sys
import tempfile
from pathlib import Path

# Tests never touch the developer's ./.data: point DATA_DIR at a fresh temp folder before the app is imported.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="bolo-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
