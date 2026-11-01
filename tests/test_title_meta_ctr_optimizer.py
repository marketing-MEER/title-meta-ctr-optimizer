import tempfile
import unittest
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from title_meta_ctr_optimizer import cli, core

EX = Path(__file__).parent.parent / "examples"
GSC = EX / "gsc_pages.csv"
CRAWL = EX / "crawl.csv"


class CurveTest(unittest.TestCase):
    def test_expected_ctr_values(self):
        c = core.DEFAULT_CURVE
        self.assertEqual(core.expected_ctr(1, c), 0.28)
        self.assertAlmostEqual(core.expected_ctr(1.5, c), 0.215)
        self.assertEqual(core.expected_ctr(0.2, c), 0.28)
        self.assertEqual(core.expected_ctr(15, c), core.BEYOND_PAGE_ONE)
        self.assertLess(core.expected_ctr(30, c), core.BEYOND_PAGE_ONE)

    def test_custom_curve_percent_and_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "curve.csv"
            p.write_text("position,ctr\n1,30%\n2,20%\n", encoding="utf-8")
            self.assertEqual(core.load_curve(p), {1: 0.3, 2: 0.2})
            p.write_text("position,ctr\n1,0.3\n2,0.2\n", encoding="utf-8")
            self.assertEqual(core.load_curve(p), {1: 0.3, 2: 0.2})
            p.write_text("a,b\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                core.load_curve(p)


class TextRulesTest(unittest.TestCase):
    def test_shorten_title_drops_brand_segment(self):
        t = "Sales Pipeline Stages Explained With Examples for Small Teams | BrightCRM"
        out = core.shorten_title(t)
        self.assertLessEqual(len(out), core.TITLE_MAX)
        self.assertNotIn("BrightCRM", out)

    def test_shorten_title_cuts_at_word(self):
        out = core.shorten_title("word " * 30)
        self.assertLessEqual(len(out), core.TITLE_MAX)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(core.shorten_title("Short title"), "Short title")

    def test_title_issues(self):
        self.assertEqual(core.title_issues("", "x", False), ["missing title"])
        issues = core.title_issues("Pipeline", "how to set up a sales pipeline", True)
        self.assertTrue(any("too short" in i for i in issues))
        self.assertTrue(any("same title" in i for i in issues))
        self.assertTrue(any("not in title" in i for i in issues))
        self.assertEqual(core.title_issues("CRM Pricing: Plans From 12 USD Per User", "crm pricing", False), [])
        self.assertTrue(any("capitals" in i for i in
                            core.title_issues("ALL CAPITAL TITLE FOR THIS PAGE HERE", "", False)))

    def test_meta_issues(self):
        self.assertEqual(core.meta_issues("", "", False), ["missing meta description"])
        ok = "x" * 100
        self.assertEqual(core.meta_issues(ok, "", False), [])
        self.assertTrue(any("too long" in i for i in core.meta_issues("x" * 170, "", False)))


class LoadTest(unittest.TestCase):
    def test_gsc_merges_rows_per_page(self):
        g = core.load_gsc(GSC)
        row = g[g["page"].str.endswith("crm-for-small-business")].iloc[0]
        self.assertEqual(row["impressions"], 11300)
        self.assertEqual(row["clicks"], 365)
        self.assertEqual(len(g), g["page"].nunique())

    def test_gsc_without_clicks_uses_ctr(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "g.csv"
            p.write_text("Top pages,Impressions,CTR,Position\nhttps://a.example/x,1000,5%,3\n", encoding="utf-8")
            g = core.load_gsc(p)
            self.assertEqual(g.iloc[0]["clicks"], 50)

    def test_missing_columns_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.csv"
            p.write_text("foo,bar\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                core.load_gsc(p)
            with self.assertRaises(ValueError):
                core.load_crawl(p)


class AnalyseTest(unittest.TestCase):
    def setUp(self):
        self.df = core.analyse(core.load_gsc(GSC), core.load_crawl(CRAWL))

    def verdict(self, tail):
        return self.df[self.df["page"].str.endswith(tail)].iloc[0]

    def test_sorted_by_extra_clicks(self):
        self.assertEqual(list(self.df["extra_clicks"]), sorted(self.df["extra_clicks"], reverse=True))

    def test_low_impression_pages_skipped(self):
        self.assertFalse(self.df["page"].str.endswith("follow-up-email-templates").any())

    def test_rewrite_and_serp_verdicts(self):
        self.assertEqual(self.verdict("free-crm-template")["verdict"], "rewrite snippet")
        self.assertTrue(self.verdict("sales-forecast-template")["verdict"].startswith("snippet looks fine"))
        self.assertEqual(self.verdict("/pricing")["verdict"], "ok")

    def test_suggested_title_only_for_long_titles(self):
        row = self.verdict("lead-scoring-model")
        self.assertTrue(row["suggested_title"])
        self.assertLessEqual(len(row["suggested_title"]), core.TITLE_MAX)
        self.assertEqual(self.verdict("free-crm-template")["suggested_title"], "")

    def test_duplicates_found(self):
        self.assertIn("same title", self.verdict("/integrations")["title_issues"])
        self.assertIn("same meta", self.verdict("/crm-for-agencies")["meta_issues"])

    def test_without_crawl(self):
        df = core.analyse(core.load_gsc(GSC))
        self.assertFalse(df.empty)
        self.assertTrue(df["verdict"].str.startswith("underperforming").any() or (df["verdict"] == "ok").any())

    def test_empty_inputs(self):
        empty = pd.DataFrame(columns=["page", "query", "impressions", "clicks", "ctr", "position"])
        df = core.analyse(empty)
        self.assertTrue(df.empty)
        self.assertEqual(core.summary(df)["pages"], 0)
        # everything filtered out
        df = core.analyse(core.load_gsc(GSC), min_impressions=10 ** 9)
        self.assertTrue(df.empty)
        self.assertIn("verdict", df.columns)

    def test_one_page(self):
        g = pd.DataFrame([{"page": "https://a.example/x", "query": "q", "impressions": 500, "clicks": 5,
                           "ctr": 0.01, "position": 3.0}])
        df = core.analyse(g)
        self.assertEqual(len(df), 1)
        self.assertEqual(core.summary(df)["underperforming"], 1)


class CliTest(unittest.TestCase):
    def test_cli_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r"
            res = CliRunner().invoke(cli.main, [str(GSC), str(CRAWL), "-o", str(out)])
            self.assertEqual(res.exit_code, 0, res.output)
            self.assertTrue(out.with_suffix(".html").exists())
            self.assertTrue(out.with_suffix(".xlsx").exists())
            self.assertIn("below the curve", res.output)
            self.assertIn("Top SERP Features", out.with_suffix(".html").read_text(encoding="utf-8"))

    def test_cli_without_crawl_and_bad_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r"
            res = CliRunner().invoke(cli.main, [str(GSC), "-o", str(out)])
            self.assertEqual(res.exit_code, 0, res.output)
            res = CliRunner().invoke(cli.main, [str(GSC), "--under", "2"])
            self.assertNotEqual(res.exit_code, 0)

    def test_cli_bad_file_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.csv"
            p.write_text("foo,bar\n1,2\n", encoding="utf-8")
            res = CliRunner().invoke(cli.main, [str(p)])
            self.assertNotEqual(res.exit_code, 0)
            self.assertIn("impressions", res.output)


if __name__ == "__main__":
    unittest.main()
