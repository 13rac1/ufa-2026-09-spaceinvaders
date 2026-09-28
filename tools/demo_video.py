"""Put game recordings side by side with a caption above each, for the demo video.

Usage: python tools/demo_video.py out.mp4 "caption one=a.mp4" "caption two=b.mp4" ...

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


def main(out: str, inputs: list[str]) -> None:
    clips, captions = [], []
    for item in inputs:
        caption, path = item.rsplit("=", 1)
        frames = [np.kron(f, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
                  for f in imageio.mimread(path, memtest=False)]
        clips.append(frames)
        captions.append(_caption(caption, frames[0].shape[1]))
    length = max(len(c) for c in clips)
    with imageio.get_writer(out, fps=FPS, macro_block_size=1) as writer:
        for i in range(length):
            panels = [np.vstack([cap, clip[min(i, len(clip) - 1)]])
                      for cap, clip in zip(captions, clips)]
            gap = np.zeros((panels[0].shape[0], 12, 3), dtype=np.uint8)
            row = panels[0]
            for panel in panels[1:]:
                row = np.hstack([row, gap, panel])
            writer.append_data(row)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
