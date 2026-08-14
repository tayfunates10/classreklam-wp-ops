#!/usr/bin/env python3
import base64, json, os, re, time, urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from pathlib import Path

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamHeaderRestore/1.0)'
OUT = Path('.ops/header-restore-2026-08-15.json')
BACKUP = Path('.ops/header-restore-backup-2026-08-15.json')

SERVICES = [
    ('Edremit Tabela', 1132, '/edremit-tabela/'),
    ('Totem Tabela', 1134, '/totem-tabela/'),
    ('Dijital Baskı', 1136, '/dijital-baski/'),
    ('Araç Giydirme', 1138, '/arac-giydirme/'),
    ('Cam Giydirme', 1140, '/cam-giydirme/'),
    ('Kutu Harf Tabela', 1142, '/kutu-harf-tabela/'),
]
TARGET_PATHS = {p for _, _, p in SERVICES}
OLD_FOOTER = '''<ul class="footer-link-list">
  <li><a href="/hizmetlerimiz">Tabela</a></li>
  <li><a href="/hizmetlerimiz">Totem</a></li>
  <li><a href="/hizmetlerimiz">Dijital Baskı</a></li>
  <li><a href="/hizmetlerimiz">Araç Giydirme</a></li>
  <li><a href="/hizmetlerimiz">Cam Giydirme</a></li>
  <li><a href="/hizmetlerimiz">Kutu Harf</a></li>
</ul>'''


def api(method, route, params=None, payload=None):
    q = {'rest_route': route}
    if params: q.update(params)
    url = BASE + '/?' + urllib.parse.urlencode(q, doseq=True)
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode('utf-8', errors='replace')
                try: body = json.loads(raw) if raw else {}
                except Exception: body = {'raw_sample': raw[:1200]}
                return r.status, body
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', errors='replace')
            try: body = json.loads(raw)
            except Exception: body = {'raw_sample': raw[:1200]}
            last = (e.code, body)
            if e.code == 403 and attempt < 3:
                time.sleep(8 * (attempt + 1)); continue
            return last
        except Exception as e:
            last = (0, {'error': f'{type(e).__name__}: {e}'})
            if attempt < 3:
                time.sleep(5 * (attempt + 1)); continue
            return last
    return last


def norm_path(url):
    if not url: return ''
    p = urllib.parse.urlparse(urllib.parse.urljoin(BASE + '/', str(url))).path or '/'
    return p.rstrip('/') + '/' if p != '/' else '/'


def title_of(item):
    t = item.get('title', '') if isinstance(item, dict) else ''
    if isinstance(t, dict): return t.get('raw') or t.get('rendered') or ''
    return str(t or '')


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.cur=None
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a': self.cur={'href': dict(attrs).get('href',''), 'text':''}
    def handle_data(self, data):
        if self.cur is not None: self.cur['text'] += data
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.cur is not None:
            self.cur['text'] = ' '.join(self.cur['text'].split()); self.links.append(self.cur); self.cur=None


def public_html():
    req = urllib.request.Request(BASE + '/?header-restore-check=' + str(int(time.time())), headers={
        'User-Agent': UA, 'Cache-Control': 'no-cache, no-store, max-age=0', 'Pragma': 'no-cache'
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8', errors='replace')


def region(raw, tag):
    m = re.search(rf'<{tag}\b[^>]*>.*?</{tag}>', raw, re.I | re.S)
    return m.group(0) if m else ''


def live_counts():
    raw = public_html()
    out = {}
    for tag in ('header', 'footer'):
        p = Links(); p.feed(region(raw, tag))
        hits = [{'text': x['text'], 'path': norm_path(x['href'])} for x in p.links if norm_path(x['href']) in TARGET_PATHS]
        out[tag + '_hits'] = hits
        out[tag + '_count'] = len(hits)
    return out


def main():
    result = {'status': 'preflight', 'changes': [], 'verification': {}}

    code, items = api('GET', '/wp/v2/menu-items', {'context':'edit', 'per_page':100, '_fields':'id,status,title,type,object,object_id,url,parent,menu_order,menus'})
    if code != 200 or not isinstance(items, list):
        raise RuntimeError(f'menu-items read failed: {code} {items}')

    base_items = [x for x in items if x.get('id') in (22,23,24,25,26,28)]
    if len(base_items) != 6:
        raise RuntimeError(f'base primary menu identity mismatch: {[x.get("id") for x in base_items]}')
    menu_ids = {int(x.get('menus')) for x in base_items if x.get('menus')}
    if len(menu_ids) != 1:
        raise RuntimeError(f'primary menu id ambiguous: {menu_ids}')
    primary_menu = next(iter(menu_ids))

    service_existing = [x for x in items if norm_path(x.get('url')) in TARGET_PATHS or title_of(x) in {n for n,_,_ in SERVICES}]

    code, widget = api('GET', '/wp/v2/widgets/block-61', {'context':'edit'})
    if code != 200 or not isinstance(widget, dict):
        raise RuntimeError(f'block-61 read failed: {code} {widget}')
    inst = widget.get('instance') or {}
    raw = inst.get('raw') if isinstance(inst, dict) else None
    raw_mode = None
    if isinstance(raw, dict) and isinstance(raw.get('content'), str):
        footer_content = raw['content']; raw_mode='dict-content'
    elif isinstance(raw, str):
        footer_content = raw; raw_mode='string'
    else:
        raise RuntimeError(f'unsupported block-61 format: {type(raw).__name__}')

    backup = {
        'primary_menu': primary_menu,
        'menu_items': items,
        'block_61': widget,
        'live_before': live_counts(),
    }
    save(BACKUP, backup)

    # Restore the six service items to the primary menu if absent.
    by_path = {norm_path(x.get('url')): x for x in service_existing}
    max_order = max([int(x.get('menu_order') or 0) for x in base_items + service_existing] or [0])
    for idx, (name, page_id, path) in enumerate(SERVICES, start=1):
        if path in by_path:
            result['changes'].append({'header': name, 'status': 'already-present', 'id': by_path[path].get('id')})
            continue
        payload = {
            'status': 'publish',
            'title': name,
            'type': 'post_type',
            'object': 'page',
            'object_id': page_id,
            'menus': primary_menu,
            'parent': 0,
            'menu_order': max_order + idx,
        }
        c, b = api('POST', '/wp/v2/menu-items', payload=payload)
        if c not in (200, 201) or not isinstance(b, dict) or not b.get('id'):
            raise RuntimeError(f'create header item {name} failed: {c} {b}')
        result['changes'].append({'header': name, 'status': 'created', 'id': b.get('id')})

    # Restore the exact pre-move footer list: six generic links to /hizmetlerimiz.
    pattern = r'<ul\b[^>]*class=["\'][^"\']*footer-link-list[^"\']*["\'][^>]*>.*?</ul>'
    if not re.search(pattern, footer_content, re.I | re.S):
        raise RuntimeError('footer-link-list not found in block-61')
    new_footer = re.sub(pattern, OLD_FOOTER, footer_content, count=1, flags=re.I | re.S)
    if new_footer != footer_content:
        new_raw = dict(raw) if raw_mode == 'dict-content' else new_footer
        if raw_mode == 'dict-content': new_raw['content'] = new_footer
        c, b = api('POST', '/wp/v2/widgets/block-61', payload={'instance': {'raw': new_raw}})
        if c != 200:
            raise RuntimeError(f'footer restore failed: {c} {b}')
        result['changes'].append({'footer': 'block-61', 'status': 'restored-old-generic-list'})
    else:
        result['changes'].append({'footer': 'block-61', 'status': 'already-old'})

    # Authoritative REST verification.
    c, after_items = api('GET', '/wp/v2/menu-items', {'context':'edit', 'per_page':100, '_fields':'id,status,title,url,menus'})
    if c != 200 or not isinstance(after_items, list):
        raise RuntimeError(f'after menu read failed: {c}')
    restored = [x for x in after_items if norm_path(x.get('url')) in TARGET_PATHS and int(x.get('menus') or 0) == primary_menu]
    c, after_widget = api('GET', '/wp/v2/widgets/block-61', {'context':'edit'})
    if c != 200 or not isinstance(after_widget, dict):
        raise RuntimeError(f'after widget read failed: {c}')
    rendered = after_widget.get('rendered') or ''
    footer_dedicated = sorted({norm_path(h) for h in re.findall(r'href=["\']([^"\']+)["\']', rendered) if norm_path(h) in TARGET_PATHS})
    result['verification']['authoritative_header_service_count'] = len(restored)
    result['verification']['authoritative_footer_dedicated_paths'] = footer_dedicated

    time.sleep(4)
    live = live_counts()
    result['verification']['live'] = live
    ok = len(restored) == 6 and not footer_dedicated and live.get('header_count') == 6 and live.get('footer_count') == 0
    result['status'] = 'success' if ok else 'verification-failed'
    save(OUT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
