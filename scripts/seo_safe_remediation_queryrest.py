#!/usr/bin/env python3
import base64
import datetime as dt
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
AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
EVIDENCE_DIR = Path(os.environ.get('SEO_EVIDENCE_DIR', '.ops'))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

META_TARGETS = {
    6: ('ana-sayfa', '/', 'Edremit Reklam ve Tabela Firması | Class Reklam',
        'Edremit’te tabela, totem, kutu harf, dijital baskı, araç ve cam giydirme çözümleri. Class Reklam’dan keşif ve teklif alın.'),
    10: ('hizmetlerimiz', '/hizmetlerimiz/', 'Edremit Tabela ve Reklam Hizmetleri | Class Reklam',
         'Edremit tabela, totem, kutu harf, dijital baskı, araç giydirme ve cam folyo hizmetlerini inceleyin. Class Reklam’dan teklif alın.'),
    18: ('iletisim', '/iletisim/', 'Class Reklam İletişim | Edremit Tabela ve Reklam',
         'Edremit’te tabela, reklam, dijital baskı, araç giydirme ve folyo uygulamaları için Class Reklam’a ulaşın. Telefon: 0546 936 42 71.'),
    1132: ('edremit-tabela', '/edremit-tabela/', 'Edremit Tabela | Işıklı ve Işıksız Tabela | Class Reklam',
           'Edremit tabela çözümleri: ışıklı ve ışıksız tabela, cephe tabelası, yönlendirme ve özel üretim. Class Reklam’dan keşif ve teklif alın.'),
    1134: ('totem-tabela', '/totem-tabela/', 'Edremit Totem Tabela | Yol Kenarı Totem | Class Reklam',
           'Edremit totem tabela üretimi ve uygulaması. Yol kenarı, işletme girişi ve geniş alanlarda görünürlüğü artıran kurumsal totem çözümleri.'),
    1136: ('dijital-baski', '/dijital-baski/', 'Edremit Dijital Baskı | Vinil, Branda ve Folyo | Class Reklam',
           'Edremit dijital baskı hizmetleri: vinil, branda, folyo ve dış mekân baskı uygulamaları. Ölçünüze ve kullanım alanınıza uygun üretim.'),
    1138: ('arac-giydirme', '/arac-giydirme/', 'Edremit Araç Giydirme ve Araç Kaplama | Class Reklam',
           'Edremit araç giydirme ve araç kaplama hizmeti. Ticari araçlar için kurumsal folyo, baskılı grafik ve mobil reklam uygulamaları.'),
    1140: ('cam-giydirme', '/cam-giydirme/', 'Edremit Cam Giydirme ve Cam Folyo | Class Reklam',
           'Edremit cam giydirme ve vitrin folyo uygulamaları. Mağaza ve ofis camlarında reklam, dekorasyon ve gizlilik çözümleri.'),
    1142: ('kutu-harf-tabela', '/kutu-harf-tabela/', 'Edremit Kutu Harf Tabela | Işıklı Kutu Harf | Class Reklam',
           'Edremit kutu harf tabela çözümleri: ışıklı ve ışıksız harf, logo ve cephe uygulamaları. Class Reklam’dan keşif ve teklif alın.'),
}


def api_url(route, params=None):
    if route.startswith('/wp-json'):
        route = route[len('/wp-json'):]
    q = {'rest_route': route}
    if params:
        q.update(params)
    return BASE + '/?' + urllib.parse.urlencode(q, doseq=True, safe='/:')


def api_once(method, route, params=None, payload=None):
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(api_url(route, params), data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {'raw_sample': raw[:1500]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw_sample': raw[:1500]}
        return e.code, body


def api(method, route, params=None, payload=None, delay=2.5):
    time.sleep(delay)
    last = None
    for attempt in range(4):
        code, body = api_once(method, route, params, payload)
        last = (code, body)
        text = json.dumps(body, ensure_ascii=False).lower() if isinstance(body, (dict, list)) else str(body).lower()
        if code != 403 or 'imunify360' not in text:
            return code, body
        time.sleep(12 * (attempt + 1))
    return last


def ensure(code, body, label):
    if code not in (200, 201):
        raise RuntimeError(f'{label}: HTTP {code} {body}')


def plain(value):
    value = html.unescape(str(value or ''))
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def get_page(page_id):
    code, body = api('GET', f'/wp/v2/pages/{page_id}', {
        'context': 'edit', '_fields': 'id,slug,status,link,modified,title,content'
    })
    ensure(code, body, f'get page {page_id}')
    return body


def get_posts():
    code, body = api('GET', '/wp/v2/posts', {
        'context': 'edit', 'per_page': 100,
        '_fields': 'id,slug,status,link,modified,title,content,categories'
    })
    ensure(code, body, 'get posts')
    if not isinstance(body, list):
        raise RuntimeError('posts response is not a list')
    return body


def write_content(kind, object_id, content):
    code, body = api('POST', f'/wp/v2/{kind}/{object_id}', payload={'content': content})
    ensure(code, body, f'update {kind}/{object_id}')


def update_meta(object_id, title, description, canonical, robots=None):
    meta = {
        'rank_math_title': title,
        'rank_math_description': description,
        'rank_math_canonical_url': canonical,
    }
    if robots is not None:
        meta['rank_math_robots'] = robots
    code, body = api('POST', '/rankmath/v1/updateMeta', payload={
        'objectType': 'post', 'objectID': int(object_id), 'meta': meta
    })
    ensure(code, body, f'Rank Math meta {object_id}')


def update_redirect(object_id, target=None):
    payload = {
        'objectID': int(object_id), 'objectType': 'post',
        'hasRedirect': bool(target), 'redirectionType': '301'
    }
    if target:
        payload['redirectionUrl'] = target
    code, body = api('POST', '/rankmath/v1/updateRedirection', payload=payload)
    ensure(code, body, f'Rank Math redirect {object_id}')


def parse_head(raw):
    def grab(pattern, alt=None):
        match = re.search(pattern, raw, re.I | re.S)
        if not match and alt:
            match = re.search(alt, raw, re.I | re.S)
        return html.unescape(match.group(1)).strip() if match else ''
    return {
        'title': grab(r'<title[^>]*>(.*?)</title>'),
        'description': grab(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']'
        ),
        'canonical': grab(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']'
        ),
        'robots': grab(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']robots["\']'
        ),
        'head_chars': len(raw),
    }


def public_head(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read(500000).decode('utf-8', errors='replace')
            blocked = 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()
            return {'http': r.status, 'waf': blocked, **parse_head(raw)}
    except urllib.error.HTTPError as e:
        raw = e.read(500000).decode('utf-8', errors='replace')
        blocked = 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()
        return {'http': e.code, 'waf': blocked, **parse_head(raw)}
    except Exception as e:
        return {'http': 0, 'waf': False, 'title': '', 'description': '', 'canonical': '', 'robots': '', 'head_chars': 0, 'error': f'{type(e).__name__}: {e}'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_status(url):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with opener.open(req, timeout=35) as r:
            raw = r.read(120000).decode('utf-8', errors='replace')
            return {'http': r.status, 'location': r.headers.get('Location', ''), 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()}
    except urllib.error.HTTPError as e:
        raw = e.read(120000).decode('utf-8', errors='replace')
        return {'http': e.code, 'location': e.headers.get('Location', ''), 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()}
    except Exception as e:
        return {'http': 0, 'location': '', 'waf': False, 'error': f'{type(e).__name__}: {e}'}


def replace_home_h1(raw):
    matches = list(re.finditer(r'<h1\b[^>]*>(.*?)</h1>', raw, re.I | re.S))
    if len(matches) != 1:
        return raw, False, f'blocked:h1_count={len(matches)}'
    match = matches[0]
    current = plain(match.group(1))
    desired = 'Edremit Tabela ve Reklam Çözümleri'
    old = 'Baskı, Tabela ve Folyo Çözümlerinde Profesyonel Hizmet'
    if current == desired:
        return raw, False, 'already-correct'
    if current != old:
        return raw, False, f'blocked:unexpected-h1={current!r}'
    inner = match.group(1)
    if 'cr-heading-line1' not in inner or 'cr-heading-line2' not in inner:
        return raw, False, 'blocked:expected-line-spans-missing'
    changed = re.sub(
        r'(<span\b[^>]*class=["\'][^"\']*cr-heading-line1[^"\']*["\'][^>]*>).*?(</span>)',
        r'\1Edremit Tabela ve Reklam\2', inner, count=1, flags=re.I | re.S
    )
    changed = re.sub(
        r'(<span\b[^>]*class=["\'][^"\']*cr-heading-line2[^"\']*["\'][^>]*>).*?(</span>)',
        r'\1Çözümleri\2', changed, count=1, flags=re.I | re.S
    )
    return raw[:match.start(1)] + changed + raw[match.end(1):], True, 'updated'


def ensure_home_copy(raw):
    old = 'Edremit’te tabela, totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
    intermediate = 'Edremit’te tabela ve reklam firması olarak; totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
    desired = 'Edremit’te reklam ve tabela firması olarak; totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
    if desired in raw:
        return raw, False, 'already-correct'
    if intermediate in raw:
        return raw.replace(intermediate, desired, 1), True, 'normalized-known-intermediate-copy'
    if old in raw:
        return raw.replace(old, desired, 1), True, 'updated'
    return raw, False, 'blocked:unexpected-home-copy'


def ensure_service_hub_links(raw):
    if 'cr-seo-service-hub-links' in raw:
        return raw, False, 'already-present'
    block = '''\n<!-- cr-seo-service-hub-links -->\n<!-- wp:heading -->\n<h2 class="wp-block-heading">Edremit Tabela ve Reklam Hizmetleri</h2>\n<!-- /wp:heading -->\n<!-- wp:paragraph -->\n<p>İhtiyacınıza göre <a href="/edremit-tabela/">Edremit tabela</a>, <a href="/totem-tabela/">totem tabela</a>, <a href="/dijital-baski/">dijital baskı</a>, <a href="/arac-giydirme/">araç giydirme</a>, <a href="/cam-giydirme/">cam giydirme ve folyo</a> ile <a href="/kutu-harf-tabela/">kutu harf tabela</a> hizmetlerimizin detaylarını inceleyebilirsiniz.</p>\n<!-- /wp:paragraph -->\n'''
    return raw + block, True, 'added'


def remove_duplicate_title_h1_block(raw, title):
    h1s = list(re.finditer(r'<h1\b[^>]*>(.*?)</h1>', raw, re.I | re.S))
    exact = [m for m in h1s if plain(m.group(1)).casefold() == title.casefold()]
    if not exact:
        return raw, False, 'no-embedded-title-h1'
    if len(exact) != 1 or len(h1s) != 1:
        return raw, False, f'ambiguous:h1_count={len(h1s)} exact_title_h1={len(exact)}'
    target = exact[0]
    pattern = re.compile(
        r'<!--\s*wp:heading(?:\s+\{.*?\})?\s*-->\s*<h1\b[^>]*>.*?</h1>\s*<!--\s*/wp:heading\s*-->',
        re.I | re.S
    )
    candidates = [m for m in pattern.finditer(raw) if m.start() <= target.start() and m.end() >= target.end()]
    if len(candidates) != 1:
        return raw, False, 'ambiguous:matching-gutenberg-h1-block-not-found'
    block = candidates[0]
    return raw[:block.start()] + raw[block.end():], True, 'removed-duplicate-title-h1-block'


def first_paragraph_repeat_count(raw):
    paragraphs = [plain(x) for x in re.findall(r'<p\b[^>]*>(.*?)</p>', raw, re.I | re.S)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return 0
    first = paragraphs[0].casefold()
    return sum(1 for p in paragraphs if p.casefold() == first)


def save_result(data):
    (EVIDENCE_DIR / 'seo-remediation-result-2026-08-14.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    results = {
        'started_at': started,
        'status': 'preflight',
        'planned': [],
        'changes': [],
        'fatal_blockers': [],
        'deferred': [],
        'rollback': [],
    }
    backup = {
        'checked_at': started,
        'base': BASE,
        'pages': {},
        'posts': {},
        'rendered_heads': {},
        'legacy_public': None,
    }

    code, settings = api('GET', '/wp/v2/settings')
    ensure(code, settings, 'settings preflight')
    wp_url = str(settings.get('url') or '').rstrip('/')
    wp_home = str(settings.get('home') or '').rstrip('/')
    if wp_url != BASE or (wp_home and wp_home != BASE):
        raise RuntimeError(f'canonical site mismatch: url={settings.get("url")} home={settings.get("home")}')

    required_pages = {pid: meta[0] for pid, meta in META_TARGETS.items()}
    required_pages[683] = 'referans-isler'
    pages = {}
    for pid, slug in required_pages.items():
        try:
            page = get_page(pid)
        except Exception:
            if pid == 683:
                results['deferred'].append({'page': 683, 'scope': 'legacy_redirect', 'detail': 'legacy page not available through authenticated REST'})
                continue
            raise
        if page.get('slug') != slug or page.get('status') != 'publish':
            raise RuntimeError(f'page identity mismatch {pid}: slug={page.get("slug")} status={page.get("status")} expected={slug}/publish')
        pages[pid] = page
        backup['pages'][str(pid)] = page

    posts = get_posts()
    for post in posts:
        backup['posts'][str(post.get('id'))] = post

    rendered_heads = {}
    for pid, (_, path, _, _) in META_TARGETS.items():
        current = public_head(BASE + path)
        backup['rendered_heads'][str(pid)] = {'path': path, **current}
        rendered_heads[pid] = current
        if current.get('http') != 200 or current.get('waf') or not current.get('head_chars'):
            results['fatal_blockers'].append({'page': pid, 'field': 'rendered_head', 'detail': current})

    content_plan = []
    home_raw = pages[6].get('content', {}).get('raw', '')
    staged, h1_changed, h1_status = replace_home_h1(home_raw)
    if h1_status.startswith('blocked:'):
        results['fatal_blockers'].append({'page': 6, 'field': 'h1', 'detail': h1_status})
    home_final, copy_changed, copy_status = ensure_home_copy(staged)
    if copy_status.startswith('blocked:'):
        results['fatal_blockers'].append({'page': 6, 'field': 'hero-copy', 'detail': copy_status})
    if h1_changed or copy_changed:
        content_plan.append({'kind': 'pages', 'id': 6, 'content': home_final, 'reason': {'h1': h1_status, 'copy': copy_status}})

    hub_raw = pages[10].get('content', {}).get('raw', '')
    hub_new, hub_changed, hub_status = ensure_service_hub_links(hub_raw)
    if hub_changed:
        content_plan.append({'kind': 'pages', 'id': 10, 'content': hub_new, 'reason': {'service_hub_links': hub_status}})

    for post in posts:
        pid = post.get('id')
        title_obj = post.get('title') or {}
        title = plain(title_obj.get('raw') if isinstance(title_obj, dict) else title_obj)
        raw = (post.get('content') or {}).get('raw', '')
        if first_paragraph_repeat_count(raw) > 1:
            results['deferred'].append({'post': pid, 'scope': 'blog_content', 'detail': 'repeated first paragraph in source; skipped'})
            continue
        if 'uncategorized' in plain(raw).casefold():
            results['deferred'].append({'post': pid, 'scope': 'blog_content', 'detail': 'literal Uncategorized in source; skipped'})
            continue
        new_raw, changed, status = remove_duplicate_title_h1_block(raw, title)
        if status.startswith('ambiguous:'):
            results['deferred'].append({'post': pid, 'scope': 'blog_h1', 'detail': status})
        elif changed:
            content_plan.append({'kind': 'posts', 'id': pid, 'content': new_raw, 'reason': {'duplicate_title_h1': status}})

    meta_plan = []
    for pid, (_, path, title, description) in META_TARGETS.items():
        current = rendered_heads.get(pid, {})
        canonical = BASE + ('/' if path == '/' else path)
        robots = ['index', 'follow'] if 'noindex' in str(current.get('robots', '')).lower() else None
        if current.get('title') != title or current.get('description') != description or current.get('canonical') != canonical or robots:
            meta_plan.append({'id': pid, 'title': title, 'description': description, 'canonical': canonical, 'robots': robots})

    redirect_plan = None
    if 683 in pages:
        legacy = public_status(BASE + '/referans-isler/')
        backup['legacy_public'] = legacy
        target = BASE + '/referanslar/'
        if legacy.get('http') == 200 and not legacy.get('waf'):
            redirect_plan = {'id': 683, 'target': target}
        elif legacy.get('http') in (301, 308) and legacy.get('location') == target:
            results['planned'].append({'page': 683, 'redirect': 'already-correct'})
        elif legacy.get('http') in (404, 410):
            results['planned'].append({'page': 683, 'redirect': f'legacy already unavailable HTTP {legacy.get("http")}'})
        else:
            results['deferred'].append({'page': 683, 'scope': 'legacy_redirect', 'detail': f'public state not safe to change: {legacy}'})

    (EVIDENCE_DIR / 'seo-remediation-backup-2026-08-14.json').write_text(
        json.dumps(backup, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    results['planned'].extend([{'content': {'kind': p['kind'], 'id': p['id'], **p['reason']}} for p in content_plan])
    results['planned'].extend([{'meta': {'id': p['id'], 'canonical': p['canonical']}} for p in meta_plan])
    if redirect_plan:
        results['planned'].append({'redirect': redirect_plan})

    if results['fatal_blockers']:
        results['status'] = 'blocked-no-writes'
        results['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_result(results)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    applied_content = []
    applied_meta = []
    redirect_applied = False
    try:
        for plan in content_plan:
            write_content(plan['kind'], plan['id'], plan['content'])
            applied_content.append((plan['kind'], plan['id']))
            results['changes'].append({'content': {'kind': plan['kind'], 'id': plan['id'], **plan['reason']}})

        for plan in meta_plan:
            update_meta(plan['id'], plan['title'], plan['description'], plan['canonical'], plan['robots'])
            applied_meta.append(plan['id'])
            results['changes'].append({'meta': {'id': plan['id'], 'canonical': plan['canonical']}})

        if redirect_plan:
            update_redirect(redirect_plan['id'], redirect_plan['target'])
            redirect_applied = True
            results['changes'].append({'redirect': redirect_plan})

    except Exception as exc:
        results['status'] = 'write-failed-rollback-attempted'
        results['write_error'] = f'{type(exc).__name__}: {exc}'
        for kind, oid in reversed(applied_content):
            try:
                source = backup['pages'].get(str(oid)) if kind == 'pages' else backup['posts'].get(str(oid))
                old = (source or {}).get('content', {}).get('raw', '')
                write_content(kind, oid, old)
                results['rollback'].append({'content': {'kind': kind, 'id': oid, 'status': 'restored'}})
            except Exception as rb_exc:
                results['rollback'].append({'content': {'kind': kind, 'id': oid, 'status': 'FAILED', 'error': str(rb_exc)}})
        for oid in reversed(applied_meta):
            try:
                old = backup['rendered_heads'][str(oid)]
                old_robots = str(old.get('robots', '')).lower()
                robots = ['noindex' if 'noindex' in old_robots else 'index', 'nofollow' if 'nofollow' in old_robots else 'follow']
                update_meta(oid, old.get('title', ''), old.get('description', ''), old.get('canonical', ''), robots)
                results['rollback'].append({'meta': {'id': oid, 'status': 'rendered-surface-restored'}})
            except Exception as rb_exc:
                results['rollback'].append({'meta': {'id': oid, 'status': 'FAILED', 'error': str(rb_exc)}})
        if redirect_applied:
            try:
                update_redirect(683, None)
                results['rollback'].append({'redirect': {'id': 683, 'status': 'disabled'}})
            except Exception as rb_exc:
                results['rollback'].append({'redirect': {'id': 683, 'status': 'FAILED', 'error': str(rb_exc)}})
        results['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_result(results)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        raise

    results['status'] = 'success-with-deferred' if results['deferred'] else 'success'
    results['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save_result(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
