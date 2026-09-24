
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.discovery import parse_sitemap_xml


def main():
    urlset = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://example.com/b</loc></url>
    </urlset>
    """

    kind, urls = parse_sitemap_xml(urlset)
    assert kind == "urlset"
    assert urls == [
        "https://example.com/a",
        "https://example.com/b",
    ]

    index = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/sitemap-products.xml</loc></sitemap>
    </sitemapindex>
    """

    kind, urls = parse_sitemap_xml(index)
    assert kind == "sitemapindex"
    assert urls == [
        "https://example.com/sitemap-products.xml",
    ]

    kind, urls = parse_sitemap_xml("<broken")
    assert kind == "invalid"
    assert urls == []

    print("SITEMAP TEST OK")


if __name__ == "__main__":
    main()
