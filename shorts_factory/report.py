"""分镜包的可读报告（Markdown）。"""

from __future__ import annotations

from .compliance import Check
from .planner import Plan
from .platforms import Variant
from .subtitles import build_timeline_md


def render_markdown(plan: Plan, variants: list[Variant], checks: list[Check]) -> str:
    brief = plan.brief
    p = plan.pacing
    blocks = sum(1 for c in checks if c.level == "block")
    warns = sum(1 for c in checks if c.level == "warn")

    lines: list[str] = []
    lines.append(f"# 分镜包：{brief.topic}")
    lines.append("")
    lines.append(
        f"> 目标时长 {brief.duration_s}s ｜ 平台 {'、'.join(v.label for v in variants)} ｜ "
        f"口播 {p['vo_chars']} 字 / 约 {p['estimated_speech_s']}s ｜ B-roll {p['b_roll_s']}s"
    )
    lines.append("")
    verdict = "可进入拍摄" if blocks == 0 else "存在阻断项，先改文案"
    lines.append(f"**投放结论：{verdict}**（阻断 {blocks} / 提醒 {warns}）")
    lines.append(f"节奏判断：{p['note']}")
    lines.append("")

    lines.append("## 1. 3 秒钩子候选")
    lines.append("")
    for i, hook in enumerate(plan.hooks, start=1):
        lines.append(f"{i}. {hook}")
    lines.append("")
    lines.append("> 建议 A/B 测试第 1 与第 3 条：前者是“反搜症状”的指令型钩子，后者用具体场景换共情。")
    lines.append("")

    lines.append("## 2. 分镜表")
    lines.append("")
    lines.append(build_timeline_md(plan.shots))
    lines.append("")

    lines.append("## 3. 多平台版本")
    lines.append("")
    lines.append("| 平台 | 比例 | 尺寸 | 标题 | 封面文字 | 话题 | 建议时长 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for v in variants:
        lines.append(
            f"| {v.label} | {v.aspect} | {v.size[0]}×{v.size[1]} | {v.title} | {v.cover_text} | "
            f"{' '.join(v.hashtags)} | {v.suggested_duration_s}s |"
        )
    lines.append("")
    for v in variants:
        lines.append(f"**{v.label}**：{v.trim_note}")
        lines.append("")
        lines.append("```bash")
        lines.append(v.ffmpeg)
        lines.append("```")
        lines.append("")

    lines.append("## 4. 合规检查")
    lines.append("")
    lines.append("| 级别 | 规则 | 说明 | 位置 |")
    lines.append("| --- | --- | --- | --- |")
    for c in checks:
        lines.append(f"| {c.level} | {c.rule} | {c.message} | {c.where} |")
    lines.append("")

    lines.append("## 5. 拍摄/发布清单")
    lines.append("")
    lines.append("- [ ] 替换所有 B-ROLL 素材位（当前为占位卡）")
    lines.append("- [ ] 按分镜表核对每镜时长，口播不赶句")
    lines.append("- [ ] 字幕逐条校对，专有名词与数字必须人工确认")
    lines.append("- [ ] 封面用 3:4 与 9:16 各导出一版，检查首屏可读性")
    lines.append("- [ ] 发布前再跑一次 `--check-only`，确认无新增绝对化用语")
    lines.append("")
    return "\n".join(lines)
