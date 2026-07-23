"""Replay calibration sample frames offline through the chroma detector.

Usage:
    python -m src.tools.replay_calibration_samples calibration_samples/20260606-101530

The directory must contain ``blue/``, ``pink/`` and ``empty/`` sub-folders
of raw PNG frames as written by the vision daemon during calibration.

For each labelled folder we report:
  - per-frame median/p95/max chroma
  - what the live detector ``_analyze_frame`` would report (blue/pink/none)
  - aggregate accuracy vs. the folder name

Also writes ``<dir>/replay_debug/<label>_<idx>.png`` with the annotated
debug overlay so we can eyeball false positives/negatives.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

import cv2

from src.hardware.usb_camera import USBCamera


def _build_camera(chroma_threshold: int, min_area: int) -> USBCamera:
    cam = USBCamera()
    cam.set_chroma_threshold(chroma_threshold)
    cam.add_color("blue", min_area=min_area, min_dimension=5)
    cam.add_color("pink", min_area=min_area, min_dimension=5)
    return cam


def _classify(cam: USBCamera, frame) -> tuple[str | None, dict]:
    results = cam._analyze_frame(frame)  # noqa: SLF001 — intentional offline reuse
    present = [name for name, r in results.items() if r.present]
    if not present:
        return None, {}
    best = max(present, key=lambda n: results[n].area)
    return best, {n: results[n].area for n in present}


def replay(root: Path, chroma_threshold: int, min_area: int, save_debug: bool) -> int:
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    cam = _build_camera(chroma_threshold, min_area)
    debug_dir = root / "replay_debug"
    if save_debug:
        debug_dir.mkdir(exist_ok=True)

    overall_correct = 0
    overall_total = 0

    for label_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "replay_debug"):
        label = label_dir.name
        png_paths = sorted(label_dir.glob("*.png"))
        if not png_paths:
            continue

        decisions: Counter[str] = Counter()
        stats_acc = {"median_chroma": 0.0, "p95_chroma": 0.0, "max_chroma": 0.0}
        for idx, path in enumerate(png_paths):
            frame = cv2.imread(str(path))
            if frame is None:
                continue
            stats = cam.chroma_stats(frame)
            for k in stats_acc:
                stats_acc[k] += stats[k]
            verdict, _areas = _classify(cam, frame)
            decisions[verdict or "none"] += 1
            if save_debug:
                annotated = cam.get_annotated_debug_frame(frame)
                cv2.imwrite(str(debug_dir / f"{label}_{idx:03d}.png"), annotated)

        n = len(png_paths)
        for k in stats_acc:
            stats_acc[k] /= n

        expected = "none" if label == "empty" else label
        correct = decisions.get(expected, 0)
        overall_correct += correct
        overall_total += n

        print(
            f"[{label:>5}] n={n:3d}  "
            f"median_C={stats_acc['median_chroma']:5.1f}  "
            f"p95_C={stats_acc['p95_chroma']:5.1f}  "
            f"max_C={stats_acc['max_chroma']:5.1f}  "
            f"decisions={dict(decisions)}  "
            f"accuracy={correct}/{n} ({100*correct/n:.0f}%)"
        )

    if overall_total:
        print(
            f"\nOverall: {overall_correct}/{overall_total} "
            f"({100*overall_correct/overall_total:.1f}%) at "
            f"chroma_threshold={chroma_threshold}, min_area={min_area}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Calibration session dir")
    parser.add_argument("--chroma-threshold", type=int, default=25)
    parser.add_argument("--min-area", type=int, default=500)
    parser.add_argument(
        "--no-debug-png",
        action="store_true",
        help="Skip writing annotated debug PNGs",
    )
    args = parser.parse_args()
    return replay(
        args.directory,
        chroma_threshold=args.chroma_threshold,
        min_area=args.min_area,
        save_debug=not args.no_debug_png,
    )


if __name__ == "__main__":
    raise SystemExit(main())
