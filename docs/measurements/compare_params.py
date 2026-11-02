#!/usr/bin/env python3
# Compare two parameter files frame by frame.
#
# Usage: compare_params.py reference.param candidate.param
#
# Both files may be GnuspeechSA's (with a header) or GamaTTS's (frames only):
# every line with exactly 16 numbers counts as one frame. Prints the frame
# counts, the largest absolute difference per parameter, the pitch ranges,
# and the frames where a parameter other than pitch differs by more than
# --tolerance (default 0.006, just above GnuspeechSA's 3-decimal rounding).
#
# Public domain. Written 2026-10-16 for docs/07-measurements.md.

import argparse

NAMES = ("pitch glotVol aspVol fricVol fricPos fricCF fricBW "
         "r1 r2 r3 r4 r5 r6 r7 r8 velum").split()


def load(path):
    frames = []
    with open(path) as f:
        for line in f:
            fields = line.split()
            if len(fields) != 16:
                continue
            try:
                frames.append([float(x) for x in fields])
            except ValueError:
                pass
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("candidate")
    ap.add_argument("--tolerance", type=float, default=0.006)
    args = ap.parse_args()

    a = load(args.reference)
    b = load(args.candidate)
    n = min(len(a), len(b))
    print(f"frames: reference {len(a)}, candidate {len(b)}")
    for c, name in enumerate(NAMES):
        d = max(abs(a[i][c] - b[i][c]) for i in range(n))
        print(f"  {name:8s} max |diff| {d:.4f}")
    pa = [r[0] for r in a]
    pb = [r[0] for r in b]
    print(f"pitch range: reference {min(pa):.2f}..{max(pa):.2f}, "
          f"candidate {min(pb):.2f}..{max(pb):.2f}")

    runs = {}
    for i in range(n):
        for c in range(1, 16):
            if abs(a[i][c] - b[i][c]) > args.tolerance:
                runs.setdefault(NAMES[c], []).append(i)
    for name, frames in runs.items():
        print(f"{name}: {len(frames)} frames beyond tolerance, "
              f"frames {frames[0]}..{frames[-1]}")
    if not runs:
        print("no non-pitch parameter beyond tolerance")


if __name__ == "__main__":
    main()
