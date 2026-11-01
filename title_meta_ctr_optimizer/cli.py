"""Command line entry point: `title-meta-ctr-optimizer GSC_FILE CRAWL_FILE`."""
from pathlib import Path

import click

from . import __version__, core
from .benchmark import STATS
from .report import Report, write_excel


@click.command()
@click.argument("gsc_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("crawl_file", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option("--curve", type=click.Path(exists=True, dir_okay=False), default=None,
              help="Your own CTR by position (CSV with position and ctr columns).")
@click.option("--min-impressions", default=core.MIN_IMPRESSIONS, show_default=True,
              help="Skip pages with fewer impressions.")
@click.option("--max-position", default=core.MAX_POSITION, show_default=True,
              help="Skip pages ranking lower than this average position.")
@click.option("--under", default=core.UNDER, show_default=True,
              help="Underperforming = CTR below this share of the expected CTR.")
@click.option("-o", "--output", default="ctr_report", show_default=True,
              help="Report name; writes <name>.html and <name>.xlsx")
@click.version_option(__version__)
def main(gsc_file, crawl_file, curve, min_impressions, max_position, under, output):
    """Find pages whose CTR is below the curve for their position and fix their title and meta.

    GSC_FILE is a Search Console export (pages, or query + page). CRAWL_FILE is a crawl export with
    url, title and meta description (optional: without it you only get the CTR gap).

    Built by Meer Hamza - linkedin.com/in/meerhamza-seo
    """
    if not 0 < under <= 1:
        raise click.BadParameter("--under must be between 0 and 1", param_hint="--under")
    try:
        gsc = core.load_gsc(gsc_file)
        crawl = core.load_crawl(crawl_file) if crawl_file else None
        curve_map = core.load_curve(curve)
    except (ValueError, FileNotFoundError) as e:
        raise click.ClickException(str(e))
    df = core.analyse(gsc, crawl, curve_map, min_impressions=min_impressions, max_position=max_position,
                      under=under)
    s = core.summary(df)

    report = Report(title="Title and meta CTR report", subtitle=f"{Path(gsc_file).name} · {s['pages']} pages checked",
                    tool="title-meta-ctr-optimizer")
    report.add_cards([("Pages checked", s["pages"]),
                      ("Below the CTR curve", s["underperforming"], "bad" if s["underperforming"] else "good"),
                      ("Rewrite title/meta", s["rewrite"], "bad" if s["rewrite"] else "good"),
                      ("Snippet fine, check SERP", s["check_serp"], "warn" if s["check_serp"] else "good"),
                      ("Clicks to win back", f"{s['extra_clicks']:,}", "warn" if s["extra_clicks"] else "good")])
    report.add_benchmark(STATS[0], how_used="SERP features (video, images, People Also Ask, carousels) take more "
                         "of the results page every year. Pages whose CTR is low but whose title and meta pass "
                         "every check are marked 'check SERP features' instead of 'rewrite snippet', so you "
                         "do not rewrite a good snippet that is being pushed down the page.")
    if not df.empty:
        fix = df[df["verdict"].isin(["rewrite snippet", "underperforming (page not in crawl)"])]
        report.add_table("Fix first: below the curve with snippet problems",
                         fix[["page", "query", "impressions", "ctr", "expected_ctr", "position", "extra_clicks",
                              "title_issues", "meta_issues", "suggested_title", "fixes"]],
                         sheet="Fix first",
                         note="Sorted by clicks you would gain by reaching the expected CTR for the position.")
    report.add_table("All pages", df, sheet="All pages",
                     note=f"Expected CTR comes from {'your curve file' if curve else 'a built-in approximate curve'}; "
                          f"underperforming = CTR below {under:.0%} of expected.")
    html_path = report.save_html(Path(output).with_suffix(".html"))
    xlsx_path = write_excel(report.sheets, Path(output).with_suffix(".xlsx"))
    click.secho(f"Report: {html_path}\nData:   {xlsx_path}", fg="green", bold=True)
    click.echo(f"{s['pages']} pages, {s['underperforming']} below the curve, {s['rewrite']} to rewrite, "
               f"{s['check_serp']} to check for SERP features, {s['extra_clicks']} clicks to win back")


if __name__ == "__main__":
    main()
