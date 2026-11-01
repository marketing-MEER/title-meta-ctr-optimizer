# Example data

Everything in this folder is made up. `brightcrm.io` is a fictional company; the clicks, impressions, positions,
titles and descriptions do not describe a real site.

- `gsc_pages.csv`: a Search Console export with one row per query and page (the first page appears twice, so you can
  see how rows for the same page are merged).
- `crawl.csv`: a crawl export in Screaming Frog's column names (`Address`, `Title 1`, `Meta Description 1`).

```bash
title-meta-ctr-optimizer examples/gsc_pages.csv examples/crawl.csv
```
