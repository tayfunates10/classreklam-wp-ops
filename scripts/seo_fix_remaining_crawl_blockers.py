#!/usr/bin/env python3
import base64
import copy
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
OUT = Path('.ops/seo-crawl-blocker-remediation-2026-08-14.json')
BACKUP = Path('.ops/seo-crawl-blocker-backup-2026-08-14.json')
MARKER = 'cr-seo-legal-bridge-v1'

PAGE_IDS = (6, 8, 10, 12, 14, 683, 1183, 1186)
PRIVACY_TITLE = 'Gizlilik Politikası'
PRIVACY_DESCRIPTION = 'Class Reklam web sitesi gizlilik ve kişisel verilerle ilgili genel bilgilendirme bağlantıları.'


def api_url(route, params=None):
    q = {'rest_route': route}
    if params:
        q.update(params)
    return BASE + '/?' + urllib.parse.urlencode(q, doseq=True, safe='/:,')


def api_once(method, route, params=None, payload=None):
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
    req = urllib.request.Request(api_url(route, params), data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=70) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {'raw_sample': raw[:1800]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw_sample': raw[:1800]}
        return e.code, body
    except Exception as e:
        return 0, {'error': f'{type(e).__name__}: {e}'}


def api(method, route, params=None, payload=None, retries=5):
    last = None
    for attempt in range(retries):
        time.sleep(1.8)
        code, body = api_once(method, route, params=params, payload=payload)
        last = (code, body)
        text = json.dumps(body, ensure_ascii=False).lower() if isinstance(body, (dict, list)) else str(body).lower()
        retryable = code == 0 or (code == 403 and ('imunify360' in text or 'bot-protection' in text))
        if not retryable:
            return code, body
        time.sleep(8 * (attempt + 1))
    return last


def ensure(code, body, label):
    if code not in (200, 201):
        raise RuntimeError(f'{label}: HTTP {code} {body}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NOREDIRECT = urllib.request.build_opener(NoRedirect)


def public(url, no_redirect=False, limit=900000, cache_bust=False):
    if cache_bust:
        p = urllib.parse.urlsplit(url)
        qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        qs.append(('crseo', str(int(time.time() * 1000))))
        url = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(qs), p.fragment))
    opener = NOREDIRECT if no_redirect else urllib.request.build_opener()
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xml,text/xml;q=0.9,*/*;q=0.5',
        'Cache-Control': 'no-cache, no-store, max-age=0',
        'Pragma': 'no-cache',
    })
    try:
        with opener.open(req, timeout=70) as r:
            body = r.read(limit).decode('utf-8', errors='replace')
            return {
                'http': r.status,
                'final_url': r.geturl(),
                'location': r.headers.get('Location', ''),
                'content_type': r.headers.get('Content-Type', ''),
                'server': r.headers.get('Server', ''),
                'cache_control': r.headers.get('Cache-Control', ''),
                'waf': is_waf(body),
                'body': body,
            }
    except urllib.error.HTTPError as e:
        body = e.read(limit).decode('utf-8', errors='replace')
        return {
            'http': e.code,
            'final_url': e.geturl(),
            'location': e.headers.get('Location', ''),
            'content_type': e.headers.get('Content-Type', ''),
            'server': e.headers.get('Server', ''),
            'cache_control': e.headers.get('Cache-Control', ''),
            'waf': is_waf(body),
            'body': body,
        }
    except Exception as e:
        return {'http': 0, 'final_url': url, 'location': '', 'waf': False, 'body': '', 'error': f'{type(e).__name__}: {e}'}


def is_waf(body):
    low = (body or '').lower()
    return 'one moment, please' in low or 'imunify360' in low


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(str(value or ''))).strip()


def first_tag(raw, tag, attr=None):
    if attr:
        pattern = rf'<{tag}\b[^>]*{attr}[^>]*>(.*?)</{tag}>'
    else:
        pattern = rf'<{tag}\b[^>]*>(.*?)</{tag}>'
    m = re.search(pattern, raw or '', re.I | re.S)
    return clean(re.sub(r'<[^>]+>', ' ', m.group(1))) if m else ''


def html_h1s(raw):
    return [clean(re.sub(r'<[^>]+>', ' ', x)) for x in re.findall(r'<h1\b[^>]*>(.*?)</h1>', raw or '', re.I | re.S)]


def canonical(raw):
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw or '', re.I)
    if not m:
        m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', raw or '', re.I)
    return html.unescape(m.group(1)).strip() if m else ''


def robots(raw):
    m = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)', raw or '', re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']robots["\']', raw or '', re.I)
    return html.unescape(m.group(1)).strip() if m else ''


def page_read(pid):
    code, body = api('GET', f'/wp/v2/pages/{pid}', params={
        'context': 'edit',
        '_fields': 'id,slug,status,link,title,content,excerpt,modified,template,meta'
    })
    ensure(code, body, f'get page {pid}')
    if not isinstance(body, dict) or int(body.get('id') or 0) != pid:
        raise RuntimeError(f'page {pid}: identity mismatch')
    return body


def page_raw(page):
    return str((page.get('content') or {}).get('raw') or '')


def page_update(pid, payload, label):
    code, body = api('POST', f'/wp/v2/pages/{pid}', payload=payload)
    ensure(code, body, label)
    return body


def rank_meta(pid, meta, label):
    code, body = api('POST', '/rankmath/v1/updateMeta', payload={
        'objectType': 'post',
        'objectID': int(pid),
        'meta': meta,
    })
    ensure(code, body, label)
    return body


def menu_items():
    code, body = api('GET', '/wp/v2/menu-items', params={'context': 'edit', 'per_page': 100})
    ensure(code, body, 'read menu items')
    if not isinstance(body, list):
        raise RuntimeError('menu-items response is not a list')
    return body


def title_value(item):
    t = item.get('title') or ''
    if isinstance(t, dict):
        return str(t.get('raw') or t.get('rendered') or '')
    return str(t)


def menu_backup(item):
    keep = ['id', 'status', 'url', 'type', 'object', 'object_id', 'parent', 'attr_title', 'description', 'classes', 'xfn', 'target', 'menus', 'menu_order']
    out = {k: copy.deepcopy(item.get(k)) for k in keep if k in item}
    out['title'] = title_value(item)
    return out


def norm_path(url):
    try:
        p = urllib.parse.urlsplit(str(url or ''))
        path = p.path or '/'
        return path.rstrip('/') + '/', urllib.parse.parse_qs(p.query)
    except Exception:
        return '', {}


def delete_menu_item(item_id):
    code, body = api('DELETE', f'/wp/v2/menu-items/{item_id}', params={'force': 'true'})
    ensure(code, body, f'delete menu item {item_id}')
    if not isinstance(body, dict) or not body.get('deleted'):
        raise RuntimeError(f'menu item {item_id}: force delete not confirmed: {body}')


def create_menu_item(saved):
    payload = {
        'status': 'publish',
        'title': saved.get('title') or '',
        'type': saved.get('type') or 'custom',
        'parent': int(saved.get('parent') or 0),
        'attr_title': saved.get('attr_title') or '',
        'description': saved.get('description') or '',
        'classes': saved.get('classes') or [],
        'xfn': saved.get('xfn') or [],
        'target': saved.get('target') or '',
        'menus': int(saved.get('menus') or 0),
        'menu_order': int(saved.get('menu_order') or 0),
    }
    if payload['type'] == 'custom':
        payload['url'] = saved.get('url') or BASE + '/'
    else:
        payload['object'] = saved.get('object') or 'page'
        payload['object_id'] = int(saved.get('object_id') or 0)
    code, body = api('POST', '/wp/v2/menu-items', payload=payload)
    ensure(code, body, f"restore menu item {saved.get('id')}")
    return body


def plugin_route(plugin_file):
    p = plugin_file[:-4] if plugin_file.endswith('.php') else plugin_file
    return '/wp/v2/plugins/' + p


def promote_heading(raw, section_selector, old_text, page_label):
    h2_pattern = re.compile(rf'<h2(\b[^>]*)>\s*{re.escape(old_text)}\s*</h2>', re.I | re.S)
    matches = list(h2_pattern.finditer(raw))
    if re.search(r'<h1\b', raw, re.I):
        return raw, 'already-has-h1'
    if len(matches) != 1:
        raise RuntimeError(f'{page_label}: expected exactly one H2 {old_text!r}, found {len(matches)}')
    updated = h2_pattern.sub(lambda m: f'<h1{m.group(1)}>{old_text}</h1>', raw, count=1)
    old_selector = section_selector + ' h2'
    new_selector = section_selector + ' h1'
    if old_selector not in updated:
        raise RuntimeError(f'{page_label}: CSS selector {old_selector!r} not found')
    updated = updated.replace(old_selector, new_selector)
    return updated, 'promoted-h2-to-h1'


def verify_public_page(path, expected_h1=None, expected_canonical=None, noindex=None):
    res = public(BASE + path, cache_bust=True)
    body = res.get('body', '')
    info = {
        'http': res.get('http'), 'waf': res.get('waf'), 'final_url': res.get('final_url'),
        'h1': html_h1s(body), 'canonical': canonical(body), 'robots': robots(body),
    }
    if res.get('http') != 200 or res.get('waf'):
        raise RuntimeError(f'{path}: public HTTP/WAF verification failed: {info}')
    if expected_h1 is not None and info['h1'] != [expected_h1]:
        raise RuntimeError(f'{path}: expected one H1 {expected_h1!r}, got {info["h1"]}')
    if expected_canonical is not None and info['canonical'] != expected_canonical:
        raise RuntimeError(f'{path}: canonical expected {expected_canonical}, got {info["canonical"]}')
    if noindex is True and 'noindex' not in info['robots'].lower():
        raise RuntimeError(f'{path}: expected noindex, got {info["robots"]}')
    return info


def verify_unavailable(path):
    res = public(BASE + path, no_redirect=True, cache_bust=True)
    info = {'http': res.get('http'), 'location': res.get('location'), 'waf': res.get('waf')}
    if res.get('waf') or res.get('http') not in (404, 410):
        raise RuntimeError(f'{path}: expected 404/410, got {info}')
    return info


def restore_page(page):
    pid = int(page['id'])
    payload = {
        'status': page.get('status') or 'draft',
        'slug': page.get('slug') or '',
        'title': (page.get('title') or {}).get('raw') or '',
        'content': page_raw(page),
        'excerpt': (page.get('excerpt') or {}).get('raw') or '',
    }
    return api('POST', f'/wp/v2/pages/{pid}', payload=payload)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = {'status': 'preflight', 'changes': [], 'verification': {}, 'rollback': [], 'cache': []}
    backups = {'pages': {}, 'menu_items_deleted': [], 'blog_canonical': BASE + '/blog/'}
    plugin_file = None
    plugin_created = False
    plugin_initial = None

    try:
        pages = {pid: page_read(pid) for pid in PAGE_IDS}
        backups['pages'] = pages

        # Identity and safety predicates.
        expected = {
            6: ('ana-sayfa', 'publish'), 8: ('hakkimizda', 'publish'), 10: ('hizmetlerimiz', 'publish'),
            12: ('galeri', 'publish'), 14: ('blog', 'publish'), 683: ('referans-isler', 'draft'),
            1183: ('gizlilik-politikasi', 'draft'), 1186: ('gizlilik-politikasi-2', 'publish'),
        }
        for pid, (slug, status) in expected.items():
            p = pages[pid]
            if p.get('slug') != slug or p.get('status') != status:
                raise RuntimeError(f'page {pid}: expected slug/status {slug}/{status}, got {p.get("slug")}/{p.get("status")}')
        if MARKER not in page_raw(pages[1183]) or MARKER not in page_raw(pages[1186]):
            raise RuntimeError('privacy pages do not match known safe bridge marker')

        menus = menu_items()
        stale_privacy = []
        duplicate_privacy = []
        stale_reference = []
        for item in menus:
            iid = int(item.get('id') or 0)
            oid = int(item.get('object_id') or 0)
            path, qs = norm_path(item.get('url', ''))
            if oid == 1183 or ('page_id' in qs and '1183' in qs.get('page_id', [])):
                stale_privacy.append(item)
            if oid == 1186 or path == '/gizlilik-politikasi-2/':
                duplicate_privacy.append(item)
            if oid == 683 or path == '/referans-isler/':
                stale_reference.append(item)
        if len(stale_privacy) != 1:
            raise RuntimeError(f'expected exactly one menu item for privacy page 1183, found {[x.get("id") for x in stale_privacy]}')
        if len(duplicate_privacy) > 1:
            raise RuntimeError(f'unexpected multiple menu items for duplicate privacy page: {[x.get("id") for x in duplicate_privacy]}')
        if len(stale_reference) > 1:
            raise RuntimeError(f'unexpected multiple legacy reference menu items: {[x.get("id") for x in stale_reference]}')

        BACKUP.write_text(json.dumps({
            'pages': pages,
            'menu_items': [menu_backup(x) for x in stale_privacy + duplicate_privacy + stale_reference],
            'blog_canonical_assumed_before': BASE + '/blog/',
        }, ensure_ascii=False, indent=2), encoding='utf-8')

        # 1) Fix the privacy slug/menu collision without touching legal copy.
        page_update(1186, {'status': 'draft'}, 'draft duplicate privacy page 1186')
        result['changes'].append({'page': 1186, 'status': 'draft'})
        page_update(1183, {
            'status': 'publish', 'slug': 'gizlilik-politikasi',
            'title': PRIVACY_TITLE, 'content': page_raw(pages[1183])
        }, 'publish canonical privacy page 1183')
        rank_meta(1183, {
            'rank_math_title': 'Gizlilik Politikası | Class Reklam',
            'rank_math_description': PRIVACY_DESCRIPTION,
            'rank_math_canonical_url': BASE + '/gizlilik-politikasi/',
            'rank_math_robots': ['noindex', 'follow'],
        }, 'privacy Rank Math meta')
        result['changes'].append({'page': 1183, 'status': 'publish', 'slug': 'gizlilik-politikasi'})

        # Duplicate menu item created for page 1186 is no longer needed; the original 1184 now resolves correctly.
        for item in duplicate_privacy:
            saved = menu_backup(item)
            delete_menu_item(int(item['id']))
            backups['menu_items_deleted'].append(saved)
            result['changes'].append({'menu_item_deleted': int(item['id']), 'reason': 'duplicate privacy'})

        # 2) Replace stale legacy reference links in authoritative homepage content.
        home_raw = page_raw(pages[6])
        old_abs = BASE + '/referans-isler/'
        count_abs = home_raw.count(old_abs)
        count_rel = home_raw.count('href="/referans-isler/"') + home_raw.count("href='/referans-isler/'")
        if count_abs + count_rel == 0:
            raise RuntimeError('homepage contains no expected /referans-isler/ links to replace')
        new_home = home_raw.replace(old_abs, BASE + '/referanslar/')
        new_home = new_home.replace('href="/referans-isler/"', 'href="/referanslar/"').replace("href='/referans-isler/'", "href='/referanslar/'")
        page_update(6, {'content': new_home}, 'replace homepage legacy reference links')
        result['changes'].append({'page': 6, 'legacy_reference_links_replaced': count_abs + count_rel})

        # If a separate menu item targets page 683, convert it to a custom archive link in place.
        for item in stale_reference:
            payload = {
                'status': 'publish', 'title': 'Referanslar', 'type': 'custom', 'url': BASE + '/referanslar/',
                'parent': int(item.get('parent') or 0), 'menus': int(item.get('menus') or 0),
                'menu_order': int(item.get('menu_order') or 0), 'attr_title': item.get('attr_title') or '',
                'description': item.get('description') or '', 'classes': item.get('classes') or [],
                'xfn': item.get('xfn') or [], 'target': item.get('target') or '',
            }
            code, body = api('POST', f"/wp/v2/menu-items/{int(item['id'])}", payload=payload)
            ensure(code, body, f"update legacy reference menu item {item['id']}")
            result['changes'].append({'menu_item_updated': int(item['id']), 'url': BASE + '/referanslar/'})

        # 3) Preserve design while promoting exact section title selectors/elements to H1.
        about_raw, about_action = promote_heading(page_raw(pages[8]), '.cr-about-head', 'Hakkımızda', 'Hakkımızda')
        if about_action != 'already-has-h1':
            page_update(8, {'content': about_raw}, 'promote Hakkımızda H1')
        result['changes'].append({'page': 8, 'h1': about_action})

        services_raw, services_action = promote_heading(page_raw(pages[10]), '.cr-services-v2-head', 'Hizmetlerimiz', 'Hizmetlerimiz')
        if services_action != 'already-has-h1':
            page_update(10, {'content': services_raw}, 'promote Hizmetlerimiz H1')
        result['changes'].append({'page': 10, 'h1': services_action})

        gallery_raw = page_raw(pages[12])
        if re.search(r'<h1\b', gallery_raw, re.I):
            gallery_action = 'already-has-h1'
        else:
            if '[cr_gallery]' not in gallery_raw:
                raise RuntimeError('Galeri page no longer contains expected [cr_gallery] shortcode')
            gallery_block = '<!-- wp:heading {"level":1,"textAlign":"center","className":"cr-gallery-page-title"} -->\n<h1 class="wp-block-heading has-text-align-center cr-gallery-page-title">Galeri</h1>\n<!-- /wp:heading -->\n'
            page_update(12, {'content': gallery_block + gallery_raw}, 'add Galeri H1')
            gallery_action = 'h1-added'
        result['changes'].append({'page': 12, 'h1': gallery_action})

        # 4) Remove the hard-coded blog canonical so Rank Math can emit paginated self canonicals.
        rank_meta(14, {'rank_math_canonical_url': ''}, 'clear blog hard-coded canonical')
        result['changes'].append({'page': 14, 'rank_math_canonical_url': ''})

        # 5) Purge server/Rank Math sitemap cache through the repository's proven LiteSpeed save hook.
        code, plugins = api('GET', '/wp/v2/plugins', params={'context': 'edit'})
        ensure(code, plugins, 'read plugins for cache purge')
        if not isinstance(plugins, list):
            raise RuntimeError('plugins response is not a list')
        ls = [p for p in plugins if str(p.get('plugin', '')).startswith('litespeed-cache/') or 'LiteSpeed Cache' in str(p.get('name', ''))]
        if ls:
            plugin_file = ls[0].get('plugin')
            plugin_initial = ls[0].get('status', 'inactive')
            if plugin_initial != 'active':
                code, body = api('POST', plugin_route(plugin_file), payload={'status': 'active'})
                ensure(code, body, 'activate existing LiteSpeed Cache')
                result['cache'].append({'litespeed': 'activated-existing', 'plugin': plugin_file})
            else:
                result['cache'].append({'litespeed': 'already-active', 'plugin': plugin_file})
        else:
            code, body = api('POST', '/wp/v2/plugins', payload={'slug': 'litespeed-cache', 'status': 'active'})
            ensure(code, body, 'temporarily install LiteSpeed Cache')
            plugin_file = body.get('plugin') if isinstance(body, dict) else None
            if not plugin_file:
                raise RuntimeError('temporary LiteSpeed install returned no plugin id')
            plugin_created = True
            plugin_initial = 'absent'
            result['cache'].append({'litespeed': 'temporarily-installed', 'plugin': plugin_file})

        # Re-save relevant post states/content to trigger native sitemap/cache invalidation hooks.
        page_update(683, {'status': 'draft'}, 'resave retired reference page for sitemap invalidation')
        p1183 = page_read(1183)
        page_update(1183, {'content': page_raw(p1183), 'status': 'publish'}, 'resave privacy page for cache invalidation')
        p6 = page_read(6)
        page_update(6, {'content': page_raw(p6)}, 'resave homepage for cache invalidation')
        time.sleep(5)

        # 6) Public verification while cache hooks are active.
        result['verification']['privacy'] = verify_public_page('/gizlilik-politikasi/', expected_canonical=None, noindex=True)
        result['verification']['privacy_duplicate'] = verify_unavailable('/gizlilik-politikasi-2/')
        result['verification']['legacy_reference'] = verify_unavailable('/referans-isler/')
        result['verification']['about'] = verify_public_page('/hakkimizda/', expected_h1='Hakkımızda', expected_canonical=BASE + '/hakkimizda/')
        result['verification']['services'] = verify_public_page('/hizmetlerimiz/', expected_h1='Hizmetlerimiz', expected_canonical=BASE + '/hizmetlerimiz/')
        result['verification']['gallery'] = verify_public_page('/galeri/', expected_h1='Galeri', expected_canonical=BASE + '/galeri/')
        result['verification']['blog'] = verify_public_page('/blog/', expected_canonical=BASE + '/blog/')
        result['verification']['blog_page_2'] = verify_public_page('/blog/page/2/', expected_canonical=BASE + '/blog/page/2/')

        home = public(BASE + '/', cache_bust=True)
        home_body = home.get('body', '')
        result['verification']['home_links'] = {
            'http': home.get('http'), 'waf': home.get('waf'),
            'page_id_1183_count': home_body.count('page_id=1183'),
            'privacy_minus_2_count': home_body.count('/gizlilik-politikasi-2/'),
            'legacy_reference_count': home_body.count('/referans-isler/'),
            'archive_reference_count': home_body.count('/referanslar/'),
        }
        hv = result['verification']['home_links']
        if hv['http'] != 200 or hv['waf'] or hv['page_id_1183_count'] or hv['privacy_minus_2_count'] or hv['legacy_reference_count'] or hv['archive_reference_count'] == 0:
            raise RuntimeError(f'homepage stale/broken links remain: {hv}')

        sitemap = None
        for _ in range(6):
            time.sleep(4)
            sitemap = public(BASE + '/page-sitemap.xml', cache_bust=True, limit=600000)
            sb = sitemap.get('body', '')
            if sitemap.get('http') == 200 and not sitemap.get('waf') and '/referans-isler/' not in sb and '/gizlilik-politikasi-2/' not in sb and '/gizlilik-politikasi/' not in sb:
                break
        result['verification']['page_sitemap_cache_bust'] = {
            'http': sitemap.get('http') if sitemap else 0,
            'waf': sitemap.get('waf') if sitemap else False,
            'legacy_reference': '/referans-isler/' in (sitemap.get('body', '') if sitemap else ''),
            'privacy_minus_2': '/gizlilik-politikasi-2/' in (sitemap.get('body', '') if sitemap else ''),
            'privacy_noindex': '/gizlilik-politikasi/' in (sitemap.get('body', '') if sitemap else ''),
        }
        sv = result['verification']['page_sitemap_cache_bust']
        if sv['http'] != 200 or sv['waf'] or sv['legacy_reference'] or sv['privacy_minus_2'] or sv['privacy_noindex']:
            raise RuntimeError(f'cache-busted page sitemap still stale/dirty: {sv}')

        result['status'] = 'success'

    except Exception as exc:
        result['status'] = 'failed-rollback-attempted'
        result['error'] = f'{type(exc).__name__}: {exc}'
        # Restore protected page states/content first.
        for pid in reversed(PAGE_IDS):
            page = backups.get('pages', {}).get(pid)
            if not page:
                continue
            try:
                code, body = restore_page(page)
                result['rollback'].append({'page': pid, 'http': code, 'ok': code in (200, 201)})
            except Exception as rb_exc:
                result['rollback'].append({'page': pid, 'ok': False, 'error': f'{type(rb_exc).__name__}: {rb_exc}'})
        # Restore blog canonical known before this change.
        try:
            code, body = api('POST', '/rankmath/v1/updateMeta', payload={
                'objectType': 'post', 'objectID': 14,
                'meta': {'rank_math_canonical_url': backups.get('blog_canonical', BASE + '/blog/')}
            })
            result['rollback'].append({'blog_canonical': 'restored', 'http': code, 'ok': code in (200, 201)})
        except Exception as rb_exc:
            result['rollback'].append({'blog_canonical': 'restore-failed', 'error': f'{type(rb_exc).__name__}: {rb_exc}'})
        # Restore menu items that were force-deleted.
        for saved in backups.get('menu_items_deleted', []):
            try:
                body = create_menu_item(saved)
                result['rollback'].append({'menu_item_recreated_for': saved.get('id'), 'new_id': body.get('id') if isinstance(body, dict) else None, 'ok': True})
            except Exception as rb_exc:
                result['rollback'].append({'menu_item_recreated_for': saved.get('id'), 'ok': False, 'error': f'{type(rb_exc).__name__}: {rb_exc}'})
        raise
    finally:
        # Always restore temporary cache plugin state.
        if plugin_file:
            try:
                if plugin_created:
                    api('POST', plugin_route(plugin_file), payload={'status': 'inactive'})
                    code, body = api('DELETE', plugin_route(plugin_file), params={'force': 'true'})
                    result['cache'].append({'litespeed_cleanup': 'deleted-temporary', 'http': code, 'deleted': body.get('deleted') if isinstance(body, dict) else None})
                elif plugin_initial != 'active':
                    code, body = api('POST', plugin_route(plugin_file), payload={'status': 'inactive'})
                    result['cache'].append({'litespeed_restore': 'inactive', 'http': code})
                else:
                    result['cache'].append({'litespeed_restore': 'left-active-as-found'})
            except Exception as cache_exc:
                result['cache'].append({'litespeed_restore_error': f'{type(cache_exc).__name__}: {cache_exc}'})

        # Verify plain sitemap after cache plugin restoration. This can turn a nominal success into failure.
        if result.get('status') == 'success':
            try:
                time.sleep(3)
                sm = public(BASE + '/page-sitemap.xml', limit=600000)
                sb = sm.get('body', '')
                plain = {
                    'http': sm.get('http'), 'waf': sm.get('waf'),
                    'legacy_reference': '/referans-isler/' in sb,
                    'privacy_minus_2': '/gizlilik-politikasi-2/' in sb,
                    'privacy_noindex': '/gizlilik-politikasi/' in sb,
                }
                result['verification']['page_sitemap_plain'] = plain
                if plain['http'] != 200 or plain['waf'] or plain['legacy_reference'] or plain['privacy_minus_2'] or plain['privacy_noindex']:
                    result['status'] = 'failed-post-cache-verification'
                    result['error'] = f'plain sitemap verification failed after cache restore: {plain}'
            except Exception as final_exc:
                result['status'] = 'failed-post-cache-verification'
                result['error'] = f'{type(final_exc).__name__}: {final_exc}'

        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if not BACKUP.exists():
            BACKUP.write_text(json.dumps(backups, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get('status') != 'success':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
