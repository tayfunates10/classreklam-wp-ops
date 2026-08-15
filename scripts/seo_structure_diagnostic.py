#!/usr/bin/env python3
import base64
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
OUT = Path('.ops/seo-structure-diagnostic-2026-08-14.json')


def api_url(route, params=None):
    q = {'rest_route': route}
    if params: q.update(params)
    return BASE + '/?' + urllib.parse.urlencode(q, doseq=True, safe='/:,')


def api_once(route, params=None):
    req = urllib.request.Request(api_url(route, params), headers={
        'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try: body = json.loads(raw) if raw else {}
            except Exception: body = {'raw_sample': raw[:2500]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try: body = json.loads(raw)
        except Exception: body = {'raw_sample': raw[:2500]}
        return e.code, body
    except Exception as e:
        return 0, {'error': f'{type(e).__name__}: {e}'}


def api(route, params=None):
    last = None
    for attempt in range(4):
        time.sleep(1.8)
        code, body = api_once(route, params)
        last = (code, body)
        text = json.dumps(body, ensure_ascii=False).lower() if isinstance(body, (dict, list)) else str(body).lower()
        if code != 403 or ('imunify360' not in text and 'bot-protection' not in text):
            return code, body
        time.sleep(8 * (attempt + 1))
    return last


def public(url, limit=900000):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return {'http': r.status, 'url': r.geturl(), 'body': r.read(limit).decode('utf-8', errors='replace')}
    except urllib.error.HTTPError as e:
        return {'http': e.code, 'url': e.geturl(), 'body': e.read(limit).decode('utf-8', errors='replace')}
    except Exception as e:
        return {'http': 0, 'url': url, 'body': '', 'error': f'{type(e).__name__}: {e}'}


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()


def headings(raw):
    out = []
    for m in re.finditer(r'<h([1-6])\b[^>]*>(.*?)</h\1>', raw or '', re.I | re.S):
        text = clean(re.sub(r'<[^>]+>', ' ', m.group(2)))
        out.append({'level': int(m.group(1)), 'text': text, 'html_sample': clean(m.group(0))[:500]})
    return out


def page_diag(page_id):
    code, page = api(f'/wp/v2/pages/{page_id}', {
        'context': 'edit', '_fields': 'id,slug,status,link,title,content,excerpt,modified,template,meta'
    })
    item = {'id': page_id, 'http': code}
    if code == 200 and isinstance(page, dict):
        raw = str((page.get('content') or {}).get('raw') or '')
        item.update({
            'slug': page.get('slug'), 'status': page.get('status'), 'link': page.get('link'),
            'title': (page.get('title') or {}).get('raw'), 'modified': page.get('modified'),
            'content_chars': len(raw), 'headings': headings(raw),
            'has_legacy_reference_link': '/referans-isler/' in raw,
            'has_1183_link': 'page_id=1183' in raw,
            'content_prefix': clean(raw)[:1800],
        })
    else:
        item['body'] = page
    return item


def compact(value):
    if isinstance(value, list):
        return value[:25]
    if isinstance(value, dict):
        return {k: value[k] for k in list(value)[:40]}
    return value


def main():
    result = {'status': 'read-only', 'pages': [], 'routes': {}, 'frontend': {}, 'sitemap': {}}
    for pid in (8, 10, 12, 683, 1183, 1186, 1188, 1190):
        result['pages'].append(page_diag(pid))

    candidates = {
        'navigation': ('/wp/v2/navigation', {'context': 'edit', 'per_page': 100}),
        'menu_items': ('/wp/v2/menu-items', {'context': 'edit', 'per_page': 100}),
        'menus': ('/wp/v2/menus', {'context': 'edit', 'per_page': 100}),
        'types': ('/wp/v2/types', {'context': 'edit'}),
    }
    for name, (route, params) in candidates.items():
        code, body = api(route, params)
        entry = {'http': code}
        if name == 'types' and isinstance(body, dict):
            entry['rest_bases'] = {k: v.get('rest_base') for k, v in body.items() if isinstance(v, dict) and any(x in k.lower() for x in ('menu', 'navigation', 'nav'))}
            entry['type_keys'] = sorted(body.keys())
        else:
            entry['body'] = compact(body)
        result['routes'][name] = entry

    code, root = api('/')
    route_keys = sorted((root.get('routes') or {}).keys()) if code == 200 and isinstance(root, dict) else []
    result['routes']['index'] = {
        'http': code,
        'menu_navigation_routes': [r for r in route_keys if re.search(r'menu|navigation|nav_', r, re.I)][:100],
        'rankmath_routes': [r for r in route_keys if 'rankmath' in r.lower()][:100],
    }

    home = public(BASE + '/')
    body = home.get('body', '')
    result['frontend']['home_http'] = home.get('http')
    result['frontend']['final_url'] = home.get('url')
    for needle in ('page_id=1183', '/referans-isler/'):
        snippets = []
        for m in re.finditer(re.escape(needle), body, re.I):
            snippets.append(clean(body[max(0, m.start()-450):min(len(body), m.end()+450)])[:1200])
        result['frontend'][needle] = snippets[:10]

    for path in ('/page-sitemap.xml', '/sitemap_index.xml'):
        res = public(BASE + path, limit=500000)
        text = res.get('body', '')
        result['sitemap'][path] = {
            'http': res.get('http'), 'final_url': res.get('url'),
            'contains_referans_isler': '/referans-isler/' in text,
            'contains_page_1183': '1183' in text,
            'sample': clean(text)[:1800],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'status': result['status'],
        'pages': [{'id': p['id'], 'http': p['http'], 'status': p.get('status'), 'slug': p.get('slug'), 'headings': p.get('headings')} for p in result['pages']],
        'routes': {k: v.get('http') for k, v in result['routes'].items()},
        'frontend_hits': {k: len(v) for k, v in result['frontend'].items() if isinstance(v, list)},
        'sitemap': result['sitemap'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
