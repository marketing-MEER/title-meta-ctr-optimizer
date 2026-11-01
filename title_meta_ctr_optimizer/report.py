"""Shared report writers: formatted Excel and a styled, self-contained HTML report.

Copied unchanged into every repo of the SEO toolbox family. Usage:

    report = Report(title="Keyword gap report", subtitle="example.com vs 3 competitors")
    report.add_cards([("Missing keywords", 412), ("Weak keywords", 96)])
    report.add_benchmark(np_stat_dict)          # optional Neil Patel data panel
    report.add_table("Missing keywords", df, note="Sorted by revenue score")
    report.save_html("keyword_gap.html")
    write_excel(report.sheets, "keyword_gap.xlsx")
"""
import html
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

AUTHOR = "Meer Hamza"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/meerhamza-seo"
TOOLBOX_URL = "https://github.com/marketing-MEER/seo-toolbox"
MAX_HTML_ROWS = 200

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def write_excel(sheets: dict, out_path) -> Path:
    """Write {sheet_name: DataFrame} to a formatted .xlsx (or the first sheet to .csv)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        next(iter(sheets.values())).to_csv(out, index=False)
        return out
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, df in sheets.items():
            sheet = name[:31]
            if df.empty:
                df = pd.DataFrame({"result": ["Nothing found"]})
            df.to_excel(writer, sheet_name=sheet, index=False)
            ws = writer.sheets[sheet]
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.fill, cell.font = HEADER_FILL, HEADER_FONT
                cell.alignment = Alignment(vertical="center")
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 70)
            ws.auto_filter.ref = ws.dimensions
    return out


def find_column(df: pd.DataFrame, candidates) -> str | None:
    """First column whose lower-cased, trimmed name is in candidates."""
    lookup = {str(c).lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand in lookup:
            return lookup[cand]
    return None


def to_number(series: pd.Series) -> pd.Series:
    """'1,234' / '12.5%' / '' -> float."""
    cleaned = (series.astype(str).str.replace(",", "", regex=False)
               .str.replace("%", "", regex=False).str.strip())
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def _esc(value) -> str:
    if value is None or (isinstance(value, float) and value != value):  # None / NaN
        return "–"
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return "✓" if value else ""
    if isinstance(value, float):
        value = f"{value:,.2f}".rstrip("0").rstrip(".")
    elif isinstance(value, int):
        value = f"{value:,}"
    return html.escape(str(value))


def _label(column) -> str:
    """Column name for display: snake_case -> 'Snake case'; domains and other dotted names stay as-is."""
    text = str(column)
    if "." in text:
        return text
    text = text.replace("_", " ")
    return text[:1].upper() + text[1:]


def _cell(value) -> str:
    text = _esc(value)
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return f'<td class="long"><a href="{text}">{text}</a></td>'
    return f'<td class="long">{text}</td>' if len(text) > 45 else f"<td>{text}</td>"


class Report:
    def __init__(self, title: str, subtitle: str = "", tool: str = ""):
        self.title, self.subtitle, self.tool = title, subtitle, tool
        self.blocks: list[str] = []
        self.sheets: dict[str, pd.DataFrame] = {}

    def add_cards(self, cards):
        """cards: [(label, value)] or [(label, value, tone)] with tone in good|warn|bad."""
        items = []
        for card in cards:
            label, value, tone = (*card, "")[:3]
            items.append(f'<div class="card {tone}"><div class="value">{_esc(value)}</div>'
                         f'<div class="label">{_esc(label)}</div></div>')
        self.blocks.append(f'<section class="cards">{"".join(items)}</section>')

    def add_text(self, heading: str, paragraphs):
        body = "".join(f"<p>{_esc(p)}</p>" for p in paragraphs)
        self.blocks.append(f"<section><h2>{_esc(heading)}</h2>{body}</section>")

    def add_benchmark(self, stat: dict, how_used: str = ""):
        """Panel with a Neil Patel / NP Digital stat (dict from np/stats.json)."""
        if not stat:
            return
        facts = "".join(f"<li>{_esc(s)}</li>" for s in stat.get("stats", [])[:5])
        used = f'<p class="used"><b>How this report uses it:</b> {_esc(how_used)}</p>' if how_used else ""
        self.blocks.append(
            f'<section class="benchmark"><div class="eyebrow">Benchmark data</div>'
            f'<h2>{_esc(stat.get("title", ""))}</h2><ul>{facts}</ul>{used}'
            f'<p class="source">Source: {_esc(stat.get("source", ""))}, {_esc(stat.get("date", ""))}. '
            f'{_esc(stat.get("methodology", ""))} '
            f'<a href="{_esc(stat.get("url", ""))}">Neil Patel marketing stats</a></p></section>')

    def add_table(self, heading: str, df: pd.DataFrame, note: str = "", sheet: str | None = None):
        self.sheets[(sheet or heading)[:31]] = df
        if df.empty:
            body = '<p class="empty">Nothing found. 🎉</p>'
        else:
            shown = df.head(MAX_HTML_ROWS)
            head = "".join(f"<th>{_esc(_label(c))}</th>" for c in shown.columns)
            rows = "".join("<tr>" + "".join(_cell(v) for v in row) + "</tr>"
                           for row in shown.itertuples(index=False))
            more = (f'<p class="more">Showing {MAX_HTML_ROWS} of {len(df):,} rows. '
                    f'The Excel file has all of them.</p>') if len(df) > MAX_HTML_ROWS else ""
            body = f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>{more}'
        note_html = f'<p class="note">{_esc(note)}</p>' if note else ""
        self.blocks.append(f"<section><h2>{_esc(heading)} <span class=\"count\">{len(df):,}</span></h2>{note_html}{body}</section>")

    def to_html(self) -> str:
        return HTML_TEMPLATE.format(
            title=_esc(self.title), subtitle=_esc(self.subtitle), tool=_esc(self.tool),
            date=date.today().isoformat(), body="\n".join(self.blocks),
            author=AUTHOR, linkedin=AUTHOR_LINKEDIN, toolbox=TOOLBOX_URL)

    def save_html(self, out_path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_html(), encoding="utf-8")
        return out


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#f6f7fb; --panel:#fff; --text:#1b2333; --muted:#5d6779; --line:#e3e7ef; --accent:#2f6fed;
        --good:#1a7f4b; --warn:#b26a00; --bad:#c23b3b; --bench:#fff8e6; --bench-line:#f1c75b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#11151d; --panel:#1a202b; --text:#e6eaf2; --muted:#9aa4b5;
        --line:#2b3342; --accent:#6d9cff; --good:#4cc38a; --warn:#f0a73a; --bad:#ff7a7a; --bench:#2a2618; --bench-line:#8a6d1f; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 -apple-system,"Segoe UI",Roboto,Arial,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 16px 48px; }}
header {{ margin-bottom:24px; }}
header .tool {{ color:var(--accent); font-weight:600; font-size:13px; text-transform:uppercase; letter-spacing:.06em; }}
h1 {{ font-size:28px; margin:4px 0; }} h2 {{ font-size:19px; margin:0 0 12px; }}
header p {{ color:var(--muted); margin:0; }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px; margin-bottom:18px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; background:none; border:0; padding:0; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; border-top:4px solid var(--accent); }}
.card.good {{ border-top-color:var(--good); }} .card.warn {{ border-top-color:var(--warn); }} .card.bad {{ border-top-color:var(--bad); }}
.card .value {{ font-size:26px; font-weight:700; }} .card .label {{ color:var(--muted); font-size:13px; }}
.benchmark {{ background:var(--bench); border-color:var(--bench-line); }}
.eyebrow {{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--warn); }}
.benchmark ul {{ margin:0 0 10px; padding-left:20px; }} .source {{ font-size:12.5px; color:var(--muted); margin:0; }}
.count {{ font-size:13px; color:var(--muted); font-weight:500; margin-left:6px; }}
.note, .more {{ color:var(--muted); font-size:13px; }} .empty {{ color:var(--good); }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
th {{ text-align:left; background:var(--bg); position:sticky; top:0; }}
th, td {{ padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; white-space:nowrap; }}
th {{ font-size:12.5px; }}
td.long {{ white-space:normal; min-width:220px; max-width:420px; overflow-wrap:anywhere; }}
tbody tr:hover {{ background:var(--bg); }}
a {{ color:var(--accent); }}
footer {{ color:var(--muted); font-size:13px; text-align:center; margin-top:28px; }}
@media print {{ body {{ background:#fff; }} section {{ break-inside:avoid; }} .scroll {{ overflow:visible; }} }}
</style></head>
<body><main>
<header><div class="tool">{tool}</div><h1>{title}</h1><p>{subtitle} · Generated {date}</p></header>
{body}
<footer>Made with <a href="{toolbox}">SEO Toolbox</a> by <a href="{linkedin}">{author}</a> · free and open source</footer>
</main></body></html>
"""
