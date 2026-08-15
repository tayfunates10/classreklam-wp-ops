#!/usr/bin/env python3
import json
import os
import runpy
import sys

if os.environ.get('GITHUB_WORKFLOW') == 'Full SEO Baseline (Branch Only)':
    print(json.dumps({
        'status': 'superseded',
        'mode': 'read-only',
        'message': 'Standalone baseline workflow superseded by Guarded SEO Production Remediation'
    }))
    sys.exit(0)

runpy.run_path(
    os.path.join(os.path.dirname(__file__), 'full_seo_baseline_impl.py'),
    run_name='__main__'
)
