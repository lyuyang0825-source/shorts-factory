"""发布前合规检查：绝对化用语、医疗/金融承诺、时长与封面。

只做“拦截提示”，不替代平台审核；词表可按行业扩充。
"""

from __future__ import annotations

from dataclasses import dataclass

from .planner import Plan
from .platforms import Variant

ABSOLUTE_TERMS = ("最好", "最强", "第一品牌", "唯一", "100%", "永久", "根治", "彻底", "绝对", "全网最", "顶级", "排名第一", "销量第一")
MEDICAL_CLAIMS = ("治愈", "包治", "药到病除", "替代就医", "不用去医院", "保证有效", "立刻见效")
FINANCIAL_CLAIMS = ("稳赚", "保本", "无风险", "翻倍", "躺赚")
HEALTH_HINTS = ("病", "症", "医", "药", "癌", "血压", "血糖", "失眠", "熬夜", "心慌", "胸痛")


@dataclass
class Check:
    level: str  # block / warn
    rule: str
    message: str
    where: str

    def to_dict(self) -> dict:
        return {"level": self.level, "rule": self.rule, "message": self.message, "where": self.where}


def _scan(text: str, terms: tuple[str, ...], rule: str, where: str) -> list[Check]:
    out = []
    for term in terms:
        if term in text:
            out.append(Check("block", rule, f"命中绝对化/承诺用语“{term}”，大多数平台会限流或判违规。", where))
    return out


def check(plan: Plan, variants: list[Variant]) -> list[Check]:
    checks: list[Check] = []
    brief = plan.brief
    all_text = " ".join(
        [brief.topic, brief.cta, brief.disclaimer, brief.title_hint]
        + brief.key_points
        + [s.subtitle for s in plan.shots if s.vo]
        + plan.hooks
    )
    checks += _scan(all_text, ABSOLUTE_TERMS, "C001", "文案")
    checks += _scan(all_text, MEDICAL_CLAIMS, "C002", "文案")
    checks += _scan(all_text, FINANCIAL_CLAIMS, "C003", "文案")

    if any(h in " ".join([brief.topic] + brief.key_points) for h in HEALTH_HINTS) and not brief.disclaimer:
        checks.append(Check("warn", "C004", "健康类内容缺少免责声明，建议在口播与角标同时标注。", "免责声明"))

    for v in variants:
        if len(v.cover_text) > 12:
            checks.append(Check("warn", "C005", f"{v.label} 封面文字超过 12 字，手机端会被截断。", "封面"))
        if v.trim_note.startswith("超出"):
            checks.append(Check("warn", "C006", f"{v.label}：{v.trim_note}", "时长"))
        if len(v.hashtags) < 3:
            checks.append(Check("warn", "C007", f"{v.label} 话题不足 3 个，冷启动流量会受影响。", "话题"))

    if not checks:
        checks.append(Check("pass", "C000", "未命中已知违规词，时长与封面规格符合平台要求。", "全部"))
    return checks


def render_md(checks: list[Check]) -> str:
    out = ["| 级别 | 规则 | 说明 | 位置 |", "| --- | --- | --- | --- |"]
    for c in checks:
        out.append(f"| {c.level} | {c.rule} | {c.message} | {c.where} |")
    return "\n".join(out)
