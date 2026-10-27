"""Private process entry point: isolate CTranslate2's CUDA runtime from PyTorch."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from tools.analysis.transcriber import Transcriber
from tools.base_tool import ToolResult


def main():
    try:
        result = Transcriber().execute(json.load(sys.stdin))
    except Exception as exc:
        result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")
    print(json.dumps(asdict(result)))


if __name__ == "__main__":
    main()
