#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CRITICAL = {
    'https://classreklamtabela.com.tr/',
    'https://classreklamtabela.com.tr/iletisim/',
    'https://classreklamtabela.com.tr/hizmetlerimiz/',
    'https://classreklamtabela.com.tr/hakkimizda/',
    'https://classreklamtabela.com.tr/blog/',
    'https://classreklamtabela.com.tr/referanslar/',
    'https://classreklamtabela.com.tr/edremit-tabela/',
    'https://classreklamtabela.com.tr/totem-tabela/',
    'https://classreklamtabela.com.tr/dijital-baski/',
    'https://classreklamtabela.com.tr/arac-giydirme/',
    'https://classreklamtabela.com.tr/cam-giydirme/',
    'https://classreklamtabela.com.tr/kutu-harf-tabela/',
}
COMMERCIAL = {
    'https://classreklamtabela.com.tr/edremit-tabela/',
    'https://classreklamtabela.com.tr/totem-tabela/',
    'https://classreklamtabela.com.tr/dijital-baski/',
    'https://classreklamtabela.com.tr/arac-giydirme/',
    'https://classreklamtabela.com.tr/cam-giydirme/',
    'https://classreklamtabela.com.tr/kutu-harf-tabela/',
}


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else '.ops/seo-site-crawl-2026-08-14.json')
    data = json.loads(source.read_text(encoding='utf-8'))
    pages = {p.get('url'): p for p in data.get('pages', []) if isinstance(p, dict)}
    failures, warnings = [], []

    sitemap_files = data.get('sitemaps') or []
    if not sitemap_files:
        failures.append({'check': 'sitemap_discovery', 'detail': 'no sitemap evidence'})
    for sm in sitemap_files:
        if sm.get('http') != 200:
            failures.append({'check': 'sitemap_http', 'url': sm.get('url'), 'detail': f"HTTP {sm.get('http')} location={sm.get('location', '')}"})
        if sm.get('waf'):
            failures.append({'check': 'sitemap_waf', 'url': sm.get('url')})
        if sm.get('parse_error'):
            failures.append({'check': 'sitemap_parse', 'url': sm.get('url'), 'detail': sm.get('parse_error')})

    if data.get('waf_urls'):
        failures.append({'check': 'waf', 'detail': f"WAF obscured {len(data['waf_urls'])} crawled URLs"})
    if data.get('broken_internal_edges'):
        failures.append({'check': 'broken_internal_links', 'detail': data['broken_internal_edges'][:25]})
    if data.get('duplicate_titles'):
        failures.append({'check': 'duplicate_titles', 'detail': data['duplicate_titles'][:20]})
    if data.get('duplicate_descriptions'):
        failures.append({'check': 'duplicate_descriptions', 'detail': data['duplicate_descriptions'][:20]})

    sitemap_urls = set(data.get('sitemap_seed_urls') or [])
    for url in sorted(sitemap_urls):
        p = pages.get(url)
        if not p:
            failures.append({'check': 'sitemap_url_not_crawled', 'url': url})
            continue
        if p.get('http') != 200:
            failures.append({'check': 'sitemap_non200_url', 'url': url, 'detail': f"HTTP {p.get('http')} location={p.get('location', '')}"})
        if p.get('classification') != 'INDEX':
            failures.append({'check': 'sitemap_nonindex_url', 'url': url, 'detail': p.get('classification')})
        if p.get('canonical') != url:
            failures.append({'check': 'sitemap_nonself_canonical', 'url': url, 'detail': p.get('canonical')})

    for url in sorted(CRITICAL):
        p = pages.get(url)
        if not p:
            failures.append({'check': 'critical_url_missing', 'url': url, 'detail': 'not discovered/crawled'})
            continue
        if p.get('http') != 200:
            failures.append({'check': 'critical_http', 'url': url, 'detail': f"HTTP {p.get('http')}"})
        if p.get('classification') != 'INDEX':
            failures.append({'check': 'critical_indexability', 'url': url, 'detail': p.get('classification')})
        if not str(p.get('title') or '').strip(): failures.append({'check': 'missing_title', 'url': url})
        if not str(p.get('description') or '').strip(): failures.append({'check': 'missing_description', 'url': url})
        if len(p.get('h1') or []) != 1: failures.append({'check': 'h1_count', 'url': url, 'detail': p.get('h1')})
        if p.get('canonical') != url: failures.append({'check': 'self_canonical', 'url': url, 'detail': p.get('canonical')})

    for url in sorted(COMMERCIAL):
        p = pages.get(url)
        if p and int(p.get('incoming_internal_count') or 0) == 0:
            failures.append({'check': 'orphan_commercial_page', 'url': url})

    indexable = [p for p in pages.values() if p.get('classification') == 'INDEX']
    for p in indexable:
        url = p.get('url')
        if not p.get('title'): failures.append({'check': 'missing_title', 'url': url})
        if not p.get('description'): warnings.append({'check': 'missing_description_noncritical', 'url': url})
        if len(p.get('h1') or []) != 1: failures.append({'check': 'indexable_h1_count', 'url': url, 'detail': p.get('h1')})
        if not p.get('canonical'): failures.append({'check': 'missing_canonical', 'url': url})
        elif p.get('canonical') != url: failures.append({'check': 'nonself_canonical_indexable', 'url': url, 'detail': p.get('canonical')})

    legacy = pages.get('https://classreklamtabela.com.tr/referans-isler/')
    if legacy and legacy.get('classification') == 'INDEX':
        failures.append({'check': 'legacy_references_still_indexable', 'url': legacy.get('url')})

    report = {
        'status': 'PASS' if not failures else 'FAIL',
        'crawled_count': data.get('crawled_count'),
        'sitemap_url_count': len(sitemap_urls),
        'indexable_count': len(indexable),
        'failures': failures,
        'warnings': warnings,
    }
    out = source.parent / 'seo-crawl-gate-2026-08-14.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == '__main__': main()
