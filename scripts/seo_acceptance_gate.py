#!/usr/bin/env python3
import json
import sys
from pathlib import Path

BASE = 'https://classreklamtabela.com.tr'
CRITICAL_PATHS = [
    '/', '/iletisim/', '/hizmetlerimiz/', '/hakkimizda/', '/blog/', '/referanslar/',
    '/edremit-tabela/', '/totem-tabela/', '/dijital-baski/', '/arac-giydirme/',
    '/cam-giydirme/', '/kutu-harf-tabela/'
]
REQUIRED_CONTENT_H1_SLUGS = {
    'iletisim', 'edremit-tabela', 'totem-tabela', 'dijital-baski',
    'arac-giydirme', 'cam-giydirme', 'kutu-harf-tabela'
}


def fail(results, key, detail):
    results.append({'check': key, 'status': 'FAIL', 'detail': detail})


def passed(results, key, detail):
    results.append({'check': key, 'status': 'PASS', 'detail': detail})


def indeterminate(results, key, detail):
    results.append({'check': key, 'status': 'INDETERMINATE', 'detail': detail})


def expected_url(path):
    return BASE + ('/' if path == '/' else path)


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else '.ops/full-seo-baseline-2026-08-14.json')
    data = json.loads(source.read_text(encoding='utf-8'))
    checks = []

    settings = data.get('settings', {})
    vals = settings.get('values', {}) if isinstance(settings, dict) else {}
    if settings.get('ok') and vals.get('url') == BASE and vals.get('home') == BASE:
        passed(checks, 'canonical_site_url', f"url/home={BASE}")
    else:
        fail(checks, 'canonical_site_url', f"settings={vals}")

    cats = data.get('categories', {})
    items = cats.get('items', []) if isinstance(cats, dict) else []
    uncategorized = [c for c in items if str(c.get('slug', '')).lower() == 'uncategorized']
    if cats.get('ok') and not uncategorized:
        passed(checks, 'uncategorized_removed', f"categories={len(items)}")
    elif cats.get('ok'):
        fail(checks, 'uncategorized_removed', f"remaining={uncategorized}")
    else:
        indeterminate(checks, 'uncategorized_removed', f"category audit unavailable: {cats}")

    pages = data.get('pages', {})
    page_items = pages.get('items', []) if isinstance(pages, dict) else []
    published_slugs = {p.get('slug') for p in page_items if p.get('status') == 'publish'}
    required_slugs = {
        'iletisim', 'hizmetlerimiz', 'hakkimizda', 'blog', 'edremit-tabela', 'totem-tabela',
        'dijital-baski', 'arac-giydirme', 'cam-giydirme', 'kutu-harf-tabela'
    }
    missing = sorted(required_slugs - published_slugs)
    if pages.get('ok') and not missing:
        passed(checks, 'commercial_pages_published', f"required={len(required_slugs)}")
    elif pages.get('ok'):
        fail(checks, 'commercial_pages_published', f"missing={missing}")
    else:
        indeterminate(checks, 'commercial_pages_published', f"page audit unavailable: {pages}")

    home = data.get('homepage_source', {})
    h1s = [x.strip() for x in home.get('h1', []) if str(x).strip()] if isinstance(home, dict) else []
    if home.get('http') == 200 and len(h1s) == 1:
        passed(checks, 'homepage_single_h1', h1s[0])
    elif home.get('http') == 200:
        fail(checks, 'homepage_single_h1', f"h1_count={len(h1s)} h1={h1s}")
    else:
        indeterminate(checks, 'homepage_single_h1', f"homepage source unavailable: {home}")

    page_source = data.get('critical_page_source_audit')
    if isinstance(page_source, list):
        by_slug = {p.get('slug'): p for p in page_source if isinstance(p, dict)}
        for slug in sorted(REQUIRED_CONTENT_H1_SLUGS):
            item = by_slug.get(slug)
            key = f'content_h1:{slug}'
            if not item:
                fail(checks, key, 'source audit item missing')
            elif item.get('h1_count') == 1:
                passed(checks, key, f"h1={item.get('h1')}")
            else:
                fail(checks, key, f"h1_count={item.get('h1_count')} h1={item.get('h1')}")
    else:
        indeterminate(checks, 'critical_page_source_audit', f"source audit unavailable: {page_source}")

    blog_source = data.get('blog_source_audit')
    if isinstance(blog_source, list):
        duplicate_title_h1 = [
            {'id': p.get('id'), 'slug': p.get('slug'), 'count': p.get('title_matching_h1_count')}
            for p in blog_source if int(p.get('title_matching_h1_count') or 0) > 0
        ]
        repeated_intro = [
            {'id': p.get('id'), 'slug': p.get('slug'), 'count': p.get('first_paragraph_occurrences')}
            for p in blog_source if int(p.get('first_paragraph_occurrences') or 0) > 1
        ]
        literal_uncategorized = [
            {'id': p.get('id'), 'slug': p.get('slug')}
            for p in blog_source if p.get('literal_uncategorized_in_content')
        ]
        if duplicate_title_h1:
            fail(checks, 'blog_embedded_duplicate_title_h1', f"affected={duplicate_title_h1}")
        else:
            passed(checks, 'blog_embedded_duplicate_title_h1', f"posts={len(blog_source)}")
        if repeated_intro:
            fail(checks, 'blog_repeated_first_paragraph', f"affected={repeated_intro}")
        else:
            passed(checks, 'blog_repeated_first_paragraph', f"posts={len(blog_source)}")
        if literal_uncategorized:
            fail(checks, 'blog_literal_uncategorized_content', f"affected={literal_uncategorized}")
        else:
            passed(checks, 'blog_literal_uncategorized_content', f"posts={len(blog_source)}")
    else:
        indeterminate(checks, 'blog_source_audit', f"source audit unavailable: {blog_source}")

    heads = data.get('rankmath_heads', {})
    for path in CRITICAL_PATHS:
        head = heads.get(path, {}) if isinstance(heads, dict) else {}
        key = f'rankmath_head:{path}'
        if not head.get('ok'):
            indeterminate(checks, key, f"HTTP={head.get('http')} error={head.get('error', '')}")
            continue
        expected = expected_url(path)
        problems = []
        if not head.get('title'):
            problems.append('missing title')
        if not head.get('description'):
            problems.append('missing description')
        if head.get('canonical') != expected:
            problems.append(f"canonical={head.get('canonical')!r}, expected={expected!r}")
        if 'noindex' in str(head.get('robots', '')).lower():
            problems.append(f"robots={head.get('robots')}")
        if problems:
            fail(checks, key, '; '.join(problems))
        else:
            passed(checks, key, f"canonical={expected}")

    hosts = data.get('host_variants', {})
    canonical_host = hosts.get('https_non_www', {}) if isinstance(hosts, dict) else {}
    if canonical_host.get('waf_challenge'):
        indeterminate(checks, 'https_non_www_public', 'WAF challenge returned to audit runner')
    elif canonical_host.get('http') == 200:
        passed(checks, 'https_non_www_public', 'HTTP 200')
    else:
        fail(checks, 'https_non_www_public', f"result={canonical_host}")

    for name, expected_location in [
        ('http_non_www', BASE + '/'),
        ('https_www', BASE + '/'),
    ]:
        result = hosts.get(name, {}) if isinstance(hosts, dict) else {}
        key = f'host_redirect:{name}'
        if result.get('waf_challenge'):
            indeterminate(checks, key, 'WAF challenge returned to audit runner')
        elif result.get('http') in (301, 308) and result.get('location') == expected_location:
            passed(checks, key, f"{result.get('http')} -> {expected_location}")
        else:
            fail(checks, key, f"HTTP={result.get('http')} location={result.get('location')!r}")

    public = data.get('technical_public', {})
    robots = public.get('robots', {}) if isinstance(public, dict) else {}
    if robots.get('waf_challenge'):
        indeterminate(checks, 'robots_public', 'WAF challenge returned to audit runner')
    elif robots.get('http') == 200 and 'text/plain' in str(robots.get('content_type', '')).lower():
        passed(checks, 'robots_public', f"content_type={robots.get('content_type')}")
    else:
        fail(checks, 'robots_public', f"result={robots}")

    sitemap = public.get('rankmath_sitemap', {}) if isinstance(public, dict) else {}
    if sitemap.get('waf_challenge'):
        indeterminate(checks, 'rankmath_sitemap_public', 'WAF challenge returned to audit runner')
    elif sitemap.get('http') == 200 and ('xml' in str(sitemap.get('content_type', '')).lower() or '<?xml' in str(sitemap.get('sample', '')).lower()):
        passed(checks, 'rankmath_sitemap_public', f"content_type={sitemap.get('content_type')}")
    else:
        fail(checks, 'rankmath_sitemap_public', f"result={sitemap}")

    legacy = public.get('legacy_references', {}) if isinstance(public, dict) else {}
    if legacy.get('waf_challenge'):
        indeterminate(checks, 'legacy_references', 'WAF challenge returned to audit runner')
    elif legacy.get('http') in (301, 308) and legacy.get('location') == BASE + '/referanslar/':
        passed(checks, 'legacy_references', f"redirects to {BASE}/referanslar/")
    elif legacy.get('http') in (404, 410):
        passed(checks, 'legacy_references', f"legacy URL intentionally unavailable: {legacy.get('http')}")
    else:
        fail(checks, 'legacy_references', f"legacy URL result={legacy}")

    counts = {
        'PASS': sum(1 for c in checks if c['status'] == 'PASS'),
        'FAIL': sum(1 for c in checks if c['status'] == 'FAIL'),
        'INDETERMINATE': sum(1 for c in checks if c['status'] == 'INDETERMINATE'),
    }
    status = 'PASS' if counts['FAIL'] == 0 and counts['INDETERMINATE'] == 0 else 'FAIL_CLOSED'
    report = {'status': status, 'counts': counts, 'checks': checks}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if status == 'PASS' else 1)


if __name__ == '__main__':
    main()
