#!/usr/bin/env python3
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ['WP_URL'].rstrip('/')
AUTH = 'Basic ' + base64.b64encode(
    f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()
).decode()
UA = 'Mozilla/5.0 (compatible; ClassReklamSEO/1.0)'
SOURCE = BASE + '/referans-isler/'
TARGET = BASE + '/referanslar/'
OUT = '.ops/seo-retire-legacy-reference-2026-08-14.json'
BACKUP = '.ops/seo-retire-legacy-reference-backup-2026-08-14.json'


def api(method, route, params=None, payload=None):
    query = {'rest_route': route}
    if params:
        query.update(params)
    q = urllib.parse.urlencode(query, doseq=True, safe='/:')
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json', 'User-Agent': UA, 'Referer': BASE + '/wp-admin/'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(BASE + '/?' + q, data=data, headers=headers, method=method)
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public(url):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'})
    try:
        with opener.open(req, timeout=35) as r:
            raw = r.read(160000).decode('utf-8', errors='replace')
            return {'http': r.status, 'location': r.headers.get('Location', ''), 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()}
    except urllib.error.HTTPError as e:
        raw = e.read(160000).decode('utf-8', errors='replace')
        return {'http': e.code, 'location': e.headers.get('Location', ''), 'waf': 'one moment, please' in raw.lower() or 'imunify360' in raw.lower()}
    except Exception as e:
        return {'http': 0, 'location': '', 'waf': False, 'error': f'{type(e).__name__}: {e}'}


def save(path, value):
    os.makedirs('.ops', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def main():
    result = {'source': SOURCE, 'target': TARGET, 'status': 'preflight'}
    before_source = public(SOURCE)
    before_target = public(TARGET)
    result['before_source'] = before_source
    result['before_target'] = before_target

    if before_source.get('waf') or before_target.get('waf'):
        result['status'] = 'blocked-waf-preflight'
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    if before_target.get('http') != 200:
        result['status'] = 'blocked-target-not-200'
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(3)
    if before_source.get('http') in (404, 410):
        result['status'] = 'already-retired'
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if before_source.get('http') != 200:
        result['status'] = 'blocked-unexpected-source-state'
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(4)

    code, page = api(
        'GET', '/wp/v2/pages/683',
        params={'context': 'edit', '_fields': 'id,slug,status,link,title,content,excerpt,modified,meta'}
    )
    result['page_read_http'] = code
    if code != 200 or not isinstance(page, dict) or page.get('id') != 683 or page.get('slug') != 'referans-isler' or page.get('status') != 'publish':
        result['status'] = 'blocked-page-identity'
        result['page'] = page
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(5)

    save(BACKUP, page)

    code, body = api('POST', '/wp/v2/pages/683', payload={'status': 'draft'})
    result['draft_write_http'] = code
    if code not in (200, 201):
        result['status'] = 'draft-write-failed'
        result['write_body'] = body
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(6)

    after_source = None
    after_target = None
    for _ in range(5):
        time.sleep(4)
        after_source = public(SOURCE)
        after_target = public(TARGET)
        if not after_source.get('waf') and not after_target.get('waf') and after_source.get('http') in (404, 410) and after_target.get('http') == 200:
            break
    result['after_source'] = after_source
    result['after_target'] = after_target

    if after_source and after_target and not after_source.get('waf') and not after_target.get('waf') and after_source.get('http') in (404, 410) and after_target.get('http') == 200:
        result['status'] = 'success'
        save(OUT, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    rb_code, rb_body = api('POST', '/wp/v2/pages/683', payload={'status': 'publish'})
    result['rollback_http'] = rb_code
    result['rollback_body'] = rb_body
    result['status'] = 'verification-failed-rollback-attempted'
    save(OUT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(7)


if __name__ == '__main__':
    main()
