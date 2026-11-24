"""字幕与口播稿：把分镜时间轴转成 SRT / 纯文本口播稿。"""

from __future__ import annotations

from .planner import Shot


def _ts(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap_cjk(text: str, limit: int = 16) -> list[str]:
    """按字符数折行，优先在标点处断开，最多两行。"""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    # 找 limit 附近最靠后的标点
    best = -1
    for i, ch in enumerate(text[: limit + 1]):
        if ch in "，。；、：！？,;:" and i >= limit // 2:
            best = i
    if best > 0:
        return [text[: best + 1], text[best + 1 :].strip()]
    return [text[:limit], text[limit:]]


def build_srt(shots: list[Shot], max_chars: int = 16) -> str:
    entries: list[str] = []
    n = 0
    for shot in shots:
        if not shot.vo:
            continue
        n += 1
        start = shot.start + 0.05
        end = max(start + 0.6, shot.end - 0.05)
        lines = wrap_cjk(shot.vo, max_chars)
        entries.append(f"{n}\n{_ts(start)} --> {_ts(end)}\n" + "\n".join(lines) + "\n")
    return "\n".join(entries)


def build_voiceover(shots: list[Shot]) -> str:
    lines = []
    for shot in shots:
        if not shot.vo:
            continue
        lines.append(f"[{shot.start:05.1f}-{shot.end:05.1f}] {shot.vo}")
    return "\n".join(lines)


def build_timeline_md(shots: list[Shot]) -> str:
    out = ["| 镜号 | 时间 | 时长 | 段落 | 景别 | 画面 | 口播/字幕 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for s in shots:
        vo = s.subtitle.replace("|", "\\|")
        visual = s.visual.replace("|", "\\|")
        out.append(
            f"| {s.index} | {s.start:.1f}–{s.end:.1f}s | {s.duration:.1f}s | {s.beat_label} | "
            f"{s.shot_size} | {visual} | {vo} |"
        )
    return "\n".join(out)
