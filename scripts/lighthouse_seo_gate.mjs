import fs from 'node:fs';

const [mobilePath = '.ops/lighthouse-mobile.json', desktopPath = '.ops/lighthouse-desktop.json'] = process.argv.slice(2);
const load = path => JSON.parse(fs.readFileSync(path, 'utf8'));
const mobile = load(mobilePath);
const desktop = load(desktopPath);

function summarize(name, report, requireMobilePerf = false) {
  const categories = report.categories || {};
  const audits = report.audits || {};
  const getScore = key => Number(categories[key]?.score ?? -1);
  const lcp = Number(audits['largest-contentful-paint']?.numericValue ?? Infinity);
  const cls = Number(audits['cumulative-layout-shift']?.numericValue ?? Infinity);
  const tbt = Number(audits['total-blocking-time']?.numericValue ?? Infinity);
  const result = {
    name,
    scores: {
      performance: getScore('performance'),
      accessibility: getScore('accessibility'),
      best_practices: getScore('best-practices'),
      seo: getScore('seo'),
    },
    lab_metrics: { lcp_ms: lcp, cls, total_blocking_time_ms: tbt },
    field_inp: 'DATA NOT AVAILABLE',
    failures: [],
  };
  if (result.scores.seo < 1.0) result.failures.push(`SEO score ${result.scores.seo * 100} < 100`);
  if (result.scores.accessibility < 0.95) result.failures.push(`Accessibility ${result.scores.accessibility * 100} < 95`);
  if (result.scores.best_practices < 0.95) result.failures.push(`Best Practices ${result.scores.best_practices * 100} < 95`);
  if (requireMobilePerf && result.scores.performance < 0.90) result.failures.push(`Mobile performance ${result.scores.performance * 100} < 90`);
  if (lcp > 2500) result.failures.push(`Lab LCP ${Math.round(lcp)}ms > 2500ms`);
  if (cls > 0.1) result.failures.push(`Lab CLS ${cls} > 0.1`);
  return result;
}

const results = [summarize('mobile', mobile, true), summarize('desktop', desktop, false)];
const failures = results.flatMap(r => r.failures.map(detail => ({ profile: r.name, detail })));
const output = {
  checked_at: new Date().toISOString(),
  status: failures.length ? 'FAIL' : 'PASS',
  note: 'Lighthouse provides lab LCP/CLS/TBT. Field INP is not fabricated and remains DATA NOT AVAILABLE without CrUX/GSC field data.',
  results,
  failures,
};
fs.writeFileSync('.ops/lighthouse-seo-gate-2026-08-14.json', JSON.stringify(output, null, 2));
console.log(JSON.stringify(output, null, 2));
if (failures.length) process.exit(1);
