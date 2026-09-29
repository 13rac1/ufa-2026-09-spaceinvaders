"""Put game recordings side by side with a caption above each, for the demo video.

Usage: python tools/demo_video.py [--columns N] [--fps F] out.mp4 "caption one=a.mp4" ...

Panels fill rows of N (default: all in one row). --fps 30 plays at 2x, 45 at 3x.

Each input is a recording made with `python -m invaders run --video-dir DIR`. Frames are
scaled 3 times; a game that ends first keeps its last frame on screen.
"""

import sys

import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCALE = 3
CAPTION_PX = 64
FPS = 15


def _caption(text: str, width: int) -> np.ndarray:
    image = Image.new("RGB", (width, CAPTION_PX), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    for i, line in enumerate(text.split("|")):
        draw.text((10, 6 + 28 * i), line.strip(), fill=(255, 255, 255), font=font)
    return np.asarray(image)


def _grid(panels: list[np.ndarray], columns: int) -> np.ndarray:
    blank = np.zeros_like(panels[0])
    rows = []
    for start in range(0, len(panels), columns):
        row = panels[start : start + columns]
        row += [blank] * (columns - len(row))
        gap = np.zeros((row[0].shape[0], 12, 3), dtype=np.uint8)
        line = row[0]
        for panel in row[1:]:
            line = np.hstack([line, gap, panel])
        rows.append(line)
    gap = np.zeros((12, rows[0].shape[1], 3), dtype=np.uint8)
    grid = rows[0]
    for line in rows[1:]:
        grid = np.vstack([grid, gap, line])
    return grid


def main(out: str, inputs: list[str], columns: int = 0, fps: float = FPS) -> None:
    clips, captions = [], []
    for item in inputs:
        caption, path = item.rsplit("=", 1)
        frames = [np.kron(f, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
                  for f in imageio.mimread(path, memtest=False)]
        clips.append(frames)
        captions.append(_caption(caption, frames[0].shape[1]))
    length = max(len(c) for c in clips)
    with imageio.get_writer(out, fps=fps, macro_block_size=1) as writer:
        for i in range(length):
            panels = [np.vstack([cap, clip[min(i, len(clip) - 1)]])
                      for cap, clip in zip(captions, clips)]
            writer.append_data(_grid(panels, columns or len(panels)))


if __name__ == "__main__":
    args = sys.argv[1:]
    options = {}
    while args and args[0].startswith("--"):
        options[args[0][2:]] = float(args[1])
        args = args[2:]
    main(args[0], args[1:], int(options.get("columns", 0)), options.get("fps", FPS))
