import fs from 'node:fs';
import { chromium } from 'playwright';

const BASE = 'https://classreklamtabela.com.tr';
const OUT = process.env.SEO_LIVE_QA_OUT || '.ops/seo-live-qa-2026-08-14.json';
const viewports = [
  { name: 'mobile-360', width: 360, height: 800 },
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'mobile-412', width: 412, height: 915 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1440', width: 1440, height: 1000 },
];
const seoPaths = [
  '/', '/iletisim/', '/hizmetlerimiz/', '/hakkimizda/', '/blog/', '/referanslar/',
  '/edremit-tabela/', '/totem-tabela/', '/dijital-baski/', '/arac-giydirme/',
  '/cam-giydirme/', '/kutu-harf-tabela/'
];
const responsivePaths = ['/', '/hizmetlerimiz/', '/iletisim/', '/edremit-tabela/'];

function normalizeUrl(path) {
  return BASE + (path === '/' ? '/' : path);
}
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const report = {
  checked_at: new Date().toISOString(),
  base: BASE,
  scope: {
    desktop_seo_urls: seoPaths.length,
    responsive_urls_per_non_desktop_viewport: responsivePaths.length,
    viewports: viewports.map(v => v.name),
  },
  status: 'running',
  failures: [],
  warnings: [],
  pages: [],
};

const browser = await chromium.launch({ headless: true });
try {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    const paths = viewport.name === 'desktop-1440' ? seoPaths : responsivePaths;
    for (const path of paths) {
      const page = await context.newPage();
      const pageErrors = [];
      page.on('pageerror', err => pageErrors.push(String(err.message || err)));
      let response = null;
      let navigationError = null;
      try {
        response = await page.goto(normalizeUrl(path), { waitUntil: 'domcontentloaded', timeout: 45000 });
        await page.waitForTimeout(1200);
      } catch (err) {
        navigationError = String(err.message || err);
      }

      const status = response?.status() ?? 0;
      const finalUrl = page.url();
      const title = await page.title().catch(() => '');
      const waf = /one moment, please|imunify360/i.test(title) || await page.locator('body').innerText().then(t => /imunify360 bot-protection/i.test(t)).catch(() => false);
      const dom = await page.evaluate(() => {
        const canonical = document.querySelector('link[rel="canonical"]')?.href || '';
        const robots = document.querySelector('meta[name="robots"]')?.content || '';
        const h1s = [...document.querySelectorAll('h1')].map(el => (el.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
        const bodyOverflow = Math.max(document.documentElement.scrollWidth, document.body?.scrollWidth || 0) - window.innerWidth;
        const tel = [...document.querySelectorAll('a[href^="tel:"]')].map(a => a.getAttribute('href') || '');
        const whatsapp = [...document.querySelectorAll('a[href*="wa.me/"],a[href*="whatsapp.com/"]')].map(a => a.getAttribute('href') || '');
        const missingAlt = [...document.querySelectorAll('img')].filter(img => !img.hasAttribute('alt')).length;
        const jsonld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent || '');
        const internalLinks = [...document.querySelectorAll('a[href]')]
          .map(a => a.href)
          .filter(href => href.startsWith(location.origin));
        return { canonical, robots, h1s, bodyOverflow, tel, whatsapp, missingAlt, jsonld, internalLinks: [...new Set(internalLinks)].length };
      }).catch(() => ({ canonical: '', robots: '', h1s: [], bodyOverflow: 9999, tel: [], whatsapp: [], missingAlt: -1, jsonld: [], internalLinks: 0 }));

      const schema = { blocks: dom.jsonld.length, parse_errors: [], types: [], forbidden_review_markup: false };
      for (const [index, raw] of dom.jsonld.entries()) {
        try {
          const parsed = JSON.parse(raw);
          const stack = [parsed];
          while (stack.length) {
            const node = stack.pop();
            if (!node || typeof node !== 'object') continue;
            if (Array.isArray(node)) { stack.push(...node); continue; }
            const type = node['@type'];
            if (typeof type === 'string') schema.types.push(type);
            else if (Array.isArray(type)) schema.types.push(...type.filter(x => typeof x === 'string'));
            if ('aggregateRating' in node || 'review' in node || 'reviews' in node) schema.forbidden_review_markup = true;
            stack.push(...Object.values(node));
          }
        } catch (err) {
          schema.parse_errors.push({ index, error: String(err.message || err) });
        }
      }
      schema.types = [...new Set(schema.types)];

      const item = {
        viewport: viewport.name,
        path,
        requested_url: normalizeUrl(path),
        final_url: finalUrl,
        http: status,
        title,
        waf,
        navigation_error: navigationError,
        page_errors: pageErrors,
        ...dom,
        schema,
      };
      report.pages.push(item);

      const fail = detail => report.failures.push({ viewport: viewport.name, path, detail });
      if (navigationError) fail(`navigation: ${navigationError}`);
      if (status !== 200) fail(`HTTP ${status}`);
      if (waf) fail('WAF challenge served instead of page');
      if (!title.trim()) fail('missing document title');
      if (dom.h1s.length !== 1) fail(`h1_count=${dom.h1s.length}`);
      if (dom.bodyOverflow > 2) fail(`horizontal_overflow=${dom.bodyOverflow}px`);
      if (dom.canonical !== normalizeUrl(path)) fail(`canonical=${JSON.stringify(dom.canonical)} expected=${normalizeUrl(path)}`);
      if (/noindex/i.test(dom.robots)) fail(`robots=${dom.robots}`);
      if (dom.missingAlt > 0) fail(`images_missing_alt_attribute=${dom.missingAlt}`);
      if (schema.parse_errors.length) fail(`invalid_jsonld_blocks=${schema.parse_errors.length}`);
      if (schema.forbidden_review_markup) fail('review/rating schema present without verified review evidence');
      if (pageErrors.length) report.warnings.push({ viewport: viewport.name, path, detail: `page_errors=${pageErrors.join(' | ')}` });

      if (path === '/') {
        const localType = schema.types.some(t => /LocalBusiness|ProfessionalService|Organization/i.test(t));
        if (!localType) fail(`homepage lacks organization/local-business JSON-LD; types=${schema.types.join(',')}`);
        if (!dom.tel.some(h => h.includes('905469364271'))) fail('homepage canonical phone tel link missing');
        if (!dom.whatsapp.some(h => h.includes('905469364271'))) fail('homepage canonical WhatsApp link missing');
      }
      if (path === '/iletisim/' && !dom.tel.some(h => h.includes('905469364271'))) {
        fail('contact phone tel link missing');
      }

      await page.close();
      await sleep(650);
    }
    await context.close();
  }
} finally {
  await browser.close();
}

report.status = report.failures.length === 0 ? 'PASS' : 'FAIL';
fs.mkdirSync(new URL('../.ops/', import.meta.url), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ status: report.status, failures: report.failures.length, warnings: report.warnings.length, pages: report.pages.length }, null, 2));
if (report.status !== 'PASS') process.exit(1);
