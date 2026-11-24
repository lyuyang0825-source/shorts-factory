"""从一句选题生成可执行的分镜包。

产品定位：不是“一键成片”，而是把最耗时的三件事标准化——
1) 3 秒钩子与叙事结构；2) 逐镜分镜表；3) 口播稿 / 字幕 / 多平台改版。
模板引擎保证离线可用；接 LLM 时只替换文案层，时间轴与合规检查仍由本工具兜底。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

# 中文口播语速经验值：4.5 字/秒（偏慢，便于留气口）
SPEECH_RATE = 4.5

BEAT_SPECS = [
    ("hook", 0.08, "真人半身口播，直视镜头，背景干净；0.5 秒内出关键词大字", "近景", "硬切"),
    ("problem", 0.15, "生活场景空镜（深夜工位 / 床头手机 / 电梯），叠关键词字幕", "中景", "叠化"),
    ("criteria", 0.29, "信息图：判断标准逐条弹出，关键数字放大，配心电图/警示音效", "特写", "硬切"),
    ("action", 0.27, "手部演示 + 清单卡片，逐条打勾；每个动作给一个可视化结果", "中景", "硬切"),
    ("caveat", 0.13, "专业场景（白大褂 / 诊室），语速放慢，角标常驻免责声明", "近景", "叠化"),
    ("cta", 0.08, "结尾定格，收藏 / 转发按钮动效，口播重复一次动作指令", "近景", "推镜"),
]

FILLER_VISUALS = [
    "空镜素材位：补一个真实生活场景（建议 3–5 秒）",
    "案例素材位：补一个具体案例或对比画面，避免全程字幕",
    "数据素材位：补一张来源可核验的图表或截图",
]


@dataclass
class Brief:
    topic: str
    audience: str = ""
    platforms: list[str] = field(default_factory=lambda: ["douyin"])
    duration_s: int = 60
    tone: str = ""
    key_points: list[str] = field(default_factory=list)
    cta: str = "收藏这条，转给需要的人"
    disclaimer: str = "以上为科普内容，不能替代专业诊断"
    title_hint: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Brief":
        allowed = {f for f in cls.__dataclass_fields__}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"未知字段: {sorted(unknown)}")
        return cls(**{k: v for k, v in data.items() if k in allowed})

    @classmethod
    def from_json(cls, path: str | Path) -> "Brief":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class Shot:
    index: int
    beat: str
    beat_label: str
    start: float
    end: float
    duration: float
    visual: str
    vo: str | None
    subtitle: str
    shot_size: str
    transition: str
    b_roll: bool = False

    @property
    def text_chars(self) -> int:
        return len(self.subtitle)


@dataclass
class Plan:
    brief: Brief
    hooks: list[str]
    shots: list[Shot]
    pacing: dict
    compliance_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "brief": asdict(self.brief),
            "hooks": self.hooks,
            "shots": [asdict(s) for s in self.shots],
            "pacing": self.pacing,
            "compliance_notes": self.compliance_notes,
        }


BEAT_LABELS = {
    "hook": "3 秒钩子",
    "problem": "痛点共鸣",
    "criteria": "判断标准",
    "action": "行动清单",
    "caveat": "边界与免责",
    "cta": "行动号召",
}


def build_hooks(brief: Brief) -> list[str]:
    topic = brief.topic.strip("。 ？?")
    short = topic.split("，")[0][:14]
    n = max(2, min(3, len(brief.key_points) or 3))
    return [
        f"先别划走。{short}，先记住判断顺序。",
        f"{short}：{n} 个最容易做错的细节。",
        f"{short}，很多人第一步就做错了。",
    ]


SENT_END_RE = re.compile(r"(?<=[。！？])")
CLAUSE_RE = re.compile(r"(?<=[；：])")
COMMA_RE = re.compile(r"(?<=[、，])")


def _pack(parts: list[str], max_chars: int) -> list[str]:
    """把过短的碎片并入相邻片段，保留句内标点，避免一个字一个镜头。"""
    out: list[str] = []
    for part in parts:
        part = re.sub(r"^[；;：:，,、（(]+", "", part.strip())
        if not part:
            continue
        if out and len(part) < 8 and len(out[-1]) + len(part) <= max_chars:
            out[-1] += part
        else:
            out.append(part)
    return out


def split_lines(text: str, max_chars: int = 26) -> list[str]:
    """先按句末标点切，过长再依次按分号/冒号、顿号/逗号切，最后硬切。"""
    text = re.sub(r"\s+", "", text.strip())
    if not text:
        return []
    out: list[str] = []
    for sentence in SENT_END_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            out.append(sentence)
            continue
        for clause in CLAUSE_RE.split(sentence):
            clause = clause.strip()
            if not clause:
                continue
            if len(clause) <= max_chars:
                out.append(clause)
                continue
            for seg in COMMA_RE.split(clause):
                seg = seg.strip()
                if not seg:
                    continue
                if len(seg) <= max_chars:
                    out.append(seg)
                else:
                    out.extend(seg[i : i + max_chars] for i in range(0, len(seg), max_chars))
    return _pack(out, max_chars)


def _build_script(brief: Brief, hooks: list[str]) -> dict[str, list[str]]:
    points = [p for p in brief.key_points if p.strip()]
    criteria_text = points[0] if points else brief.topic
    action_text = "；".join(points[1:]) if len(points) > 1 else "把上面的判断标准保存下来，出现信号时按顺序执行。"
    problem_text = f"这条只讲一件事：{brief.topic}。先给结论，再给可执行的判断顺序。"
    caveat_text = "；".join(
        x for x in [brief.disclaimer, "症状持续、加重或反复发作，直接就医，不要靠短视频自我诊断。"] if x
    )
    return {
        "hook": [hooks[0]],
        "problem": split_lines(problem_text, 22) or [brief.topic],
        "criteria": split_lines(criteria_text, 24) or [brief.topic],
        "action": split_lines(action_text, 24) or ["按上面的顺序执行。"],
        "caveat": split_lines(caveat_text, 22) or ["以上为科普内容。"],
        "cta": split_lines(brief.cta, 18) or ["收藏这条。"],
    }


def _alloc(durations: list[float], total: float) -> list[float]:
    """按权重分配，保留 1 位小数，最后一段吸收误差。"""
    if not durations:
        return []
    weights = [max(d, 0.1) for d in durations]
    s = sum(weights)
    raw = [total * w / s for w in weights]
    rounded = [round(x, 1) for x in raw]
    diff = round(total - sum(rounded), 1)
    rounded[-1] = round(rounded[-1] + diff, 1)
    return rounded


def build_plan(brief: Brief) -> Plan:
    hooks = build_hooks(brief)
    script = _build_script(brief, hooks)
    target = float(brief.duration_s)

    raw: dict[str, list[float]] = {}
    for beat, *_ in BEAT_SPECS:
        raw[beat] = [max(1.6, len(line) / SPEECH_RATE) for line in script[beat]]
    total_est = sum(sum(v) for v in raw.values())

    if total_est > target:
        factor = target / total_est
        extra = 0.0
    else:
        factor = 1.0
        extra = target - total_est

    shots: list[Shot] = []
    cursor = 0.0
    idx = 1
    for beat, ratio, visual, size, transition in BEAT_SPECS:
        durations = [round(d * factor, 1) for d in raw[beat]]
        extra_b = extra * ratio
        fillers: list[float] = []
        if extra_b >= 3.0:
            n = int(extra_b // 3.0)
            each = round(extra_b / n, 1)
            fillers = [each] * n
            rem = round(extra_b - each * n, 1)
            if rem:
                if durations:
                    durations[-1] = round(durations[-1] + rem, 1)
                else:
                    fillers[-1] = round(fillers[-1] + rem, 1)
        elif extra_b > 0:
            if durations:
                durations[-1] = round(durations[-1] + extra_b, 1)
            else:
                fillers = [round(extra_b, 1)]

        lines = script[beat]
        for i, dur in enumerate(durations):
            vo = lines[i]
            shots.append(
                Shot(
                    index=idx,
                    beat=beat,
                    beat_label=BEAT_LABELS[beat],
                    start=round(cursor, 2),
                    end=round(cursor + dur, 2),
                    duration=round(dur, 2),
                    visual=visual,
                    vo=vo,
                    subtitle=vo,
                    shot_size=size,
                    transition=transition,
                    b_roll=False,
                )
            )
            cursor = round(cursor + dur, 2)
            idx += 1

        for _ in fillers:
            dur = round(fillers[0], 1) if False else round(fillers.pop(0), 1)
            shots.append(
                Shot(
                    index=idx,
                    beat=beat,
                    beat_label=BEAT_LABELS[beat],
                    start=round(cursor, 2),
                    end=round(cursor + dur, 2),
                    duration=round(dur, 2),
                    visual=FILLER_VISUALS[(idx - 1) % len(FILLER_VISUALS)],
                    vo=None,
                    subtitle="B-ROLL 素材位",
                    shot_size=size,
                    transition=transition,
                    b_roll=True,
                )
            )
            cursor = round(cursor + dur, 2)
            idx += 1

    # 把浮点误差吸收到最后一镜，保证总时长严格等于目标
    diff = round(target - shots[-1].end, 1)
    if abs(diff) >= 0.1:
        shots[-1].duration = round(shots[-1].duration + diff, 1)
        shots[-1].end = round(shots[-1].end + diff, 1)

    total_chars = sum(len(s.vo) for s in shots if s.vo)
    est_speech = round(total_chars / SPEECH_RATE, 1)
    b_roll_s = round(sum(s.duration for s in shots if s.b_roll), 1)
    pacing = {
        "target_s": brief.duration_s,
        "planned_s": round(shots[-1].end, 2),
        "vo_chars": total_chars,
        "estimated_speech_s": est_speech,
        "b_roll_s": b_roll_s,
        "speech_density": round(total_chars / max(brief.duration_s, 1), 1),
        "note": _pacing_note(est_speech, b_roll_s, brief.duration_s, total_chars),
    }
    return Plan(brief=brief, hooks=hooks, shots=shots, pacing=pacing)


def _pacing_note(speech_s: float, b_roll_s: float, target: int, chars: int) -> str:
    density = chars / max(target, 1)
    if density > 5.8:
        cut = chars - int(target * 4.8)
        return (
            f"口播需 {density:.1f} 字/秒，偏快：建议删减约 {cut} 字，"
            f"或把时长放宽到 {int(chars / 4.5)} 秒。"
        )
    if b_roll_s / max(target, 1) > 0.35:
        return "口播信息量偏低，已留出较多 B-roll 位：建议每个要点补一个具体案例或对比数据。"
    if density < 2.8:
        return "信息密度偏低（<2.8 字/秒），完播率风险高：建议增加一个反常识结论或具体数字。"
    return f"口播密度 {density:.1f} 字/秒，落在 2.8–5.8 的舒适区。"
