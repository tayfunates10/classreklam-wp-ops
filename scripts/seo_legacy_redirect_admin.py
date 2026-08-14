#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ['WP_URL'].rstrip('/')
COOKIE = os.environ['WP_SESSION_COOKIE_HEADER']
NONCE = os.environ['WP_REST_NONCE']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
SOURCE = BASE + '/referans-isler/'
TARGET = BASE + '/referanslar/'
OUT = '.ops/seo-legacy-redirect-admin-2026-08-14.json'


def request(method, path, payload=None, nonce=None):
    data = None
    headers = {
        'Accept': 'application/json',
        'User-Agent': UA,
        'Referer': BASE + '/wp-admin/',
        'Cookie': COOKIE,
    }
    if nonce:
        headers['X-WP-Nonce'] = nonce
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try: body = json.loads(raw) if raw else {}
            except Exception: body = {'raw_sample': raw[:1000]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try: body = json.loads(raw)
        except Exception: body = {'raw_sample': raw[:1000]}
        return e.code, body


def refresh_nonce():
    url = BASE + '/wp-admin/admin-ajax.php?' + urllib.parse.urlencode({'action': 'rest-nonce'})
    req = urllib.request.Request(url, headers={
        'Accept': 'text/plain,*/*',
        'User-Agent': UA,
        'Referer': BASE + '/wp-admin/',
        'Cookie': COOKIE,
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            value = r.read().decode('utf-8', errors='replace').strip()
            if r.status == 200 and value and value not in ('-1', '0') and len(value) <= 64:
                return r.status, value
            return r.status, ''
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception:
        return 0, ''


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_state():
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(SOURCE, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with opener.open(req, timeout=35) as r:
            raw = r.read(120000).decode('utf-8', errors='replace')
            return {
                'http': r.status,
                'location': r.headers.get('Location', ''),
                'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(),
            }
    except urllib.error.HTTPError as e:
        raw = e.read(120000).decode('utf-8', errors='replace')
        return {
            'http': e.code,
            'location': e.headers.get('Location', ''),
            'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower(),
        }
    except Exception as e:
        return {'http': 0, 'location': '', 'waf': False, 'error': f'{type(e).__name__}: {e}'}


def save(result):
    os.makedirs('.ops', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def valid_page(page):
    return isinstance(page, dict) and page.get('id') == 683 and page.get('slug') == 'referans-isler' and page.get('status') == 'publish'


def main():
    result = {'source': SOURCE, 'target': TARGET, 'status': 'running'}

    before = public_state()
    result['before'] = before
    if before.get('http') in (301, 308) and before.get('location') == TARGET:
        result['status'] = 'already-correct'
        save(result)
        return

    nonce = NONCE
    code, page = request('GET', '/wp-json/wp/v2/pages/683?context=edit&_fields=id,slug,status,link,title', nonce=nonce)
    result['initial_admin_page_http'] = code

    if code == 403 and isinstance(page, dict) and page.get('code') == 'rest_cookie_invalid_nonce':
        nonce_http, fresh_nonce = refresh_nonce()
        result['nonce_refresh_http'] = nonce_http
        result['nonce_refreshed'] = bool(fresh_nonce)
        if fresh_nonce:
            nonce = fresh_nonce
            code, page = request('GET', '/wp-json/wp/v2/pages/683?context=edit&_fields=id,slug,status,link,title', nonce=nonce)
            result['refreshed_admin_page_http'] = code

    if code != 200 or not valid_page(page):
        result['status'] = 'identity-or-admin-auth-failed'
        result['page'] = page
        save(result)
        raise SystemExit(3)

    if before.get('http') not in (0, 200) and not before.get('waf'):
        result['status'] = 'unexpected-public-state-before-write'
        save(result)
        raise SystemExit(2)

    payload = {
        'objectID': 683,
        'objectType': 'post',
        'hasRedirect': True,
        'redirectionUrl': TARGET,
        'redirectionType': '301',
    }
    code, body = request('POST', '/wp-json/rankmath/v1/updateRedirection', payload, nonce=nonce)
    result['redirect_api_http'] = code
    result['redirect_api_body'] = body
    if code not in (200, 201):
        result['status'] = 'redirect-write-failed'
        save(result)
        raise SystemExit(4)

    after = None
    for _ in range(6):
        time.sleep(4)
        after = public_state()
        if after.get('http') in (301, 308) and after.get('location') == TARGET:
            break
    result['after'] = after
    if after and after.get('http') in (301, 308) and after.get('location') == TARGET:
        result['status'] = 'success'
        save(result)
        return

    result['status'] = 'write-completed-public-indeterminate'
    save(result)
    raise SystemExit(5)


if __name__ == '__main__':
    main()
