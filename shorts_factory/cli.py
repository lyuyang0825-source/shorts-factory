from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compliance import check, render_md
from .planner import Brief, build_plan
from .platforms import build_variants
from .render import render_cover, render_video
from .report import render_markdown
from .subtitles import build_srt, build_voiceover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="选题 → 分镜 → 字幕 → 多平台交付包")
    parser.add_argument("--brief", "-b", required=True, help="选题 JSON")
    parser.add_argument("--out-dir", default="demo_out")
    parser.add_argument("--render", action="store_true", help="渲染 MP4 与封面（需要 ffmpeg）")
    parser.add_argument("--check-only", action="store_true", help="只跑合规检查")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    args = parser.parse_args(argv[: len(argv)] if argv is not None else sys.argv[1:])

    brief = Brief.from_json(args.brief)
    plan = build_plan(brief)
    variants = build_variants(brief, plan.shots)
    checks = check(plan, variants)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    blocks = [c for c in checks if c.level == "block"]
    if args.check_only:
        print(render_md(checks))
        return 2 if blocks else 0

    (out_dir / "plan.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "storyboard.md").write_text(render_markdown(plan, variants, checks), encoding="utf-8")
    (out_dir / "voiceover.txt").write_text(build_voiceover(plan.shots), encoding="utf-8")
    (out_dir / "subtitles.srt").write_text(build_srt(plan.shots), encoding="utf-8")
    (out_dir / "platforms.json").write_text(
        json.dumps([v.to_dict() for v in variants], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "compliance.md").write_text("# 合规检查\n\n" + render_md(checks) + "\n", encoding="utf-8")

    if args.render:
        video = render_video(plan, out_dir / "demo_9x16.mp4", size=(args.width, args.height))
        cover = render_cover(plan, out_dir / "cover.png")
        print(f"[shorts] 视频: {video}")
        print(f"[shorts] 封面: {cover}")

    print(
        f"[shorts] {brief.topic}: {len(plan.shots)} 镜 / {plan.shots[-1].end:.1f}s / "
        f"口播约 {plan.pacing['estimated_speech_s']}s / 阻断 {len(blocks)}"
    )
    print(f"[shorts] 分镜包: {out_dir}")
    if blocks:
        print(render_md(checks))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
