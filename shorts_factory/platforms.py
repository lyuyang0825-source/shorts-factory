"""多平台适配：规格、标题、话题、改版建议与 ffmpeg 命令。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .planner import Brief, Shot

PLATFORMS = {
    "douyin": {
        "label": "抖音",
        "aspect": "9:16",
        "size": (1080, 1920),
        "max_s": 300,
        "title_limit": 30,
        "hook_s": 3,
        "note": "前 3 秒决定完播，钩子不要放进场动画",
    },
    "shipinhao": {
        "label": "视频号",
        "aspect": "9:16",
        "size": (1080, 1920),
        "max_s": 300,
        "title_limit": 20,
        "hook_s": 3,
        "note": "标题更短，社交推荐依赖转发，结尾 CTA 要明确",
    },
    "xiaohongshu": {
        "label": "小红书",
        "aspect": "3:4",
        "size": (1080, 1440),
        "max_s": 300,
        "title_limit": 20,
        "hook_s": 2,
        "note": "封面文字比口播更重要，标题带情绪或身份标签",
    },
    "bilibili": {
        "label": "B 站",
        "aspect": "16:9",
        "size": (1920, 1080),
        "max_s": 600,
        "title_limit": 40,
        "hook_s": 5,
        "note": "可容纳更长解释，建议补一张原理图或数据来源",
    },
    "kuaishou": {
        "label": "快手",
        "aspect": "9:16",
        "size": (1080, 1920),
        "max_s": 300,
        "title_limit": 25,
        "hook_s": 3,
        "note": "口语化、直接给结果，避免书面语",
    },
}

DEFAULT_TAGS = ["#干货分享", "#知识科普", "#涨知识"]


@dataclass
class Variant:
    platform: str
    label: str
    aspect: str
    size: tuple[int, int]
    title: str
    cover_text: str
    hashtags: list[str]
    suggested_duration_s: int
    trim_note: str
    ffmpeg: str

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "label": self.label,
            "aspect": self.aspect,
            "width": self.size[0],
            "height": self.size[1],
            "title": self.title,
            "cover_text": self.cover_text,
            "hashtags": self.hashtags,
            "suggested_duration_s": self.suggested_duration_s,
            "trim_note": self.trim_note,
            "ffmpeg": self.ffmpeg,
        }


def derive_tags(brief: Brief, limit: int = 5) -> list[str]:
    tags = list(brief.tags) if getattr(brief, "tags", None) else []
    topic = brief.topic.strip()
    if topic:
        key = re.split(r"[，,。？?！!：:]", topic)[0][:8]
        tags.insert(0, f"#{key}")
    for t in DEFAULT_TAGS:
        if len(tags) >= limit:
            break
        if t not in tags:
            tags.append(t)
    return tags[:limit]


def _cover_text(brief: Brief, limit: int = 12) -> str:
    first = re.split(r"[，,。？?！!：:]", brief.topic.strip())[0].strip()
    if first and len(first) <= limit:
        return first
    base = brief.title_hint or brief.topic
    return base[:limit]


def _title(brief: Brief, limit: int) -> str:
    base = brief.title_hint or brief.topic
    if len(base) <= limit:
        return base
    return base[: limit - 1] + "…"


def _trim_note(shots: list[Shot], max_s: int, planned: float) -> str:
    if planned <= max_s:
        return f"时长 {planned:.1f}s，未超过平台上限 {max_s}s，可直接发布。"
    b_roll = sum(s.duration for s in shots if s.b_roll)
    return (
        f"超出平台上限 {planned:.1f}s > {max_s}s：先删 B-roll 素材位（可省 {b_roll:.1f}s），"
        "仍超时则压缩“行动清单”逐条演示，保留钩子与判断标准。"
    )


def ffmpeg_command(size: tuple[int, int], concat_file: str, out: str) -> str:
    w, h = size
    return (
        f"ffmpeg -y -f concat -safe 0 -i {concat_file} "
        f"-f lavfi -i anullsrc=r=44100:cl=stereo -shortest "
        f'-vf "scale={w}:{h}:force_original_aspect_ratio=decrease,'
        f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0b0b12" '
        f"-c:v libx264 -crf 23 -preset medium -pix_fmt yuv420p -r 30 {out}"
    )


def build_variants(brief: Brief, shots: list[Shot]) -> list[Variant]:
    planned = shots[-1].end if shots else 0
    out: list[Variant] = []
    for key in brief.platforms:
        if key not in PLATFORMS:
            raise ValueError(f"未知平台: {key}，可选 {list(PLATFORMS)}")
        spec = PLATFORMS[key]
        out.append(
            Variant(
                platform=key,
                label=spec["label"],
                aspect=spec["aspect"],
                size=spec["size"],
                title=_title(brief, spec["title_limit"]),
                cover_text=_cover_text(brief, 12),
                hashtags=derive_tags(brief),
                suggested_duration_s=min(int(round(planned)), spec["max_s"]),
                trim_note=_trim_note(shots, spec["max_s"], planned),
                ffmpeg=ffmpeg_command(spec["size"], "shots.txt", f"{key}_{int(planned)}s.mp4"),
            )
        )
    return out
