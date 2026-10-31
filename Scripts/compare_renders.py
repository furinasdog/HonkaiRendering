"""Arrange unretouched reference/render crops from a local JSON manifest (Matplotlib + Pillow)."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("manifest", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--font", type=Path)
args = parser.parse_args()
data = json.loads(args.manifest.read_text(encoding="utf-8"))
rows, columns = data["rows"], data["columns"]
assert rows and columns
font = FontProperties(fname=str(args.font)) if args.font else FontProperties()
fig, axes = plt.subplots(len(rows), len(columns), squeeze=False,
                         figsize=(4 * len(columns), 6 * len(rows)), dpi=150, facecolor="#20242b")
for row_index, row in enumerate(rows):
    assert len(row["images"]) == len(columns), row["name"]
    for col_index, item in enumerate(row["images"]):
        path = args.manifest.parent / item["path"]
        with Image.open(path) as im:
            x0, y0, x1, y1 = item.get("crop", [0, 0, im.width, im.height])
            assert 0 <= x0 < x1 <= im.width and 0 <= y0 < y1 <= im.height, path
            ax = axes[row_index, col_index]
            ax.imshow(im.convert("RGB"), interpolation="nearest")
            ax.set_xlim(x0, x1)
            ax.set_ylim(y1, y0)
            ax.axis("off")
            ax.set_title(row["name"] + " · " + columns[col_index], fontproperties=font, color="white")
fig.suptitle(data["title"], fontproperties=font, color="white", fontsize=16)
fig.text(.5, .015, data["note"], ha="center", fontproperties=font, color="#bfc6d2", fontsize=9)
fig.tight_layout(rect=(0, .035, 1, .97))
args.output.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.output, facecolor=fig.get_facecolor())
plt.close(fig)
print(args.output.resolve())
