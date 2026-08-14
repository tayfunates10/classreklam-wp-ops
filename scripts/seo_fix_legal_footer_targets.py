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
AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamSEO/1.0)'
OUT = Path('.ops/seo-legal-footer-targets-2026-08-14.json')
BACKUP = Path('.ops/seo-legal-footer-targets-backup-2026-08-14.json')
MARKER = 'cr-seo-legal-bridge-v1'

TARGETS = {
    'gizlilik-politikasi': {
        'title': 'Gizlilik Politikası',
        'seo_title': 'Gizlilik Politikası | Class Reklam',
        'description': 'Class Reklam web sitesi gizlilik ve kişisel verilerle ilgili genel bilgilendirme bağlantıları.',
    },
    'kullanim-sartlari': {
        'title': 'Kullanım Şartları',
        'seo_title': 'Kullanım Şartları | Class Reklam',
        'description': 'Class Reklam web sitesi kullanımıyla ilgili genel bilgilendirme ve iletişim bağlantıları.',
    },
    'kvkk': {
        'title': 'KVKK Bilgilendirme',
        'seo_title': 'KVKK Bilgilendirme | Class Reklam',
        'description': 'Class Reklam kişisel veriler ve KVKK ile ilgili genel bilgilendirme ve iletişim bağlantıları.',
    },
}


def api_url(route, params=None):
    q = {'rest_route': route}
    if params:
        q.update(params)
    return BASE + '/?' + urllib.parse.urlencode(q, doseq=True, safe='/:')


def api(method, route, params=None, payload=None):
    time.sleep(1.5)
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(api_url(route, params), data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try: body = json.loads(raw) if raw else {}
            except Exception: body = {'raw_sample': raw[:1200]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try: body = json.loads(raw)
        except Exception: body = {'raw_sample': raw[:1200]}
        return e.code, body


def ensure(code, body, label):
    if code not in (200, 201):
        raise RuntimeError(f'{label}: HTTP {code} {body}')


def rendered(raw):
    def grab(pattern, alt=''):
        m = re.search(pattern, raw, re.I | re.S)
        if not m and alt:
            m = re.search(alt, raw, re.I | re.S)
        return html.unescape(m.group(1)).strip() if m else ''
    return {
        'title': grab(r'<title[^>]*>(.*?)</title>'),
        'canonical': grab(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']'),
        'robots': grab(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)', r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']robots["\']'),
    }


def public(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read(500000).decode('utf-8', errors='replace')
            return {'http': r.status, 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(), **rendered(raw)}
    except urllib.error.HTTPError as e:
        raw = e.read(500000).decode('utf-8', errors='replace')
        return {'http': e.code, 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(), **rendered(raw)}
    except Exception as e:
        return {'http': 0, 'waf': False, 'error': f'{type(e).__name__}: {e}', 'title': '', 'canonical': '', 'robots': ''}


def bridge_content(title):
    return f'''<!-- {MARKER} -->
<!-- wp:paragraph -->
<p>Class Reklam’ın web sitesi kullanımı, iletişim kanalları ve kişisel verilerle ilgili genel bilgilendirmelerini <a href="/yasal-bilgiler/">Yasal Bilgiler</a> sayfasında inceleyebilirsiniz.</p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p>{title} hakkında ek bilgi veya talebiniz varsa <a href="/iletisim/">İletişim</a> sayfasından bize ulaşabilirsiniz.</p>
<!-- /wp:paragraph -->'''


def update_meta(page_id, cfg, canonical):
    code, body = api('POST', '/rankmath/v1/updateMeta', payload={
        'objectType': 'post',
        'objectID': int(page_id),
        'meta': {
            'rank_math_title': cfg['seo_title'],
            'rank_math_description': cfg['description'],
            'rank_math_canonical_url': canonical,
            'rank_math_robots': ['noindex', 'follow'],
        },
    })
    ensure(code, body, f'Rank Math meta {page_id}')


def verified(after, url):
    canonical = str((after or {}).get('canonical') or '')
    return bool(
        after and after.get('http') == 200 and not after.get('waf')
        and 'noindex' in str(after.get('robots', '')).lower()
        and canonical in ('', url)
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = {'status': 'running', 'targets': [], 'rollback': []}
    backups = []
    try:
        for slug, cfg in TARGETS.items():
            url = BASE + '/' + slug + '/'
            before_public = public(url)
            code, found = api('GET', '/wp/v2/pages', params={
                'context': 'edit', 'slug': slug, 'per_page': 10,
                '_fields': 'id,slug,status,title,content,link,modified'
            })
            ensure(code, found, f'query page {slug}')
            if not isinstance(found, list):
                raise RuntimeError(f'{slug}: page query is not a list')
            if len(found) > 1:
                raise RuntimeError(f'{slug}: multiple existing pages found: {[x.get("id") for x in found]}')

            if found:
                page = found[0]
                raw = str((page.get('content') or {}).get('raw') or '')
                status = str(page.get('status') or '')
                backups.append({'kind': 'existing', 'id': page.get('id'), 'slug': slug, 'status': status, 'content': raw})
                if status == 'publish' and before_public.get('http') == 200:
                    page_id = int(page['id'])
                    action = 'existing-published'
                elif status in ('draft', 'pending', 'private'):
                    if raw.strip() and MARKER not in raw:
                        raise RuntimeError(f'{slug}: existing non-public page has unrecognized content; refusing overwrite')
                    code, body = api('POST', f'/wp/v2/pages/{page["id"]}', payload={
                        'title': cfg['title'], 'content': bridge_content(cfg['title']), 'status': 'publish'
                    })
                    ensure(code, body, f'publish existing page {slug}')
                    page_id = int(page['id'])
                    action = 'published-existing-safe-page'
                else:
                    raise RuntimeError(f'{slug}: unexpected existing status={status}')
            else:
                code, body = api('POST', '/wp/v2/pages', payload={
                    'title': cfg['title'], 'slug': slug, 'content': bridge_content(cfg['title']), 'status': 'publish'
                })
                ensure(code, body, f'create page {slug}')
                page_id = int(body.get('id') or 0)
                if not page_id:
                    raise RuntimeError(f'{slug}: created page missing id')
                backups.append({'kind': 'created', 'id': page_id, 'slug': slug})
                action = 'created'

            update_meta(page_id, cfg, url)
            after = None
            for _ in range(5):
                time.sleep(3)
                after = public(url)
                if verified(after, url):
                    break
            result['targets'].append({'slug': slug, 'id': page_id, 'action': action, 'before': before_public, 'after': after})
            if not verified(after, url):
                raise RuntimeError(f'{slug}: public verification failed: {after}')

        result['status'] = 'success'
        BACKUP.write_text(json.dumps(backups, ensure_ascii=False, indent=2), encoding='utf-8')
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        for item in reversed(backups):
            try:
                if item['kind'] == 'created':
                    code, body = api('POST', f'/wp/v2/pages/{item["id"]}', payload={'status': 'draft'})
                else:
                    code, body = api('POST', f'/wp/v2/pages/{item["id"]}', payload={'status': item['status'], 'content': item['content']})
                result['rollback'].append({'id': item['id'], 'slug': item['slug'], 'http': code, 'ok': code in (200, 201)})
            except Exception as rb_exc:
                result['rollback'].append({'id': item.get('id'), 'slug': item.get('slug'), 'ok': False, 'error': f'{type(rb_exc).__name__}: {rb_exc}'})
        result['status'] = 'failed-rollback-attempted'
        result['error'] = f'{type(exc).__name__}: {exc}'
        BACKUP.write_text(json.dumps(backups, ensure_ascii=False, indent=2), encoding='utf-8')
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise


if __name__ == '__main__':
    main()
