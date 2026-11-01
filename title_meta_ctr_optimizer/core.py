"""Join a Search Console export with a crawl export and flag titles/metas that cost clicks.

Inputs
- GSC export (CSV/XLSX): one row per page (or per query+page): page, clicks, impressions, ctr, position,
  optionally query.
- Crawl export (CSV/XLSX): url, title, meta description (Screaming Frog / Sitebulb column names work).

Rules come from the title/meta length limits that are standard best practice, plus an expected-CTR
curve by position. The curve is an approximation: pass your own with --curve for better numbers.
"""
import re
from pathlib import Path

import pandas as pd

from .report import find_column, to_number

# Display limits (characters) before Google usually truncates. General best practice, not from NP.
TITLE_MAX, TITLE_MIN = 60, 30
META_MAX, META_MIN = 160, 70

# Approximate share of clicks by organic position (general rule of thumb; override with --curve).
DEFAULT_CURVE = {1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.065, 6: 0.05, 7: 0.04, 8: 0.032, 9: 0.028, 10: 0.024}
BEYOND_PAGE_ONE = 0.012

# NP stat slug top-serp-features: video, images, PAA and carousels now appear on most results pages, so
# a page can sit below its curve for reasons the snippet cannot fix. When title and meta are clean we
# send the user to check SERP features instead of rewriting.
UNDER = 0.7          # actual CTR below 70% of the curve counts as underperforming
MIN_IMPRESSIONS = 100
MAX_POSITION = 20

GSC_PAGE = ["page", "top pages", "landing page", "url", "address", "pages"]
GSC_QUERY = ["query", "top queries", "keyword", "queries"]
GSC_CLICKS = ["clicks"]
GSC_IMPR = ["impressions"]
GSC_CTR = ["ctr", "url ctr"]
GSC_POS = ["position", "average position", "avg position", "avg. position"]
CRAWL_URL = ["address", "url", "page", "landing page"]
CRAWL_TITLE = ["title 1", "title", "page title", "title tag"]
CRAWL_META = ["meta description 1", "meta description", "description", "meta"]

SEPARATORS = [" | ", " - ", " – ", " — ", " · ", " :: "]
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "with", "how", "what", "best"}

RESULT_COLUMNS = ["page", "query", "impressions", "clicks", "ctr", "position", "expected_ctr", "extra_clicks",
                  "verdict", "title", "title_len", "meta_len", "title_issues", "meta_issues",
                  "suggested_title", "fixes"]


def read_table(path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p, encoding="utf-8-sig", sep=None, engine="python")


def load_curve(path=None) -> dict:
    """Position -> expected CTR (0-1). A custom file needs columns position and ctr."""
    if not path:
        return dict(DEFAULT_CURVE)
    df = read_table(path)
    pc, cc = find_column(df, ["position", "pos"]), find_column(df, ["ctr", "expected ctr"])
    if not pc or not cc:
        raise ValueError("curve file needs 'position' and 'ctr' columns")
    ctr = to_number(df[cc])
    if ctr.max() > 1:
        ctr = ctr / 100
    return {int(p): float(c) for p, c in zip(to_number(df[pc]), ctr) if p >= 1}


def expected_ctr(position: float, curve: dict) -> float:
    """Expected CTR at an average position (linear between whole positions)."""
    if position < 1:
        position = 1.0
    last = max(curve)
    if position > last:
        return BEYOND_PAGE_ONE if position <= MAX_POSITION else BEYOND_PAGE_ONE / 2
    lo = int(position)
    hi = min(lo + 1, last)
    frac = position - lo
    return curve[lo] + (curve.get(hi, curve[lo]) - curve[lo]) * frac


def normalise_url(url) -> str:
    u = str(url).strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.split("#")[0].rstrip("/")


def load_gsc(path) -> pd.DataFrame:
    """One row per page: impressions, clicks, ctr, position and the top query by impressions."""
    df = read_table(path)
    page, imp = find_column(df, GSC_PAGE), find_column(df, GSC_IMPR)
    if not page or not imp:
        raise ValueError("GSC file needs a page column and an impressions column "
                         f"(found: {', '.join(map(str, df.columns))})")
    clicks, ctr, pos, query = (find_column(df, c) for c in (GSC_CLICKS, GSC_CTR, GSC_POS, GSC_QUERY))
    out = pd.DataFrame({"page": df[page].astype(str).str.strip(),
                        "impressions": to_number(df[imp]),
                        "clicks": to_number(df[clicks]) if clicks else 0.0,
                        "position": to_number(df[pos]) if pos else 0.0,
                        "query": df[query].astype(str).str.strip() if query else ""})
    if not clicks and ctr:
        c = to_number(df[ctr])
        c = c / 100 if c.max() > 1 else c
        out["clicks"] = (c * out["impressions"]).round()
    if out.empty:
        return pd.DataFrame(columns=["page", "query", "impressions", "clicks", "ctr", "position"])
    rows = []
    for page_url, g in out.groupby("page", sort=False):
        total = g["impressions"].sum()
        top = g.sort_values("impressions", ascending=False).iloc[0]
        position = (g["position"] * g["impressions"]).sum() / total if total else float(top["position"])
        clicks_sum = g["clicks"].sum()
        rows.append({"page": page_url, "query": top["query"] if top["query"] not in ("nan", "") else "",
                     "impressions": int(total), "clicks": int(clicks_sum),
                     "ctr": clicks_sum / total if total else 0.0, "position": round(float(position), 1)})
    return pd.DataFrame(rows, columns=["page", "query", "impressions", "clicks", "ctr", "position"])


def load_crawl(path) -> pd.DataFrame:
    df = read_table(path)
    url, title, meta = find_column(df, CRAWL_URL), find_column(df, CRAWL_TITLE), find_column(df, CRAWL_META)
    if not url or not title:
        raise ValueError("crawl file needs a url/address column and a title column "
                         f"(found: {', '.join(map(str, df.columns))})")
    out = pd.DataFrame({"url": df[url].astype(str).str.strip(),
                        "title": df[title].fillna("").astype(str).str.strip(),
                        "meta": df[meta].fillna("").astype(str).str.strip() if meta else ""})
    out["key"] = out["url"].map(normalise_url)
    return out.drop_duplicates("key")


def keywords(query: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", str(query).lower()) if w not in STOP and len(w) > 1]


def keyword_hit(query: str, text: str) -> float:
    """Share of the query's words that appear in text (1.0 when the query has no usable words)."""
    words = keywords(query)
    if not words:
        return 1.0
    low = str(text).lower()
    return sum(1 for w in words if w in low) / len(words)


def shorten_title(title: str, limit: int = TITLE_MAX) -> str:
    """Drop trailing brand/separator segments, then cut at a word boundary, until the title fits."""
    t = title.strip()
    if len(t) <= limit:
        return t
    for sep in SEPARATORS:
        while sep in t and len(t) > limit:
            t = t.rsplit(sep, 1)[0].strip()
    if len(t) <= limit:
        return t
    cut = t[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,:;-|")
    return cut + "…"


def title_issues(title: str, query: str, duplicate: bool) -> list:
    if not title:
        return ["missing title"]
    issues = []
    n = len(title)
    if n > TITLE_MAX:
        issues.append(f"too long ({n} chars, ~{TITLE_MAX} shown)")
    elif n < TITLE_MIN:
        issues.append(f"too short ({n} chars)")
    if duplicate:
        issues.append("same title on other pages")
    if query and keyword_hit(query, title) < 0.5:
        issues.append(f"top query '{query}' not in title")
    elif query and n > TITLE_MAX and keyword_hit(query, title[:TITLE_MAX]) < 0.5:
        issues.append("top query only after the cut-off")
    letters = [c for c in title if c.isalpha()]
    if len(letters) > 8 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        issues.append("mostly capitals")
    return issues


def meta_issues(meta: str, query: str, duplicate: bool) -> list:
    if not meta:
        return ["missing meta description"]
    issues = []
    n = len(meta)
    if n > META_MAX:
        issues.append(f"too long ({n} chars, ~{META_MAX} shown)")
    elif n < META_MIN:
        issues.append(f"too short ({n} chars)")
    if duplicate:
        issues.append("same meta on other pages")
    if query and keyword_hit(query, meta) < 0.5:
        issues.append(f"top query '{query}' not in meta")
    return issues


def fixes_for(title_i: list, meta_i: list, title: str, query: str) -> str:
    fixes = []
    for i in title_i:
        if i.startswith("too long"):
            fixes.append(f"cut the title to {TITLE_MAX} characters or fewer (see suggested title)")
        elif i.startswith("too short"):
            fixes.append("expand the title with the benefit or a qualifier")
        elif i == "missing title":
            fixes.append("write a title that starts with the main query")
        elif "not in title" in i or "after the cut-off" in i:
            fixes.append(f"move '{query}' to the start of the title")
        elif i.startswith("same title"):
            fixes.append("make the title unique to this page")
        elif i == "mostly capitals":
            fixes.append("use sentence or title case")
    for i in meta_i:
        if i == "missing meta description":
            fixes.append("write a meta description of 100-155 characters with a reason to click")
        elif i.startswith("too long"):
            fixes.append(f"trim the meta description to {META_MAX} characters")
        elif i.startswith("too short"):
            fixes.append("expand the meta description with a benefit and a call to action")
        elif "not in meta" in i:
            fixes.append(f"work '{query}' into the meta description")
        elif i.startswith("same meta"):
            fixes.append("make the meta description unique to this page")
    return "; ".join(dict.fromkeys(fixes))


def analyse(gsc: pd.DataFrame, crawl: pd.DataFrame = None, curve: dict = None,
            min_impressions: int = MIN_IMPRESSIONS, max_position: float = MAX_POSITION,
            under: float = UNDER) -> pd.DataFrame:
    """One row per page with the CTR gap, snippet issues and fixes, biggest click gap first."""
    curve = curve or DEFAULT_CURVE
    if gsc.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    lookup = {}
    dup_titles, dup_metas = set(), set()
    if crawl is not None and not crawl.empty:
        lookup = {r.key: r for r in crawl.itertuples()}
        tc = crawl[crawl["title"] != ""]["title"].str.lower().value_counts()
        mc = crawl[crawl["meta"] != ""]["meta"].str.lower().value_counts()
        dup_titles, dup_metas = set(tc[tc > 1].index), set(mc[mc > 1].index)

    rows = []
    for g in gsc.itertuples():
        if g.impressions < min_impressions or g.position <= 0 or g.position > max_position:
            continue
        exp = expected_ctr(g.position, curve)
        extra = max(0.0, exp - g.ctr) * g.impressions
        c = lookup.get(normalise_url(g.page))
        if c is None:
            title = meta = None
            t_i, m_i = [], []
        else:
            title, meta = c.title, c.meta
            t_i = title_issues(title, g.query, title.lower() in dup_titles)
            m_i = meta_issues(meta, g.query, meta.lower() in dup_metas)
        if g.ctr < exp * under:
            if c is None:
                verdict = "underperforming (page not in crawl)"
            elif t_i or m_i:
                verdict = "rewrite snippet"
            else:
                verdict = "snippet looks fine, check SERP features"
        else:
            verdict = "ok" if not (t_i or m_i) else "ok, tidy later"
        rows.append({"page": g.page, "query": g.query, "impressions": g.impressions, "clicks": g.clicks,
                     "ctr": f"{g.ctr:.1%}", "position": g.position, "expected_ctr": f"{exp:.1%}",
                     "extra_clicks": round(extra),
                     "verdict": verdict,
                     "title": title if title is not None else "",
                     "title_len": len(title) if title is not None else 0,
                     "meta_len": len(meta) if meta is not None else 0,
                     "title_issues": "; ".join(t_i), "meta_issues": "; ".join(m_i),
                     "suggested_title": shorten_title(title) if title and len(title) > TITLE_MAX else "",
                     "fixes": fixes_for(t_i, m_i, title or "", g.query)})
    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    return pd.DataFrame(rows, columns=RESULT_COLUMNS).sort_values(
        ["extra_clicks", "impressions"], ascending=False).reset_index(drop=True)


def summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"pages": 0, "underperforming": 0, "rewrite": 0, "check_serp": 0, "extra_clicks": 0}
    under = df["verdict"].str.startswith("underperforming") | (df["verdict"] == "rewrite snippet") \
        | df["verdict"].str.startswith("snippet looks fine")
    return {"pages": len(df), "underperforming": int(under.sum()),
            "rewrite": int((df["verdict"] == "rewrite snippet").sum()),
            "check_serp": int(df["verdict"].str.startswith("snippet looks fine").sum()),
            "extra_clicks": int(df.loc[under, "extra_clicks"].sum())}
