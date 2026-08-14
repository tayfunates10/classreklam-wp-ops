#!/usr/bin/env python3
import argparse
import collections
import datetime as dt
import html
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://classreklamtabela.com.tr'
UA = 'Mozilla/5.0 (compatible; ClassReklamSEOAudit/1.0; +https://classreklamtabela.com.tr/)'
EXCLUDE_PREFIXES = ('/wp-admin', '/wp-login.php', '/wp-json', '/xmlrpc.php', '/feed')
EXCLUDE_QUERY_KEYS = {'s', 'replytocom', 'preview', 'elementor-preview'}
MAX_URLS = 220
DELAY = 0.85


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.title = ''
        self._in_title = False
        self._title_buf = []
        self.h1 = []
        self._h1_depth = 0
        self._h1_buf = []
        self.description = ''
        self.robots = ''
        self.canonical = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); tag = tag.lower()
        if tag == 'a' and attrs.get('href'): self.links.append(attrs['href'])
        elif tag == 'title': self._in_title = True; self._title_buf = []
        elif tag == 'h1':
            self._h1_depth += 1
            if self._h1_depth == 1: self._h1_buf = []
        elif tag == 'meta':
            name = (attrs.get('name') or '').lower()
            if name == 'description' and not self.description: self.description = attrs.get('content') or ''
            elif name == 'robots' and not self.robots: self.robots = attrs.get('content') or ''
        elif tag == 'link':
            rel = attrs.get('rel') or ''
            if isinstance(rel, str) and 'canonical' in rel.lower().split() and not self.canonical:
                self.canonical = attrs.get('href') or ''
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'title' and self._in_title:
            self.title = clean(' '.join(self._title_buf)); self._in_title = False
        elif tag == 'h1' and self._h1_depth:
            if self._h1_depth == 1: self.h1.append(clean(' '.join(self._h1_buf)))
            self._h1_depth -= 1
    def handle_data(self, data):
        if self._in_title: self._title_buf.append(data)
        if self._h1_depth: self._h1_buf.append(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


OPENER = urllib.request.build_opener(NoRedirect)


def clean(s): return re.sub(r'\s+', ' ', html.unescape(str(s or ''))).strip()


def canonicalize(raw, base=BASE + '/'):
    if not raw: return None
    p = urllib.parse.urlsplit(urllib.parse.urljoin(base, raw))
    if p.scheme not in ('http', 'https'): return None
    if (p.hostname or '').lower() not in ('classreklamtabela.com.tr', 'www.classreklamtabela.com.tr'): return None
    path = p.path or '/'
    if path.startswith(EXCLUDE_PREFIXES): return None
    if re.search(r'\.(?:jpg|jpeg|png|gif|webp|avif|svg|pdf|zip|css|js|xml|ico|woff2?|ttf|eot)$', path, re.I): return None
    qs = urllib.parse.parse_qs(p.query, keep_blank_values=True)
    if any(k in EXCLUDE_QUERY_KEYS or k.startswith('utm_') for k in qs):
        qs = {k: v for k, v in qs.items() if k not in EXCLUDE_QUERY_KEYS and not k.startswith('utm_')}
    query = urllib.parse.urlencode([(k, x) for k in sorted(qs) for x in qs[k]]) if qs else ''
    return urllib.parse.urlunsplit(('https', 'classreklamtabela.com.tr', path, query, ''))


def get(url, limit=1_500_000):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xml,text/xml;q=0.9,*/*;q=0.5'})
    try:
        with OPENER.open(req, timeout=40) as r:
            body = r.read(limit).decode('utf-8', errors='replace')
            return {'http': r.status, 'url': r.geturl(), 'location': r.headers.get('Location', ''), 'content_type': r.headers.get('Content-Type', ''), 'body': body}
    except urllib.error.HTTPError as e:
        body = e.read(limit).decode('utf-8', errors='replace')
        return {'http': e.code, 'url': e.geturl(), 'location': e.headers.get('Location', ''), 'content_type': e.headers.get('Content-Type', ''), 'body': body}
    except Exception as e:
        return {'http': 0, 'url': url, 'location': '', 'content_type': '', 'body': '', 'error': f'{type(e).__name__}: {e}'}


def waf(body):
    low = (body or '').lower(); return 'one moment, please' in low or 'imunify360' in low


def sitemap_urls():
    discovered, evidence = set(), []
    queue, seen_maps = collections.deque([BASE + '/sitemap_index.xml']), set()
    while queue and len(seen_maps) < 20:
        sm = queue.popleft()
        if sm in seen_maps: continue
        seen_maps.add(sm); time.sleep(DELAY); res = get(sm)
        item = {'url': sm, 'http': res['http'], 'location': res.get('location', ''), 'content_type': res['content_type'], 'waf': waf(res['body']), 'locs': 0}
        if res['http'] != 200 or item['waf']:
            evidence.append(item); continue
        try:
            root = ET.fromstring(res['body'])
            locs = [clean(el.text) for el in root.iter() if el.tag.lower().endswith('loc') and el.text]
            item['locs'] = len(locs)
            if root.tag.lower().endswith('sitemapindex'):
                for loc in locs:
                    if loc.startswith(BASE): queue.append(loc)
            else:
                for loc in locs:
                    u = canonicalize(loc)
                    if u: discovered.add(u)
        except Exception as exc: item['parse_error'] = str(exc)
        evidence.append(item)
    return discovered, evidence


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output', default='.ops/seo-site-crawl-2026-08-14.json'); args = ap.parse_args()
    sitemap_seeds, sm_evidence = sitemap_urls()
    crawl_seeds = set(sitemap_seeds); crawl_seeds.add(BASE + '/')
    q, seen, pages = collections.deque(sorted(crawl_seeds)), set(), {}
    incoming, broken_edges, waf_urls = collections.defaultdict(set), [], []

    while q and len(seen) < MAX_URLS:
        url = q.popleft()
        if url in seen: continue
        seen.add(url); time.sleep(DELAY); res = get(url); body = res.get('body', ''); is_waf = waf(body)
        if is_waf: waf_urls.append(url)
        parser = Parser()
        if res.get('http') == 200 and 'html' in res.get('content_type', '').lower() and not is_waf:
            try: parser.feed(body)
            except Exception: pass
        record = {
            'url': url, 'http': res.get('http'), 'location': res.get('location', ''), 'final_url': res.get('url'),
            'content_type': res.get('content_type'), 'waf': is_waf, 'sitemap_seed': url in sitemap_seeds,
            'title': clean(parser.title), 'description': clean(parser.description),
            'canonical': canonicalize(parser.canonical, url) if parser.canonical else '', 'robots': clean(parser.robots),
            'h1': [x for x in parser.h1 if x], 'internal_links': [], 'error': res.get('error', ''),
        }
        links = []
        for href in parser.links:
            child = canonicalize(href, url)
            if child:
                links.append(child); incoming[child].add(url)
                if child not in seen and child not in q and len(seen) + len(q) < MAX_URLS: q.append(child)
        record['internal_links'] = sorted(set(links)); pages[url] = record

    for source, rec in pages.items():
        for target in rec.get('internal_links', []):
            if target in pages and pages[target].get('http') not in (200, 301, 302, 307, 308):
                broken_edges.append({'source': source, 'target': target, 'http': pages[target].get('http')})

    for url, rec in pages.items():
        rec['incoming_internal_count'] = len(incoming.get(url, set()))
        rec['classification'] = (
            'INDETERMINATE' if rec['waf'] or rec['http'] == 0 else
            'REDIRECT' if rec['http'] in (301, 302, 307, 308) else
            'REMOVE' if rec['http'] in (404, 410) else
            'INDEX' if rec['http'] == 200 and 'noindex' not in rec['robots'].lower() else
            'NOINDEX' if rec['http'] == 200 else 'ERROR'
        )

    title_map, desc_map = collections.defaultdict(list), collections.defaultdict(list)
    for url, rec in pages.items():
        if rec['classification'] != 'INDEX': continue
        if rec['title']: title_map[rec['title'].casefold()].append(url)
        if rec['description']: desc_map[rec['description'].casefold()].append(url)

    report = {
        'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'base': BASE,
        'limits': {'max_urls': MAX_URLS, 'delay_seconds': DELAY}, 'sitemaps': sm_evidence,
        'sitemap_seed_count': len(sitemap_seeds), 'sitemap_seed_urls': sorted(sitemap_seeds),
        'crawled_count': len(pages), 'waf_urls': waf_urls, 'broken_internal_edges': broken_edges,
        'duplicate_titles': [v for v in title_map.values() if len(v) > 1],
        'duplicate_descriptions': [v for v in desc_map.values() if len(v) > 1], 'pages': list(pages.values()),
    }
    with open(args.output, 'w', encoding='utf-8') as f: json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({'crawled': len(pages), 'sitemap_seeds': len(sitemap_seeds), 'waf': len(waf_urls), 'broken_edges': len(broken_edges), 'duplicate_titles': len(report['duplicate_titles']), 'duplicate_descriptions': len(report['duplicate_descriptions'])}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
