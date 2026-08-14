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

SERVICE_PAGES = {
    1132: ('edremit-tabela', 'Edremit Tabela | Işıklı ve Işıksız Tabela | Class Reklam',
           'Edremit tabela çözümleri: ışıklı ve ışıksız tabela, cephe tabelası, yönlendirme ve özel üretim. Class Reklam’dan keşif ve teklif alın.',
           'edremit tabela'),
    1134: ('totem-tabela', 'Edremit Totem Tabela | Yol Kenarı Totem | Class Reklam',
           'Edremit totem tabela üretimi ve uygulaması. Yol kenarı, işletme girişi ve geniş alanlarda görünürlüğü artıran kurumsal totem çözümleri.',
           'edremit totem tabela'),
    1136: ('dijital-baski', 'Edremit Dijital Baskı | Vinil, Branda ve Folyo | Class Reklam',
           'Edremit dijital baskı hizmetleri: vinil, branda, folyo ve dış mekân baskı uygulamaları. Ölçünüze ve kullanım alanınıza uygun üretim.',
           'edremit dijital baskı'),
    1138: ('arac-giydirme', 'Edremit Araç Giydirme ve Araç Kaplama | Class Reklam',
           'Edremit araç giydirme ve araç kaplama hizmeti. Ticari araçlar için kurumsal folyo, baskılı grafik ve mobil reklam uygulamaları.',
           'edremit araç giydirme'),
    1140: ('cam-giydirme', 'Edremit Cam Giydirme ve Cam Folyo | Class Reklam',
           'Edremit cam giydirme ve vitrin folyo uygulamaları. Mağaza ve ofis camlarında reklam, dekorasyon ve gizlilik çözümleri.',
           'edremit cam giydirme'),
    1142: ('kutu-harf-tabela', 'Edremit Kutu Harf Tabela | Işıklı Kutu Harf | Class Reklam',
           'Edremit kutu harf tabela çözümleri: ışıklı ve ışıksız harf, logo ve cephe uygulamaları. Class Reklam’dan keşif ve teklif alın.',
           'edremit kutu harf tabela'),
}

CORE_META = {
    6: ('ana-sayfa', 'Edremit Reklam ve Tabela Firması | Class Reklam',
        'Edremit’te tabela, totem, kutu harf, dijital baskı, araç ve cam giydirme çözümleri. Class Reklam’dan keşif ve teklif alın.',
        'edremit reklam firması', BASE + '/'),
    10: ('hizmetlerimiz', 'Edremit Tabela ve Reklam Hizmetleri | Class Reklam',
         'Edremit tabela, totem, kutu harf, dijital baskı, araç giydirme ve cam folyo hizmetlerini inceleyin. Class Reklam’dan teklif alın.',
         'edremit reklam tabela', BASE + '/hizmetlerimiz/'),
    18: ('iletisim', 'Class Reklam İletişim | Edremit Tabela ve Reklam',
         'Edremit’te tabela, reklam, dijital baskı, araç giydirme ve folyo uygulamaları için Class Reklam’a ulaşın. Telefon: 0546 936 42 71.',
         'class reklam iletişim', BASE + '/iletisim/'),
}


def build_url(route, params=None):
    if route.startswith('/wp-json'):
        route = route[len('/wp-json'):]
    q = {'rest_route': route}
    if params:
        q.update(params)
    return BASE + '/?' + urllib.parse.urlencode(q, doseq=True, safe='/:')


def one(method, route, params=None, payload=None):
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
    req = urllib.request.Request(build_url(route, params), data=data, headers=headers, method=method)
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


def request(method, route, params=None, payload=None, delay=2.5):
    time.sleep(delay)
    last = None
    for attempt in range(4):
        code, body = one(method, route, params, payload)
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
    code, body = request('GET', f'/wp/v2/pages/{page_id}', {
        'context': 'edit', '_fields': 'id,slug,status,link,modified,title,content'
    })
    ensure(code, body, f'get page {page_id}')
    return body


def get_posts():
    code, body = request('GET', '/wp/v2/posts', {
        'context': 'edit', 'per_page': 100,
        '_fields': 'id,slug,status,link,modified,title,content,categories'
    })
    ensure(code, body, 'get posts')
    if not isinstance(body, list):
        raise RuntimeError('posts response is not a list')
    return body


def update_content(kind, object_id, content):
    code, body = request('POST', f'/wp/v2/{kind}/{object_id}', payload={'content': content})
    ensure(code, body, f'update {kind}/{object_id}')
    return body


def rank_meta(object_id, title, description, focus, canonical):
    payload = {
        'objectType': 'post',
        'objectID': int(object_id),
        'meta': {
            'rank_math_title': title,
            'rank_math_description': description,
            'rank_math_focus_keyword': focus,
            'rank_math_canonical_url': canonical,
        },
    }
    code, body = request('POST', '/rankmath/v1/updateMeta', payload=payload)
    ensure(code, body, f'Rank Math meta {object_id}')


def rank_redirect(object_id, target):
    payload = {
        'objectID': int(object_id),
        'objectType': 'post',
        'hasRedirect': True,
        'redirectionUrl': target,
        'redirectionType': '301',
    }
    code, body = request('POST', '/rankmath/v1/updateRedirection', payload=payload)
    ensure(code, body, f'Rank Math redirect {object_id}')


def rank_head(url):
    code, body = request('GET', '/rankmath/v1/getHead', {'url': url})
    ensure(code, body, f'Rank Math head {url}')
    return body


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
    new_raw = raw[:match.start(1)] + changed + raw[match.end(1):]
    return new_raw, True, 'updated'


def ensure_home_copy(raw):
    old = 'Edremit’te tabela, totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
    new = 'Edremit’te reklam ve tabela firması olarak; totem, dijital baskı, araç giydirme, cam giydirme ve kutu harf çözümleriyle markanızı profesyonel şekilde görünür kılıyoruz.'
    if new in raw:
        return raw, False, 'already-correct'
    if old in raw:
        return raw.replace(old, new, 1), True, 'updated'
    return raw, False, 'blocked:expected-home-copy-not-found'


def ensure_service_hub_links(raw):
    marker = 'cr-seo-service-hub-links'
    if marker in raw:
        return raw, False, 'already-present'
    block = '''\n<!-- cr-seo-service-hub-links -->\n<!-- wp:heading -->\n<h2 class="wp-block-heading">Edremit Tabela ve Reklam Hizmetleri</h2>\n<!-- /wp:heading -->\n<!-- wp:paragraph -->\n<p>İhtiyacınıza göre <a href="/edremit-tabela/">Edremit tabela</a>, <a href="/totem-tabela/">totem tabela</a>, <a href="/dijital-baski/">dijital baskı</a>, <a href="/arac-giydirme/">araç giydirme</a>, <a href="/cam-giydirme/">cam giydirme ve folyo</a> ile <a href="/kutu-harf-tabela/">kutu harf tabela</a> hizmetlerimizin detaylarını inceleyebilirsiniz.</p>\n<!-- /wp:paragraph -->\n'''
    return raw + block, True, 'added'


def remove_duplicate_title_h1_block(raw, title):
    h1s = list(re.finditer(r'<h1\b[^>]*>(.*?)</h1>', raw, re.I | re.S))
    exact = [m for m in h1s if plain(m.group(1)).casefold() == title.casefold()]
    if not exact:
        return raw, False, 'no-embedded-title-h1'
    if len(exact) != 1 or len(h1s) != 1:
        return raw, False, f'blocked:h1_count={len(h1s)} exact_title_h1={len(exact)}'
    target = exact[0]
    block_pattern = re.compile(
        r'<!--\s*wp:heading(?:\s+\{.*?\})?\s*-->\s*<h1\b[^>]*>.*?</h1>\s*<!--\s*/wp:heading\s*-->',
        re.I | re.S,
    )
    candidates = [m for m in block_pattern.finditer(raw) if m.start() <= target.start() and m.end() >= target.end()]
    if len(candidates) != 1:
        return raw, False, 'blocked:matching-gutenberg-h1-block-not-found'
    block = candidates[0]
    return raw[:block.start()] + raw[block.end():], True, 'removed-duplicate-title-h1-block'


def paragraph_repeat_count(raw):
    paragraphs = [plain(x) for x in re.findall(r'<p\b[^>]*>(.*?)</p>', raw, re.I | re.S)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return 0
    first = paragraphs[0].casefold()
    return sum(1 for p in paragraphs if p.casefold() == first)


def main():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    backup = {'checked_at': started, 'base': BASE, 'pages': {}, 'posts': {}, 'rank_heads': {}}
    results = {'started_at': started, 'status': 'running', 'changes': [], 'blocked': [], 'verified_inputs': []}

    settings_code, settings = request('GET', '/wp/v2/settings')
    ensure(settings_code, settings, 'settings preflight')
    wp_url = str(settings.get('url') or '').rstrip('/')
    wp_home = str(settings.get('home') or '').rstrip('/')
    if wp_url != BASE or (wp_home and wp_home != BASE):
        raise RuntimeError(f'canonical site mismatch: url={settings.get("url")} home={settings.get("home")}')
    results['verified_inputs'].append('canonical WordPress URL; home matched when exposed')

    expected_pages = {6: 'ana-sayfa', 10: 'hizmetlerimiz', 18: 'iletisim', 683: 'referans-isler'}
    expected_pages.update({pid: meta[0] for pid, meta in SERVICE_PAGES.items()})
    pages = {}
    for pid, slug in expected_pages.items():
        try:
            page = get_page(pid)
        except Exception:
            if pid == 683:
                continue
            raise
        if page.get('slug') != slug or page.get('status') != 'publish':
            raise RuntimeError(f'page identity mismatch {pid}: slug={page.get("slug")} status={page.get("status")} expected={slug}/publish')
        pages[pid] = page
        backup['pages'][str(pid)] = page
    results['verified_inputs'].append('expected page IDs/slugs/statuses')

    posts = get_posts()
    for post in posts:
        backup['posts'][str(post.get('id'))] = post
    results['verified_inputs'].append(f'blog posts={len(posts)}')

    for path in ['/', '/hizmetlerimiz/', '/iletisim/', '/edremit-tabela/', '/totem-tabela/', '/dijital-baski/', '/arac-giydirme/', '/cam-giydirme/', '/kutu-harf-tabela/', '/referans-isler/']:
        try:
            backup['rank_heads'][path] = rank_head(BASE + path)
        except Exception as exc:
            backup['rank_heads'][path] = {'error': str(exc)}

    (EVIDENCE_DIR / 'seo-remediation-backup-2026-08-14.json').write_text(
        json.dumps(backup, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    home = pages[6]
    home_raw = home.get('content', {}).get('raw', '')
    updated, changed_h1, h1_status = replace_home_h1(home_raw)
    if h1_status.startswith('blocked:'):
        results['blocked'].append({'page': 6, 'field': 'h1', 'detail': h1_status})
    updated2, changed_copy, copy_status = ensure_home_copy(updated)
    if copy_status.startswith('blocked:'):
        results['blocked'].append({'page': 6, 'field': 'hero-copy', 'detail': copy_status})
    if changed_h1 or changed_copy:
        update_content('pages', 6, updated2)
        results['changes'].append({'page': 6, 'h1': h1_status, 'copy': copy_status})

    hub = pages[10]
    hub_raw = hub.get('content', {}).get('raw', '')
    hub_new, hub_changed, hub_status = ensure_service_hub_links(hub_raw)
    if hub_changed:
        update_content('pages', 10, hub_new)
        results['changes'].append({'page': 10, 'service_hub_links': hub_status})

    for post in posts:
        post_id = post.get('id')
        title_obj = post.get('title') or {}
        title = plain(title_obj.get('raw') if isinstance(title_obj, dict) else title_obj)
        raw = (post.get('content') or {}).get('raw', '')
        if paragraph_repeat_count(raw) > 1:
            results['blocked'].append({'post': post_id, 'field': 'content', 'detail': 'repeated first paragraph in source; manual review required'})
            continue
        if 'uncategorized' in plain(raw).casefold():
            results['blocked'].append({'post': post_id, 'field': 'content', 'detail': 'literal Uncategorized found in source; manual review required'})
            continue
        new_raw, changed, status = remove_duplicate_title_h1_block(raw, title)
        if status.startswith('blocked:'):
            results['blocked'].append({'post': post_id, 'field': 'h1', 'detail': status})
        elif changed:
            update_content('posts', post_id, new_raw)
            results['changes'].append({'post': post_id, 'duplicate_title_h1': status})

    for pid, (_, title, description, focus, canonical) in CORE_META.items():
        rank_meta(pid, title, description, focus, canonical)
        results['changes'].append({'page': pid, 'rank_math_meta': 'updated'})

    for pid, (slug, title, description, focus) in SERVICE_PAGES.items():
        rank_meta(pid, title, description, focus, BASE + f'/{slug}/')
        results['changes'].append({'page': pid, 'rank_math_meta': 'updated'})

    if 683 in pages:
        rank_redirect(683, BASE + '/referanslar/')
        results['changes'].append({'page': 683, 'redirect': BASE + '/referanslar/', 'type': 301})

    results['status'] = 'success' if not results['blocked'] else 'partial-blocked'
    results['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (EVIDENCE_DIR / 'seo-remediation-result-2026-08-14.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if results['blocked']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
