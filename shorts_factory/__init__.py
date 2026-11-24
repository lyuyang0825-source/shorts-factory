"""shorts-factory: 选题到分镜包的生产流水线（离线模板基线）。"""

__version__ = "0.1.0"

from .planner import Brief, Shot, build_plan, build_hooks
from .platforms import build_variants
from .compliance import check
from .subtitles import build_srt, build_voiceover
from .render import render_video, render_cover

__all__ = [
    "Brief",
    "Shot",
    "build_plan",
    "build_hooks",
    "build_variants",
    "check",
    "build_srt",
    "build_voiceover",
    "render_video",
    "render_cover",
]
