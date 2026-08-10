#!/usr/bin/env python3
import importlib.util, json, os, urllib.error, urllib.request

spec = importlib.util.spec_from_file_location('phase1', 'scripts/apply_phase1.py')
phase1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase1)

BASE = os.environ['WP_URL'].rstrip('/')
COOKIE = os.environ['WP_SESSION_COOKIE_HEADER']
NONCE = os.environ['WP_REST_NONCE']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'


def cookie_request(method, path, payload=None):
    url = BASE + path
    data = None
    headers = {
        'Accept': 'application/json',
        'User-Agent': UA,
        'Referer': BASE + '/wp-admin/',
        'Cookie': COOKIE,
        'X-WP-Nonce': NONCE,
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {'raw': raw[:1000]}
            return r.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try:
            body = json.loads(raw)
        except Exception:
            body = {'raw': raw[:1000]}
        return e.code, body

phase1.request = cookie_request
phase1.main()
