from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so "import Codes" works no matter where you run from
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from Codes.__main__ import main  # calls PipetGui.main under the hood

if __name__ == "__main__":
    raise SystemExit(main())
