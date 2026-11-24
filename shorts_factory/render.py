"""把分镜渲染成可交付的 MP4（字幕烧录 + 卡片视觉）。

这里刻意不接 TTS / 图生视频：先保证「时间轴、字幕、镜头结构」是对的，
再把画面替换成真实拍摄或生成素材。渲染出的卡片视频用于内部过片，不是终版。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .planner import Plan, Shot
from .subtitles import wrap_cjk

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_FALLBACK = "/usr/share/fonts/truetype/arphic/uming.ttc"

BEAT_COLORS = {
    "hook": (255, 92, 98),
    "problem": (255, 196, 110),
    "criteria": (122, 220, 180),
    "action": (110, 180, 255),
    "caveat": (198, 202, 214),
    "cta": (255, 255, 255),
}

BG_TOP = (11, 11, 18)
BG_BOTTOM = (24, 24, 42)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size=size, index=0)
    except OSError:
        return ImageFont.truetype(FONT_FALLBACK, size=size)


def _gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img


def _rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _wrap_px(draw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _center_text(draw, text, font_size, box, fill=(245, 246, 250), line_gap=1.3, bold=True, max_lines=5):
    """按像素宽度自动折行并逐级缩字号，保证不溢出画面。"""
    w = box[2] - box[0]
    h = box[3] - box[1]
    size = font_size
    while True:
        font = _font(size, bold=bold)
        lines = _wrap_px(draw, text, font, w)
        line_h = draw.textbbox((0, 0), "字", font=font)[3]
        total = int(line_h * line_gap * len(lines))
        if (len(lines) <= max_lines and total <= h) or size <= 22:
            break
        size -= 4

    y = box[1] + (h - total) // 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        draw.text((box[0] + (w - tw) / 2, y), line, font=font, fill=fill)
        y += int(line_h * line_gap)


def render_shot(shot: Shot, total_shots: int, total_s: float, size=(720, 1280)) -> Image.Image:
    w, h = size
    img = _gradient(size)
    draw = ImageDraw.Draw(img)
    color = BEAT_COLORS.get(shot.beat, (255, 255, 255))

    # 左侧色带
    draw.rectangle([0, 0, 8, h], fill=color)

    small = _font(22)
    draw.text((40, 46), f"SHOT {shot.index:02d} / {total_shots:02d}   {shot.duration:.1f}s", font=small, fill=(150, 154, 168))

    # 段落标签
    label_font = _font(28, bold=True)
    tw = draw.textbbox((0, 0), shot.beat_label, font=label_font)
    box_w = tw[2] - tw[0] + 44
    _rounded(draw, (40, 92, 40 + box_w, 146), 14, tuple(int(c * 0.28) for c in color))
    draw.text((62, 106), shot.beat_label, font=label_font, fill=color)

    if shot.b_roll:
        big = _font(64, bold=True)
        bbox = draw.textbbox((0, 0), "B-ROLL", font=big)
        draw.text(((w - (bbox[2] - bbox[0])) // 2, h // 2 - 140), "B-ROLL", font=big, fill=color)
        _center_text(draw, shot.visual, 30, (70, h // 2 - 40, w - 70, h // 2 + 160), fill=(190, 194, 206), bold=False)
    else:
        text = shot.vo or shot.subtitle
        _center_text(draw, text, 56, (64, 320, w - 64, h - 280))

    # 进度条
    bar_y = h - 120
    draw.rectangle([40, bar_y, w - 40, bar_y + 6], fill=(40, 42, 58))
    progress = shot.end / max(total_s, 0.01)
    draw.rectangle([40, bar_y, 40 + int((w - 80) * progress), bar_y + 6], fill=color)

    foot = _font(20)
    draw.text((40, h - 92), "shorts-factory / storyboard render", font=foot, fill=(110, 114, 130))
    right = f"{shot.start:.1f}-{shot.end:.1f}s"
    bbox = draw.textbbox((0, 0), right, font=foot)
    draw.text((w - 40 - (bbox[2] - bbox[0]), h - 92), right, font=foot, fill=(130, 134, 150))
    return img


def render_cover(plan: Plan, out_path: Path, size=(1080, 1440)) -> Path:
    w, h = size
    img = _gradient(size)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 10], fill=BEAT_COLORS["hook"])
    _center_text(draw, plan.brief.topic, 92, (90, 300, w - 90, h - 500), fill=(250, 250, 252), line_gap=1.3, max_lines=4)
    tag = _font(34)
    draw.text((92, h - 420), f"#{(plan.brief.tags or ['干货分享'])[0].lstrip('#')}", font=tag, fill=(255, 196, 110))
    sub = _font(40)
    draw.text((92, h - 330), f"{plan.brief.duration_s} 秒讲清 · 收藏备用", font=sub, fill=(180, 184, 198))
    draw.text((92, h - 150), "shorts-factory", font=_font(26), fill=(120, 124, 140))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path


def _write_concat(frame_paths: list[Path], durations: list[float], work: Path) -> Path:
    lines = []
    for p, d in zip(frame_paths, durations):
        lines.append(f"file '{p.as_posix()}'")
        lines.append(f"duration {d:.2f}")
    lines.append(f"file '{frame_paths[-1].as_posix()}'")
    concat = work / "shots.txt"
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return concat


def render_video(plan: Plan, out_path: Path, size=(720, 1280), fps: int = 30) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先安装（apt install ffmpeg）")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shorts_") as tmp:
        work = Path(tmp)
        frames = []
        for shot in plan.shots:
            frame = render_shot(shot, len(plan.shots), plan.shots[-1].end, size=size)
            p = work / f"shot_{shot.index:03d}.png"
            frame.save(p)
            frames.append(p)
        concat = _write_concat(frames, [s.duration for s in plan.shots], work)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
            "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,"
            f"pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2:color=0x0b0b12,fps={fps}",
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-1500:])
    return out_path
