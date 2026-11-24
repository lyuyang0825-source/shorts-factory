import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shorts_factory import Brief, build_plan, build_srt, build_variants, check  # noqa: E402
from shorts_factory.planner import split_lines  # noqa: E402
from shorts_factory.render import render_video  # noqa: E402

BRIEF_PATH = Path(__file__).resolve().parents[1] / "samples" / "brief_zh_01.json"
BRIEF2_PATH = Path(__file__).resolve().parents[1] / "samples" / "brief_zh_02.json"


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.brief = Brief.from_json(BRIEF_PATH)
        self.plan = build_plan(self.brief)

    def test_total_duration_matches_target(self):
        self.assertAlmostEqual(self.plan.shots[-1].end, self.brief.duration_s, delta=0.2)

    def test_timeline_is_contiguous(self):
        self.assertEqual(self.plan.shots[0].start, 0.0)
        for prev, nxt in zip(self.plan.shots, self.plan.shots[1:]):
            self.assertAlmostEqual(prev.end, nxt.start, delta=0.02)
            self.assertEqual(nxt.index, prev.index + 1)

    def test_hooks(self):
        self.assertEqual(len(self.plan.hooks), 3)
        self.assertTrue(all(len(h) <= 30 for h in self.plan.hooks))

    def test_hooks_are_topic_aware(self):
        self.assertTrue(any("熬夜" in h for h in self.plan.hooks), self.plan.hooks)
        self.assertFalse(any("凌晨三点" in h for h in self.plan.hooks), "不应复用其他题材的固定钩子")
        # “第一步”是流程描述，不应被当成绝对化用语“第一”
        self.assertFalse(any(c.rule == "C001" and "第一" in c.message for c in check(self.plan, build_variants(self.brief, self.plan.shots))))

    def test_overloaded_brief_warns_not_speeds_up(self):
        plan = build_plan(Brief.from_json(BRIEF2_PATH))
        self.assertGreater(plan.pacing["speech_density"], 5.8)
        self.assertIn("删减", plan.pacing["note"])
        self.assertAlmostEqual(plan.shots[-1].end, 30.0, delta=0.2)

    def test_every_shot_has_visual_and_subtitle(self):
        for shot in self.plan.shots:
            self.assertTrue(shot.visual)
            self.assertTrue(shot.subtitle)

    def test_speech_density_in_range(self):
        self.assertLess(self.plan.pacing["speech_density"], 5.8)

    def test_short_fragments_are_packed(self):
        lines = split_lines("现在能做的三件事：坐下测一次心率并记下时间、停止咖啡因和酒精。", 24)
        self.assertTrue(all(len(x) >= 8 for x in lines[:-1]), lines)


class TestSubtitles(unittest.TestCase):
    def test_srt_blocks(self):
        plan = build_plan(Brief.from_json(BRIEF_PATH))
        srt = build_srt(plan.shots)
        vo_shots = [s for s in plan.shots if s.vo]
        self.assertEqual(srt.count(" --> "), len(vo_shots))
        self.assertIn("00:00:00,", srt.split("\n")[1])


class TestPlatforms(unittest.TestCase):
    def test_variants(self):
        brief = Brief.from_json(BRIEF_PATH)
        plan = build_plan(brief)
        variants = build_variants(brief, plan.shots)
        self.assertEqual([v.platform for v in variants], brief.platforms)
        for v in variants:
            self.assertIn(v.aspect, {"9:16", "3:4", "16:9"})
            self.assertLessEqual(len(v.title), 40)
            self.assertGreaterEqual(len(v.hashtags), 3)


class TestCompliance(unittest.TestCase):
    def test_absolute_claim_blocked(self):
        brief = Brief(topic="某产品测评", duration_s=30, key_points=["这个方案能根治所有问题"], platforms=["douyin"])
        plan = build_plan(brief)
        variants = build_variants(brief, plan.shots)
        checks = check(plan, variants)
        self.assertTrue(any(c.level == "block" for c in checks))

    def test_clean_brief_passes(self):
        brief = Brief.from_json(BRIEF_PATH)
        plan = build_plan(brief)
        variants = build_variants(brief, plan.shots)
        self.assertFalse(any(c.level == "block" for c in check(plan, variants)))


@unittest.skipUnless(shutil.which("ffmpeg"), "需要 ffmpeg")
class TestRender(unittest.TestCase):
    def test_render_small_video(self):
        plan = build_plan(Brief.from_json(BRIEF_PATH))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo.mp4"
            render_video(plan, out, size=(270, 480))
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
