from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import median

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult


def _money(value: float | None, currency: str = "EUR") -> str:
    if value is None:
        return "nav norādīta"
    return f"{value:.2f} {escape(currency)}"


def _analytics(entities: list[MarketEntity]) -> dict:
    relevant = [e for e in entities if e.is_relevant]
    prices = [e.price for e in relevant if e.price is not None]
    sellers = {e.seller.strip() for e in relevant if e.seller.strip()}
    category_counts = Counter(e.category for e in relevant)

    return {
        "total": len(entities),
        "relevant": len(relevant),
        "sellers": len(sellers),
        "median_price": median(prices) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "category_counts": category_counts,
    }


def generate_html_report(
    project: ResearchProject,
    result: ResearchRunResult,
) -> str:
    stats = _analytics(result.entities)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    cards = []
    for entity in sorted(
        result.entities,
        key=lambda e: (not e.is_relevant, -e.relevance_score, e.title.lower()),
    ):
        image = (
            f'<img class="thumb" src="{escape(entity.image_url)}" alt="">'
            if entity.image_url
            else '<div class="thumb placeholder">bez attēla</div>'
        )
        attrs = "".join(
            f"<dt>{escape(str(key))}</dt><dd>{escape(str(value))}</dd>"
            for key, value in entity.attributes.items()
            if value not in ("", None, [], {})
        )

        cards.append(
            f"""
            <article class="card {'irrelevant' if not entity.is_relevant else ''}">
              {image}
              <div class="body">
                <div class="chips">
                  <span>{escape(entity.entity_type)}</span>
                  <span>{escape(entity.category)}</span>
                  <span>relevance {entity.relevance_score:.0%}</span>
                </div>
                <h3>{escape(entity.title)}</h3>
                <div class="meta">
                  <strong>{_money(entity.price, entity.currency)}</strong>
                  <span>{escape(entity.seller or "pārdevējs nav atrasts")}</span>
                </div>
                <p>{escape((entity.description or "—")[:800])}</p>
                <dl>
                  {attrs or '<dt>Attributes</dt><dd>—</dd>'}
                  <dt>Ieguve</dt><dd>{escape(entity.extraction_method)}</dd>
                </dl>
                {
                    f'<p class="op"><b>Iespējas piezīme:</b> {escape(entity.opportunity_notes)}</p>'
                    if entity.opportunity_notes else ''
                }
                <a href="{escape(entity.source_url)}">Atvērt avotu ↗</a>
              </div>
            </article>
            """
        )

    category_rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{count}</td></tr>"
        for name, count in stats["category_counts"].most_common()
    ) or '<tr><td colspan="2">Nav datu</td></tr>'

    domain_rows = "".join(
        f"""
        <tr>
          <td>{escape(record.domain)}</td>
          <td>{escape(record.status)}</td>
          <td>{record.relevance_score:.2f}</td>
          <td>{record.pages_seen}</td>
          <td>{record.entities_found}</td>
          <td>{escape(record.robots_status)}</td>
          <td>{escape(record.sitemap_status)}</td>
          <td>{record.sitemap_urls_found}</td>
          <td>{escape(record.reason or '—')}</td>
        </tr>
        """
        for record in sorted(
            result.domains.values(),
            key=lambda item: (-item.relevance_score, item.domain),
        )
    ) or '<tr><td colspan="9">Nav</td></tr>'

    return f"""<!doctype html>
<html lang="lv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(project.name)} — Sprīdītis</title>
<style>
:root {{
 --bg:#0d1015; --panel:#171b22; --panel2:#1d232d; --line:#2b3441;
 --text:#edf2f7; --muted:#98a5b3; --a:#82c5ff; --ok:#7fdaa7;
}}
* {{ box-sizing:border-box }}
body {{ margin:0;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif }}
.wrap {{ max-width:1240px;margin:auto;padding:28px }}
.hero {{ background:linear-gradient(135deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:18px;padding:28px }}
h1 {{ font-size:clamp(32px,5vw,56px);margin:0 0 8px }}
.muted {{ color:var(--muted) }}
.stats {{ display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:20px 0 }}
.stat {{ background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px }}
.stat b {{ display:block;font-size:26px }}
.stat span {{ color:var(--muted);font-size:12px }}
.grid {{ display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px }}
.card {{ display:grid;grid-template-columns:180px 1fr;background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden }}
.card.irrelevant {{ opacity:.55 }}
.thumb {{ width:100%;height:100%;min-height:220px;object-fit:cover;background:#080a0d }}
.placeholder {{ display:grid;place-items:center;color:var(--muted) }}
.body {{ padding:17px }}
.body h3 {{ margin:9px 0 }}
.chips {{ display:flex;gap:7px;flex-wrap:wrap }}
.chips span {{ border:1px solid var(--line);border-radius:999px;padding:4px 7px;color:var(--muted);font-size:11px }}
.meta {{ display:flex;gap:13px;flex-wrap:wrap;color:var(--muted) }}
.meta strong {{ color:var(--ok) }}
dl {{ display:grid;grid-template-columns:145px 1fr;gap:6px 10px;font-size:13px }}
dt {{ color:var(--muted) }}
dd {{ margin:0 }}
a {{ color:var(--a) }}
table {{ width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line) }}
td,th {{ padding:10px;border-bottom:1px solid var(--line);text-align:left }}
.cols {{ display:grid;grid-template-columns:1fr 1fr;gap:18px }}
.panel {{ background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px }}
.op {{ border-left:3px solid var(--ok);padding-left:10px }}
@media(max-width:900px) {{
 .stats {{ grid-template-columns:repeat(2,1fr) }}
 .grid,.cols {{ grid-template-columns:1fr }}
 .card {{ grid-template-columns:1fr }}
 .thumb {{ height:260px }}
}}
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <h1>Sprīdītis 3.3</h1>
  <h2>{escape(project.name)}</h2>
  <p>{escape(project.description)}</p>
  <p class="muted">
    Projekts: {escape(project.id)} · Tips: {escape(project.research_type)} ·
    Režīms: {escape(project.crawl.mode)} · Ģenerēts: {generated}
  </p>
</header>

<div class="stats">
  <div class="stat"><b>{stats["relevant"]}</b><span>relevanti objekti</span></div>
  <div class="stat"><b>{stats["sellers"]}</b><span>unikāli pārdevēji</span></div>
  <div class="stat"><b>{_money(stats["median_price"])}</b><span>mediānas cena</span></div>
  <div class="stat"><b>{result.visited_pages}</b><span>apmeklētas lapas</span></div>
  <div class="stat"><b>{len(result.domains)}</b><span>novēroti domēni</span></div>
</div>

<section class="cols">
  <div class="panel">
    <h2>Kategorijas</h2>
    <table><tbody>{category_rows}</tbody></table>
  </div>
  <div class="panel">
    <h2>Domain Registry</h2>
    <div style="overflow:auto">
      <table>
        <thead>
          <tr>
            <th>Domain</th><th>Status</th><th>Score</th>
            <th>Pages</th><th>Entities</th><th>Robots</th><th>Sitemap</th><th>URLs</th><th>Reason</th>
          </tr>
        </thead>
        <tbody>{domain_rows}</tbody>
      </table>
    </div>
  </div>
</section>

<section>
  <h2>Atrastie tirgus objekti</h2>
  <div class="grid">{''.join(cards) or '<p class="muted">Nekas netika atrasts.</p>'}</div>
</section>

<p class="muted">
  failed={result.failed_pages} · robots_skipped={result.skipped_by_robots} ·
  search_queries={result.search_queries_issued} · search_raw={result.search_results_seen} ·
  search_unique={result.search_results_unique} · search_duplicates={result.search_results_duplicates} ·
  search_activated={result.search_domains_activated} · search_errors={result.search_provider_errors} ·
  feed_candidates={result.feed_candidates_seen} · feeds={result.feeds_found} ·
  feed_entries={result.feed_entries_seen} · feed_new={result.feed_entries_new} ·
  feed_304={result.feed_not_modified} · feed_errors={result.feed_errors} ·
  kopā atrasti={len(result.entities)}
</p>
</div>
</body>
</html>
"""


def save_html_report(
    html: str,
    report_dir: Path,
    project_id: str,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"{project_id}_{stamp}.html"
    path.write_text(html, encoding="utf-8")
    return path
