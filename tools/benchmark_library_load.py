from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.constants import LIBRARY_CACHE_FILE_NAME
from app.controllers.metadata_controller import MetadataController
from app.services.library_cache_service import LibraryCache


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark MokaMusic library loading.")
    parser.add_argument("folder", help="Music folder to load.")
    parser.add_argument("--runs", type=int, default=2, help="Number of load runs. Default: 2.")
    parser.add_argument(
        "--cache",
        default=LIBRARY_CACHE_FILE_NAME,
        help=f"SQLite cache path. Default: {LIBRARY_CACHE_FILE_NAME}.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Delete the selected cache file before the first run.",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        print(json.dumps({"error": f"Folder does not exist: {folder}"}, indent=2))
        return 1

    cache_path = Path(args.cache)
    if args.clear_cache and cache_path.exists():
        cache_path.unlink()

    runs = max(1, int(args.runs or 1))
    results = []
    cache = LibraryCache(cache_path)
    for run_index in range(1, runs + 1):
        controller = MetadataController(library_cache=cache)
        start = time.perf_counter()
        files = controller.cargar_archivos_mp3(str(folder))
        elapsed = time.perf_counter() - start
        metrics = controller.load_metrics_snapshot()
        results.append(
            {
                "run": run_index,
                "files": len(files),
                "elapsed_seconds": round(elapsed, 4),
                "metrics": metrics,
            }
        )

    print(
        json.dumps(
            {
                "folder": str(folder.resolve()),
                "cache": str(cache_path.resolve()),
                "runs": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
