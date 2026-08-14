#!/usr/bin/env python3
import base64
import datetime as dt
import html
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
CTX = ssl.create_default_context()


def queryrest_url(route, params=None):
    if route.startswith('/wp-json'):
        route = route[len('/wp-json'):]
    qs = {'rest_route': route}
    if params:
        qs.update(params)
    return BASE + '/?' + urllib.parse.urlencode(qs, doseq=True, safe='/:')


def request_json(route, params=None, delay=2.0):
    time.sleep(delay)
    url = queryrest_url(route, params)
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': AUTH,
            'Accept': 'application/json',
            'User-Agent': UA,
            'Referer': BASE + '/wp-admin/',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw) if raw else None
            except Exception:
                body = {'raw_sample': raw[:1000]}
            return {'http': r.status, 'ok': 200 <= r.status < 300, 'body': body}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw_sample': raw[:1000]}
        return {'http': e.code, 'ok': False, 'body': body}
    except Exception as e:
        return {'http': 0, 'ok': False, 'error': f'{type(e).__name__}: {e}'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_fetch(url, method='GET'):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method=method, headers={'User-Agent': UA, 'Accept': '*/*'})
    try:
        with opener.open(req, timeout=35) as r:
            raw = r.read(300000).decode('utf-8', errors='replace') if method != 'HEAD' else ''
            title_match = re.search(r'<title[^>]*>(.*?)</title>', raw, re.I | re.S)
            return {
                'http': r.status,
                'location': r.headers.get('Location', ''),
                'content_type': r.headers.get('Content-Type', ''),
                'server': r.headers.get('Server', ''),
                'cache_control': r.headers.get('Cache-Control', ''),
                'waf_challenge': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(),
                'title': title_match.group(1).strip() if title_match else '',
                'sample': re.sub(r'\s+', ' ', raw[:500]).strip(),
            }
    except urllib.error.HTTPError as e:
        raw = e.read(300000).decode('utf-8', errors='replace') if method != 'HEAD' else ''
        return {
            'http': e.code,
            'location': e.headers.get('Location', ''),
            'content_type': e.headers.get('Content-Type', ''),
            'server': e.headers.get('Server', ''),
            'cache_control': e.headers.get('Cache-Control', ''),
            'waf_challenge': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(),
            'sample': re.sub(r'\s+', ' ', raw[:500]).strip(),
        }
    except Exception as e:
        return {'http': 0, 'error': f'{type(e).__name__}: {e}'}


def slim_list(res, keys):
    body = res.get('body')
    if not isinstance(body, list):
        return res
    return {
        'http': res['http'],
        'ok': res['ok'],
        'items': [{k: item.get(k) for k in keys} for item in body if isinstance(item, dict)],
    }


def safe_settings(res):
    body = res.get('body')
    allowed = [
        'title', 'description', 'url', 'home', 'timezone', 'show_on_front',
        'page_on_front', 'page_for_posts', 'default_category', 'permalink_structure'
    ]
    if not isinstance(body, dict):
        return {'http': res.get('http'), 'ok': res.get('ok'), 'error': res.get('error', '')}
    return {
        'http': res.get('http'),
        'ok': res.get('ok'),
        'values': {key: body.get(key) for key in allowed if key in body},
    }


def plain(value):
    value = html.unescape(str(value or ''))
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def h1_texts(raw):
    return [plain(x) for x in re.findall(r'<h1\b[^>]*>(.*?)</h1>', raw or '', re.I | re.S)]


def first_paragraph(raw):
    match = re.search(r'<p\b[^>]*>(.*?)</p>', raw or '', re.I | re.S)
    return plain(match.group(1)) if match else ''


def source_audit(items):
    audited = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title_obj = item.get('title') or {}
        title = plain(title_obj.get('raw') if isinstance(title_obj, dict) else title_obj)
        content_obj = item.get('content') or {}
        raw = content_obj.get('raw', '') if isinstance(content_obj, dict) else str(content_obj)
        h1s = h1_texts(raw)
        title_h1_count = sum(1 for h in h1s if h.casefold() == title.casefold() and title)
        intro = first_paragraph(raw)
        intro_occurrences = 0
        if intro:
            # Compare normalized paragraph text, not raw markup, so Gutenberg attributes do not matter.
            paragraphs = [plain(x) for x in re.findall(r'<p\b[^>]*>(.*?)</p>', raw, re.I | re.S)]
            intro_occurrences = sum(1 for p in paragraphs if p.casefold() == intro.casefold())
        audited.append({
            'id': item.get('id'),
            'slug': item.get('slug'),
            'status': item.get('status'),
            'title': title,
            'h1_count': len(h1s),
            'h1': h1s,
            'title_matching_h1_count': title_h1_count,
            'first_paragraph_occurrences': intro_occurrences,
            'literal_uncategorized_in_content': 'uncategorized' in plain(raw).casefold(),
            'content_chars': len(raw),
            'modified': item.get('modified'),
        })
    return audited


def rankmath_head(target_url):
    res = request_json('/rankmath/v1/getHead', {'url': target_url}, delay=2.5)
    body = res.get('body')
    html_head = body.get('head', '') if isinstance(body, dict) else ''
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_head, re.I | re.S)
    desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html_head, re.I)
    canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html_head, re.I)
    robots_match = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)', html_head, re.I)
    return {
        'http': res.get('http'),
        'ok': res.get('ok'),
        'title': title_match.group(1).strip() if title_match else '',
        'description': desc_match.group(1) if desc_match else '',
        'canonical': canonical_match.group(1) if canonical_match else '',
        'robots': robots_match.group(1) if robots_match else '',
        'has_jsonld': 'application/ld+json' in html_head.lower(),
        'head_chars': len(html_head),
        'error': res.get('error', ''),
    }


out = {
    'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    'site_url': BASE,
    'mode': 'read-only',
}

out['settings'] = safe_settings(request_json('/wp/v2/settings'))
out['plugins'] = slim_list(
    request_json('/wp/v2/plugins', {'status': 'active', 'per_page': 100}),
    ['plugin', 'status', 'name', 'version'],
)
out['themes'] = slim_list(
    request_json('/wp/v2/themes', {'status': 'active', 'per_page': 100}),
    ['stylesheet', 'template', 'status', 'name', 'version'],
)
out['pages'] = slim_list(
    request_json('/wp/v2/pages', {'context': 'edit', 'per_page': 100, '_fields': 'id,slug,status,link,parent,modified,title'}),
    ['id', 'slug', 'status', 'link', 'parent', 'modified', 'title'],
)
out['posts'] = slim_list(
    request_json('/wp/v2/posts', {'context': 'edit', 'per_page': 100, '_fields': 'id,slug,status,link,modified,title,categories'}),
    ['id', 'slug', 'status', 'link', 'modified', 'title', 'categories'],
)
out['categories'] = slim_list(
    request_json('/wp/v2/categories', {'context': 'edit', 'per_page': 100, 'hide_empty': 'false', '_fields': 'id,name,slug,count,link'}),
    ['id', 'name', 'slug', 'count', 'link'],
)

home = request_json('/wp/v2/pages/6', {'context': 'edit', '_fields': 'id,slug,status,link,modified,title,content'})
if home.get('ok') and isinstance(home.get('body'), dict):
    raw = home['body'].get('content', {}).get('raw', '')
    out['homepage_source'] = {
        'http': home['http'],
        'id': home['body'].get('id'),
        'modified': home['body'].get('modified'),
        'h1': h1_texts(raw),
        'localbusiness_marker': 'class-reklam-localbusiness-schema' in raw,
        'content_chars': len(raw),
    }
else:
    out['homepage_source'] = home

page_source = request_json('/wp/v2/pages', {
    'context': 'edit', 'per_page': 100,
    '_fields': 'id,slug,status,modified,title,content'
}, delay=2.5)
if page_source.get('ok') and isinstance(page_source.get('body'), list):
    critical_slugs = {
        'iletisim', 'hizmetlerimiz', 'hakkimizda', 'blog', 'edremit-tabela', 'totem-tabela',
        'dijital-baski', 'arac-giydirme', 'cam-giydirme', 'kutu-harf-tabela'
    }
    out['critical_page_source_audit'] = source_audit([
        p for p in page_source['body'] if p.get('slug') in critical_slugs
    ])
else:
    out['critical_page_source_audit'] = {'ok': False, 'http': page_source.get('http'), 'error': page_source.get('error', '')}

post_source = request_json('/wp/v2/posts', {
    'context': 'edit', 'per_page': 100,
    '_fields': 'id,slug,status,modified,title,content,categories'
}, delay=2.5)
if post_source.get('ok') and isinstance(post_source.get('body'), list):
    out['blog_source_audit'] = source_audit(post_source['body'])
else:
    out['blog_source_audit'] = {'ok': False, 'http': post_source.get('http'), 'error': post_source.get('error', '')}

critical_urls = [
    '/', '/iletisim/', '/hizmetlerimiz/', '/hakkimizda/', '/blog/', '/referanslar/',
    '/edremit-tabela/', '/totem-tabela/', '/dijital-baski/', '/arac-giydirme/', '/cam-giydirme/', '/kutu-harf-tabela/'
]
out['rankmath_heads'] = {path: rankmath_head(BASE + path) for path in critical_urls}

out['host_variants'] = {
    'http_non_www': public_fetch('http://classreklamtabela.com.tr/'),
    'https_non_www': public_fetch('https://classreklamtabela.com.tr/'),
    'https_www': public_fetch('https://www.classreklamtabela.com.tr/'),
}
out['technical_public'] = {
    'robots': public_fetch(BASE + '/robots.txt'),
    'rankmath_sitemap': public_fetch(BASE + '/sitemap_index.xml'),
    'wp_sitemap': public_fetch(BASE + '/wp-sitemap.xml'),
    'sample_service': public_fetch(BASE + '/edremit-tabela/'),
    'references': public_fetch(BASE + '/referanslar/'),
    'legacy_references': public_fetch(BASE + '/referans-isler/'),
}

print(json.dumps(out, ensure_ascii=False, indent=2))
