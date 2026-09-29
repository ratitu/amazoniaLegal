#!/usr/bin/env python3
"""Check the rendered timelapse: projection, encoding and animation.

I cannot look at the images, so every property that matters is measured instead:
the spots must land on the pixels the Mercator math says they should, they must
survive GIF quantisation and delta encoding, and consecutive frames must differ.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageSequence

import make_gif

GIF = make_gif.BASE / "focos_timelapse.gif"
INPUT = make_gif.BASE / "clipped"
SIZE = (1600, 1200)
ZOOM = 6
SPOT_RGB = np.array([255, 77, 26])
# The renderer anchors the date label at transAxes (0.5, 0.975) and the count at
# (0.5, 0.012), both at zorder 4, above the spots at zorder 2-3. A spot
# projected under either label is hidden by design and cannot be checked. These
# rects are that layout plus the text height and stroke width. The test has to
# be geometric: a colour test cannot tell white text from cloud, or the #101418
# stroke from dark water, and a colour test measured here excused 0.7% of
# random windows in open terrain.
LABEL_RECTS = ((655, 25, 945, 82), (685, 1150, 915, 1195))


def is_spot(pixels: np.ndarray) -> np.ndarray:
    # Match the spot core by colour distance, not red dominance: the Amazon
    # imagery is brown and would satisfy any red-dominance test. The cast is
    # essential -- in uint8 the subtraction wraps and flags the whole frame.
    return np.abs(pixels.astype(int) - SPOT_RGB).sum(2) < 90


def under_label(x: float, y: float) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in LABEL_RECTS)


def mercator_y_is_inverse_gudermannian() -> bool:
    # Independent guard: Mercator y must be the inverse gudermannian,
    # ln(tan(pi/4 + phi/2))/pi, not the forward gudermannian atan(sinh(phi))
    # (the original make_gif bug, which displaced latitudes up to ~66 km
    # across the Amazon band). Checked against the closed form so this does
    # not restate make_gif's own math.
    lat = np.array([5.2696, -18.0416, 10.0, -10.0, 45.0, -45.0])
    _, y = make_gif.to_mercator(np.zeros_like(lat), lat)
    want = 0.5 - np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) / np.pi
    return bool(np.allclose(y, want, atol=1e-9))


def main() -> None:
    files = sorted(INPUT.glob("focos_diario_br_*.csv"))
    geom = make_gif.load_boundary()
    west, south, east, north = map(float, geom.bounds)

    merc_ok = mercator_y_is_inverse_gudermannian()
    print(f"E  to_mercator y = inverse gudermannian ln(tan(pi/4+phi/2))/pi "
          f"at 5.27,-18.04,+/-10,+/-45: {merc_ok}")
    assert merc_ok, "to_mercator y is not ln(tan(pi/4+phi/2))/pi"

    # Re-derive the exact frame window make_gif used, so the locality check is
    # an independent confirmation of that projection rather than a restatement.
    width, height = SIZE
    px0, py0 = make_gif.world_pixels(west, north, ZOOM)
    px1, py1 = make_gif.world_pixels(east, south, ZOOM)
    aspect = width / height
    span_x, span_y = px1 - px0, py1 - py0
    if span_x / span_y < aspect:
        grow = (span_y * aspect - span_x) / 2
        px0, px1 = px0 - grow, px1 + grow
    else:
        grow = (span_x / aspect - span_y) / 2
        py0, py1 = py0 - grow, py1 + grow
    scale_x, scale_y = width / (px1 - px0), height / (py1 - py0)

    gif = Image.open(GIF)
    decoded = [f.convert("RGB") for f in ImageSequence.Iterator(gif)]
    durations = [f.info.get("duration") for f in ImageSequence.Iterator(Image.open(GIF))]

    print(f"A  gif frames {len(decoded)}  expect {len(files)}")
    print(f"A  gif size {gif.size}  expect {SIZE}   loop {gif.info.get('loop')}  "
          f"durations {sorted(set(durations))} ms  {GIF.stat().st_size / 1e6:.1f} MB")
    assert len(decoded) == len(files), "frame count mismatch"
    assert gif.size == SIZE
    assert set(durations) == {500}, f"frame durations {set(durations)} != 500 ms (2 fps)"

    misses = total_sampled = covered = 0
    spot_counts, csv_counts = [], []
    for index, path in enumerate(files):
        arr = np.asarray(decoded[index])
        mask = is_spot(arr)
        spot_counts.append(int(mask.sum()))
        lons, lats = make_gif.read_points(path)
        csv_counts.append(lons.size)

        ys, xs = np.nonzero(mask)
        rng = np.random.default_rng(index)
        if xs.size and lons.size:
            pick = rng.choice(lons.size, size=min(40, lons.size), replace=False)
            sx, sy = make_gif.world_pixels(lons[pick], lats[pick], ZOOM)
            want_x, want_y = (sx - px0) * scale_x, (sy - py0) * scale_y
            for tx, ty in zip(want_x, want_y):
                if not (0 <= tx < width and 0 <= ty < height):
                    misses += 1  # off-frame, cannot be checked here
                    continue
                total_sampled += 1
                x0, x1 = max(int(tx) - 3, 0), min(int(tx) + 4, width)
                y0, y1 = max(int(ty) - 3, 0), min(int(ty) + 4, height)
                if mask[y0:y1, x0:x1].any():
                    continue
                if under_label(tx, ty):
                    covered += 1
                    continue
                misses += 1
        else:
            misses += 1

    print(f"B  spots located {total_sampled - misses}/{total_sampled} within 3 px "
          f"of their projected position  ({covered} hidden under the text label)")
    assert misses == 0, f"{misses} sampled spots missing or off-frame"

    empty = [i for i, c in enumerate(spot_counts) if c == 0]
    print(f"C  spot pixels per frame: min {min(spot_counts)} max {max(spot_counts)}  "
          f"frames with none {len(empty)}")
    assert not empty, f"frames with no spots drawn: {empty}"
    assert max(range(27), key=lambda i: spot_counts[i]) == max(range(27), key=lambda i: csv_counts[i])
    assert max(range(27), key=lambda i: csv_counts[i]) == 20, "2026-09-21 should be the busiest day"

    diffs = [int(np.abs(np.asarray(decoded[i + 1]).astype(int)
                        - np.asarray(decoded[i]).astype(int)).sum()) for i in range(26)]
    print(f"D  consecutive frame difference: min {min(diffs):,} max {max(diffs):,} "
          f"(0 would mean a frozen animation)")
    assert min(diffs) > 0, "two consecutive frames are identical"

    print("\nOK - all checks passed")


if __name__ == "__main__":
    main()
