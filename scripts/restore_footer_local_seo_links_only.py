#!/usr/bin/env python3
import base64, json, os, re, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamFooterLocalSEO/1.0)'
OUT = Path('.ops/footer-local-seo-links-restore-2026-08-15.json')
SERVICES = [
    ('Edremit Tabela', '/edremit-tabela/'),
    ('Totem Tabela', '/totem-tabela/'),
    ('Dijital Baskı', '/dijital-baski/'),
    ('Araç Giydirme', '/arac-giydirme/'),
    ('Cam Giydirme', '/cam-giydirme/'),
    ('Kutu Harf Tabela', '/kutu-harf-tabela/'),
]
TARGET_PATHS = {p for _, p in SERVICES}


def api(method, route, params=None, payload=None):
    q = {'rest_route': route}
    if params:
        q.update(params)
    url = BASE + '/?' + urllib.parse.urlencode(q, doseq=True)
    data = None
    headers = {
        'Authorization': AUTH,
        'Accept': 'application/json',
        'User-Agent': UA,
        'Referer': BASE + '/wp-admin/',
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode('utf-8', errors='replace')
                try:
                    body = json.loads(raw) if raw else {}
                except Exception:
                    body = {'raw_sample': raw[:1200]}
                return r.status, body
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw)
            except Exception:
                body = {'raw_sample': raw[:1200]}
            last = (e.code, body)
            if e.code == 403 and attempt < 3:
                time.sleep(8 * (attempt + 1))
                continue
            return last
        except Exception as e:
            last = (0, {'error': f'{type(e).__name__}: {e}'})
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            return last
    return last


def norm_path(url):
    if not url:
        return ''
    p = urllib.parse.urlparse(urllib.parse.urljoin(BASE + '/', str(url))).path or '/'
    return p.rstrip('/') + '/' if p != '/' else '/'


def title_of(item):
    t = item.get('title', '') if isinstance(item, dict) else ''
    if isinstance(t, dict):
        return t.get('raw') or t.get('rendered') or ''
    return str(t or '')


def save(obj):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.cur = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            self.cur = {'href': dict(attrs).get('href', ''), 'text': ''}
    def handle_data(self, data):
        if self.cur is not None:
            self.cur['text'] += data
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.cur is not None:
            self.cur['text'] = ' '.join(self.cur['text'].split())
            self.links.append(self.cur)
            self.cur = None


def region(raw, tag):
    m = re.search(rf'<{tag}\b[^>]*>.*?</{tag}>', raw, re.I | re.S)
    return m.group(0) if m else ''


def live_state():
    url = BASE + '/?footer-local-seo-check=' + str(int(time.time()))
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Cache-Control': 'no-cache, no-store, max-age=0',
        'Pragma': 'no-cache',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode('utf-8', errors='replace')
    result = {}
    for tag in ('header', 'footer'):
        parser = Links()
        parser.feed(region(raw, tag))
        hits = [
            {'text': x['text'], 'path': norm_path(x['href'])}
            for x in parser.links if norm_path(x['href']) in TARGET_PATHS
        ]
        result[tag + '_hits'] = hits
        result[tag + '_count'] = len(hits)
        result[tag + '_paths'] = sorted({x['path'] for x in hits})
    return result


def main():
    result = {'status': 'preflight', 'changes': [], 'verification': {}}

    code, items = api('GET', '/wp/v2/menu-items', {
        'context': 'edit', 'per_page': 100, '_fields': 'id,status,title,url,menus'
    })
    if code != 200 or not isinstance(items, list):
        raise RuntimeError(f'menu read failed: {code} {items}')

    header_service_items = [
        {'id': x.get('id'), 'title': title_of(x), 'path': norm_path(x.get('url')), 'menus': x.get('menus')}
        for x in items if norm_path(x.get('url')) in TARGET_PATHS
    ]
    if header_service_items:
        raise RuntimeError(f'header service links must remain absent; found: {header_service_items}')

    code, widget = api('GET', '/wp/v2/widgets/block-61', {'context': 'edit'})
    if code != 200 or not isinstance(widget, dict):
        raise RuntimeError(f'block-61 read failed: {code} {widget}')
    inst = widget.get('instance') or {}
    raw = inst.get('raw') if isinstance(inst, dict) else None
    if isinstance(raw, dict) and isinstance(raw.get('content'), str):
        content = raw['content']
        raw_mode = 'dict'
    elif isinstance(raw, str):
        content = raw
        raw_mode = 'string'
    else:
        raise RuntimeError(f'unsupported block-61 raw format: {type(raw).__name__}')

    lis = '\n'.join(f'<li><a href="{path}">{name}</a></li>' for name, path in SERVICES)
    desired = f'<ul class="footer-link-list">\n{lis}\n</ul>'
    pattern = r'<ul\b[^>]*class=["\'][^"\']*footer-link-list[^"\']*["\'][^>]*>.*?</ul>'
    if not re.search(pattern, content, re.I | re.S):
        raise RuntimeError('footer-link-list not found in block-61')
    new_content = re.sub(pattern, desired, content, count=1, flags=re.I | re.S)

    if new_content != content:
        if raw_mode == 'dict':
            new_raw = dict(raw)
            new_raw['content'] = new_content
        else:
            new_raw = new_content
        code, body = api('POST', '/wp/v2/widgets/block-61', payload={'instance': {'raw': new_raw}})
        if code != 200:
            raise RuntimeError(f'footer update failed: {code} {body}')
        result['changes'].append({'widget': 'block-61', 'status': 'updated', 'links': SERVICES})
    else:
        result['changes'].append({'widget': 'block-61', 'status': 'already-correct'})

    code, after_widget = api('GET', '/wp/v2/widgets/block-61', {'context': 'edit'})
    if code != 200 or not isinstance(after_widget, dict):
        raise RuntimeError(f'block-61 verify read failed: {code}')
    rendered = after_widget.get('rendered') or ''
    authoritative_paths = sorted({
        norm_path(href)
        for href in re.findall(r'href=["\']([^"\']+)["\']', rendered)
        if norm_path(href) in TARGET_PATHS
    })
    result['verification']['authoritative_footer_paths'] = authoritative_paths
    if set(authoritative_paths) != TARGET_PATHS:
        result['status'] = 'authoritative-verification-failed'
        save(result)
        raise SystemExit(2)

    time.sleep(5)
    live = live_state()
    result['verification']['live'] = live
    ok = (
        live.get('header_count') == 0
        and live.get('footer_count') == 6
        and set(live.get('footer_paths') or []) == TARGET_PATHS
    )
    result['status'] = 'success' if ok else 'live-verification-failed'
    save(result)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if not ok:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
