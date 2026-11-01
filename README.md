<div align="center">

# 🖱️ title-meta-ctr-optimizer

### Flag titles and meta descriptions that hurt CTR, and see which pages lose the most clicks against the CTR curve.

[![tests](https://github.com/marketing-MEER/title-meta-ctr-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/marketing-MEER/title-meta-ctr-optimizer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![No API keys](https://img.shields.io/badge/API%20keys-none%20needed-brightgreen)
[![Part of SEO Toolbox](https://img.shields.io/badge/part%20of-SEO%20Toolbox-orange)](https://github.com/marketing-MEER/seo-toolbox)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Meer%20Hamza-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)

[🚀 Quick start](#quick-start) · [⚙️ How it works](#how-it-works) · [📄 Report](#report) · [❓ FAQ](#faq) · [👤 Author](#author)

</div>

---

## 💡 What it does

Rewriting titles and metas page by page is slow, and most teams do not know which pages are worth it. This tool
joins your Search Console export with a crawl export, works out what CTR each page should get for its average
position, and lists the pages that fall short, with the clicks you would gain, what is wrong with the snippet and a
suggested shorter title.

- ✅ Ranks pages by clicks lost against the CTR curve for their position, so you start with the biggest gap
- ✅ Checks title and meta length, missing and duplicate tags, capitals, and whether the top query is in the snippet
- ✅ Tells you when the snippet looks fine and the cause is probably SERP features, so you do not rewrite a good snippet
- ✅ Free, MIT licensed, no API keys. Works with the exports you already have.

## 📊 Why this matters

> **Top SERP Features** · STAT Search Analytics, November 2024
> - Images presence jumped from 38% (2023) to 64% (2024).
> - Videos presence increased from 53% (2023) to 76% (2024).
>
> Data: [Neil Patel marketing stats](https://neilpatel.com/marketing-stats/top-serp-features/)

**How title-meta-ctr-optimizer uses this:** the stat's insights say ranking is not enough, because images, video,
People Also Ask and carousels compete with your blue link. So a page can sit under its CTR curve even with a good
snippet. The tool separates "rewrite snippet" (the title or meta has a problem) from "snippet looks fine, check SERP
features" (nothing wrong with the text), which follows the insight to track SERP features, not just rankings.

<a id="quick-start"></a>

## 🚀 Quick start

```bash
git clone https://github.com/marketing-MEER/title-meta-ctr-optimizer.git
cd title-meta-ctr-optimizer
pip install -e .
title-meta-ctr-optimizer examples/gsc_pages.csv examples/crawl.csv
```

This writes **`ctr_report.html`** (a formatted report you can open, share or print to PDF) and **`ctr_report.xlsx`** (all the data).

> [!TIP]
> If the `title-meta-ctr-optimizer` command isn't found, use `python -m title_meta_ctr_optimizer`.

## 📥 Input

| File | How to get it | Columns found automatically |
|---|---|---|
| GSC export (CSV or XLSX) | Search Console > Performance > add Page and Query (Pages tab, filter by query if you like) > Export | `Page` / `Top pages` / `URL`, `Query`, `Clicks`, `Impressions`, `CTR`, `Position` |
| Crawl export (CSV or XLSX), optional | Screaming Frog > Internal > Export, or any file with these columns | `Address` / `URL`, `Title 1` / `Title`, `Meta Description 1` / `Description` |

Rows for the same page are merged (impressions added up, position weighted by impressions, the query with the
most impressions is treated as the page's main query). URLs are matched without `http(s)://`, `www.`, fragments and
trailing slash. Without a crawl file you get the CTR gap only.

<a id="how-it-works"></a>

## ⚙️ How it works

1. Merges the GSC rows per page and keeps pages with at least 100 impressions that rank at position 20 or better.
2. Looks up the expected CTR for the average position on a built-in curve (28% at position 1 down to 2.4% at 10,
   1.2% on page two). This is an approximation from general rules of thumb, not a Neil Patel figure. Pass your own
   with `--curve` (a file with `position` and `ctr` columns) for numbers that fit your market.
3. Extra clicks = (expected CTR - actual CTR) x impressions, never below zero.
4. A page is underperforming when its CTR is below 70% of the expected CTR (`--under`).
5. Title checks: missing, longer than 60 characters, shorter than 30, the same title on other pages, top query
   missing or only after the cut-off, mostly capitals. Meta checks: missing, longer than 160, shorter than 70,
   duplicated, top query missing. These limits are standard display guidance; Google rewrites snippets by pixel
   width, so treat them as a guide.
6. Verdict: **rewrite snippet** (underperforming and a check failed), **snippet looks fine, check SERP features**
   (underperforming, no check failed), **ok**, or **ok, tidy later**.
7. For titles over 60 characters it suggests a shorter version by dropping the brand segment after the last
   separator, then cutting at a word boundary.

### Options

| Option | Default | What it does |
|---|---|---|
| `--curve FILE` | built-in | Your own CTR by position (`position`, `ctr` columns; 0.3 or 30% both work) |
| `--min-impressions` | 100 | Skip pages with fewer impressions |
| `--max-position` | 20 | Skip pages ranking lower than this |
| `--under` | 0.7 | Underperforming = CTR below this share of the expected CTR |
| `-o`, `--output` | `ctr_report` | File name for the report (`.html` + `.xlsx`) |

<a id="report"></a>

## 📄 The report

The HTML report opens with summary cards (pages checked, below the curve, to rewrite, to check for SERP features,
clicks to win back), the Neil Patel data panel, a **Fix first** table (underperforming pages with snippet problems,
biggest click gap first, with issues, suggested title and fixes) and an **All pages** table. The Excel file has the
same two sheets.

<details>
<summary>📄 Example: real output from <code>examples/</code></summary>

The sample data is made up (fictional site brightcrm.io). The top 8 of 14 pages from `ctr_report.xlsx`, sheet All pages:

| page | query | impressions | ctr | position | expected ctr | extra clicks | verdict |
|---|---|---|---|---|---|---|---|
| /blog/free-crm-template | free crm template | 6,100 | 1.0% | 3.4 | 9.8% | 534 | rewrite snippet |
| /crm-for-small-business | crm for small business | 11,300 | 3.2% | 4.3 | 7.6% | 488 | rewrite snippet |
| /blog/crm-software-comparison | crm software comparison | 7,400 | 1.3% | 5.8 | 5.3% | 297 | rewrite snippet |
| /integrations | crm integrations | 2,600 | 2.7% | 3.9 | 8.3% | 146 | rewrite snippet |
| /blog/sales-pipeline-setup | how to set up a sales pipeline | 5,200 | 2.3% | 6.9 | 4.1% | 93 | rewrite snippet |
| /blog/crm-vs-spreadsheet | crm vs spreadsheet | 2,200 | 2.2% | 5.1 | 6.3% | 92 | rewrite snippet |
| /blog/crm-onboarding-checklist | crm onboarding checklist | 1,800 | 8.3% | 2.4 | 13.4% | 91 | snippet looks fine, check SERP features |
| /blog/lead-scoring-model | lead scoring model | 4,100 | 0.9% | 8.7 | 2.9% | 82 | rewrite snippet |

Summary line: `14 pages, 11 below the curve, 9 to rewrite, 2 to check for SERP features, 1944 clicks to win back`

</details>

## 🧰 More free SEO tools

This repo is one tool in the **[SEO Toolbox](https://github.com/marketing-MEER/seo-toolbox)**, a family of free, single-purpose SEO tools. Related:
- [heading-structure-auditor](https://github.com/marketing-MEER/heading-structure-auditor): check H1-H6 structure page by page
- [url-structure-auditor](https://github.com/marketing-MEER/url-structure-auditor): audit URL length, depth and patterns
- [content-decay-detector](https://github.com/marketing-MEER/content-decay-detector): find pages that are losing traffic
- [seo-workhorse](https://github.com/marketing-MEER/seo-workhorse): audit, clustering, redirects and GSC quick wins in one CLI

<a id="faq"></a>

## ❓ FAQ

<details><summary><b>Where does the expected CTR come from?</b></summary>

From a built-in curve of rounded rules of thumb. Real CTR varies by industry, device, brand and SERP layout, so for
decisions use your own curve: export your site's average CTR by position from Search Console and pass it with `--curve`.
</details>

<details><summary><b>Why does a page with a perfect snippet still show up?</b></summary>

If CTR is below the curve and the title and meta pass every check, the tool says "snippet looks fine, check SERP
features". Open the query in Google: a video, image pack, People Also Ask box or carousel above you is a likelier cause
than your wording.
</details>

<details><summary><b>Is my data sent anywhere?</b></summary>

No. The tool reads the two files you give it on your own machine and makes no network requests.
</details>

## 🧪 Tests

```bash
python -m unittest discover -s tests -t . -v
```

## 📄 License

[MIT](LICENSE). Free for personal and commercial use. Benchmark figures © their original publishers and quoted with a link to the source.

<a id="author"></a>

## 👤 Author

**Meer Hamza** · SEO Team Lead · Berlin 🇩🇪
10+ years in SEO, AEO and GEO. I build small tools that take the spreadsheet work out of SEO.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)
[![Email](https://img.shields.io/badge/Email-meerhamza5%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:meerhamza5@gmail.com)

<div align="center">

**If this saved you time, a ⭐ helps other SEOs find it.**

</div>
