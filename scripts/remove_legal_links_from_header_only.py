#!/usr/bin/env python3
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamHeaderFix/1.0)'
LEGAL_PATHS = {'/gizlilik-politikasi/', '/kullanim-sartlari/', '/kvkk/'}
OUT = '.ops/header-legal-links-only-2026-08-15.json'
BACKUP = '.ops/header-legal-links-backup-2026-08-15.json'


def norm_path(url):
    if not url:
        return ''
    p = urllib.parse.urlparse(urllib.parse.urljoin(BASE + '/', str(url))).path or '/'
    return p.rstrip('/') + '/'


def api(method, route, params=None, payload=None):
    q = {'rest_route': route}
    if params:
        q.update(params)
    url = BASE + '/?' + urllib.parse.urlencode(q)
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode('utf-8', errors='replace')
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw_sample': raw[:1200]}
        return e.code, body


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.cur = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            d = dict(attrs)
            self.cur = {'href': d.get('href', ''), 'text': ''}
    def handle_data(self, data):
        if self.cur is not None:
            self.cur['text'] += data
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.cur is not None:
            self.cur['text'] = ' '.join(self.cur['text'].split())
            self.links.append(self.cur)
            self.cur = None


def region(html, tag):
    m = re.search(rf'<{tag}\b[^>]*>.*?</{tag}>', html, re.I | re.S)
    return m.group(0) if m else ''


def public_html():
    url = BASE + '/?header_legal_check=' + str(int(time.time()))
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Cache-Control': 'no-cache, no-store, max-age=0',
        'Pragma': 'no-cache',
        'Accept': 'text/html,*/*',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', errors='replace')


def extract_legal(html, tag):
    parser = Links()
    parser.feed(region(html, tag))
    return [
        {'text': x['text'], 'href': x['href'], 'path': norm_path(x['href'])}
        for x in parser.links if norm_path(x['href']) in LEGAL_PATHS
    ]


def save(path, obj):
    os.makedirs('.ops', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    result = {'status': 'started', 'legal_paths': sorted(LEGAL_PATHS)}

    code, items = api('GET', '/wp/v2/menu-items', {'context': 'edit', 'per_page': '100'})
    if code != 200 or not isinstance(items, list):
        result['status'] = 'menu-read-failed'
        result['http'] = code
        result['body'] = items
        save(OUT, result)
        raise SystemExit(2)

    all_before = []
    legal_items = []
    for it in items:
        title = it.get('title', {})
        if isinstance(title, dict):
            title = title.get('raw') or title.get('rendered') or ''
        rec = {
            'id': it.get('id'), 'title': title, 'url': it.get('url', ''),
            'path': norm_path(it.get('url', '')), 'menus': it.get('menus'),
            'status': it.get('status')
        }
        all_before.append(rec)
        if rec['path'] in LEGAL_PATHS:
            legal_items.append(rec)

    save(BACKUP, {'all_menu_items_before': all_before, 'legal_menu_items_before': legal_items})
    result['legal_menu_items_before'] = legal_items

    # Delete only exact legal-page menu items. Do not touch pages, footer widgets, service links, or any other menu item.
    deleted = []
    for item in legal_items:
        code, body = api('DELETE', f"/wp/v2/menu-items/{item['id']}", {'force': 'true'})
        ok = code == 200 and isinstance(body, dict) and body.get('deleted') is True
        deleted.append({'id': item['id'], 'title': item['title'], 'path': item['path'], 'http': code, 'deleted': ok})
        if not ok:
            result['deleted'] = deleted
            result['status'] = 'menu-delete-failed'
            save(OUT, result)
            raise SystemExit(3)
    result['deleted'] = deleted

    code, after_items = api('GET', '/wp/v2/menu-items', {'context': 'edit', 'per_page': '100'})
    if code != 200 or not isinstance(after_items, list):
        result['status'] = 'menu-reread-failed'
        save(OUT, result)
        raise SystemExit(4)

    before_nonlegal_ids = sorted(x['id'] for x in all_before if x['path'] not in LEGAL_PATHS and x.get('id'))
    after_nonlegal_ids = sorted(it.get('id') for it in after_items if norm_path(it.get('url', '')) not in LEGAL_PATHS and it.get('id'))
    remaining_legal = [
        {'id': it.get('id'), 'url': it.get('url', ''), 'path': norm_path(it.get('url', ''))}
        for it in after_items if norm_path(it.get('url', '')) in LEGAL_PATHS
    ]
    result['remaining_legal_menu_items'] = remaining_legal
    result['nonlegal_menu_ids_unchanged'] = before_nonlegal_ids == after_nonlegal_ids

    # Legal pages themselves must remain published and reachable.
    page_states = []
    for path in sorted(LEGAL_PATHS):
        slug = path.strip('/')
        code, pages = api('GET', '/wp/v2/pages', {'context': 'edit', 'slug': slug, 'per_page': '10'})
        state = {'slug': slug, 'http': code, 'count': len(pages) if isinstance(pages, list) else None}
        if isinstance(pages, list) and pages:
            state['id'] = pages[0].get('id')
            state['status'] = pages[0].get('status')
        page_states.append(state)
    result['legal_pages'] = page_states

    time.sleep(3)
    html = public_html()
    header_legal = extract_legal(html, 'header')
    footer_legal = extract_legal(html, 'footer')
    result['live_header_legal_links'] = header_legal
    result['live_footer_legal_links'] = footer_legal

    pages_ok = all(x.get('http') == 200 and x.get('count', 0) >= 1 and x.get('status') == 'publish' for x in page_states)
    footer_paths = {x['path'] for x in footer_legal}
    ok = (
        not remaining_legal
        and result['nonlegal_menu_ids_unchanged']
        and pages_ok
        and len(header_legal) == 0
        and LEGAL_PATHS.issubset(footer_paths)
    )
    result['status'] = 'success' if ok else 'verification-failed'
    save(OUT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(5)


if __name__ == '__main__':
    main()
