# Class Reklam Tabela — SEO Baseline (2026-08-14)

> Status: **IN PROGRESS / NOT ACCEPTED**  
> Acceptance state: **FAIL-CLOSED until fresh branch audit completes**

## 1. Scope and source-of-truth rules

Site: `https://classreklamtabela.com.tr/`  
Repository: `tayfunates10/classreklam-wp-ops`  
Default branch: `main`  
Baseline main HEAD: `b2f2c71eec1ae806a013095279573ac44ed08402`  
SEO working branch: `seo/full-seo-optimization`

This repository is an operational WordPress automation/audit repository, not a checked-in WordPress theme source tree. Production WordPress changes are performed through authenticated WordPress REST/Rank Math operations in GitHub Actions workflows.

Evidence hierarchy used in this audit:

1. Fresh authenticated WordPress REST + Rank Math head output — authoritative when available.
2. Fresh public HTTP evidence — authoritative for public response behavior when WAF does not intercept it.
3. Existing `.ops` evidence captured on 2026-08-10 — historical evidence, not automatically treated as current.
4. Current search-engine/web index samples — useful for index visibility and SERP intent, but may lag WordPress source changes.

No fabricated GSC, GA4, Lighthouse, ranking or search-volume numbers are permitted.

## 2. Data availability

| Data source | Status | Notes |
|---|---|---|
| GitHub repository | AVAILABLE | Read/write access confirmed |
| WordPress authenticated REST | PENDING FRESH RUN | Historical successful evidence exists from 2026-08-10 |
| Rank Math generated head | PENDING FRESH RUN | Fresh branch collector added |
| Public HTTP from GitHub runner | PENDING FRESH RUN | Imunify360 has intermittently challenged automation IPs |
| Search-engine/web index samples | AVAILABLE | Results can be stale; no exact Google ranking claims |
| Google Search Console | DATA NOT AVAILABLE | No verified GSC connector/export in this session |
| Google Analytics | DATA NOT AVAILABLE | No verified analytics connector/export in this session |
| Google Business Profile | DATA NOT AVAILABLE | No verified GBP connector/export in this session |
| Lighthouse / field CWV | DATA NOT AVAILABLE | No fresh executed measurement yet |

## 3. Repository / WordPress inventory baseline

Historical authenticated inventory (2026-08-10) recorded:

- WordPress canonical site URL: `https://classreklamtabela.com.tr`
- Front page ID: `6`
- Posts page ID: `14`
- Active SEO plugin: Rank Math SEO
- Active content/layout plugin: Kadence Blocks
- WPCode Lite present
- Custom reference post type exists (`cr_reference`)
- Main operational paths: `.github/workflows`, `.ops`, `scripts`

Active theme and fresh active-plugin versions are intentionally **not asserted as current** until the new read-only baseline run completes.

## 4. Current commercial architecture

Dedicated commercial pages evidenced in WordPress history:

- `/edremit-tabela/`
- `/totem-tabela/`
- `/dijital-baski/`
- `/arac-giydirme/`
- `/cam-giydirme/`
- `/kutu-harf-tabela/`

Core pages:

- `/`
- `/hizmetlerimiz/`
- `/hakkimizda/`
- `/iletisim/`
- `/blog/`
- public references archive `/referanslar/`

Historical live verification confirms all six commercial service URLs were linked in the footer. The homepage also historically contained links to all six service pages.

## 5. Local business baseline

Public contact-page index sample currently exposes:

- Business: Class Reklam
- Phone: `0546 936 42 71`
- Email: `classreklam0@gmail.com`
- Instagram: `@classreklaam`
- Address: `Hamidiye Mh. Mithatpaşa Cd. NO: 18/C 10300 Edremit/Balıkesir`

Historical LocalBusiness implementation uses the same phone and address and limits `areaServed` to Edremit / Balıkesir. Fake ratings, fake reviews, fake prices and unverified branches are prohibited.

GBP parity is **DATA NOT AVAILABLE** until verified GBP data is supplied/connected.

## 6. Search-intent / SERP observations

Current sampled search results for Edremit commercial terms show a strong local-service intent. Competing results commonly use a service-oriented homepage or service hub and expose broad service menus, project proof and direct contact information.

Observed competitor patterns:

- Edit Reklam: broad Edremit tabela + folyo + dijital baskı + araç giydirme service architecture and project examples.
- tabela-reklam.net: broad local homepage with many explicit service categories and contact details.
- Maksimum Reklam: broad Edremit tabela/dijital baskı architecture with many service subtypes and project imagery.
- Marketplace results (for example Armut) also compete on service-specific local queries such as vehicle wrapping.

No exact Google position is recorded because a verified Google Search Console/Google SERP rank source is not available in this session.

## 7. Keyword → URL intent map

| Keyword cluster | Intent | Target URL | State | Priority |
|---|---|---|---|---|
| Edremit reklam firması / reklam tabela firması | Local / transactional | `/` | Existing | P1 |
| Edremit tabela / tabela yaptırma | Local / transactional | `/edremit-tabela/` | Existing | P1 |
| Edremit totem tabela | Local / transactional | `/totem-tabela/` | Existing | P1 |
| Edremit dijital baskı | Local / transactional | `/dijital-baski/` | Existing | P1 |
| Edremit araç giydirme / araç kaplama reklam | Local / transactional | `/arac-giydirme/` | Existing | P1 |
| Edremit cam giydirme / vitrin folyo | Local / transactional | `/cam-giydirme/` | Existing | P1 |
| Edremit kutu harf tabela | Local / transactional | `/kutu-harf-tabela/` | Existing | P1 |
| tabela seçimi / tabela malzemeleri / montaj | Informational | Blog topic cluster | Existing | P2 |
| dijital baskı / branda / dış mekan baskı rehberleri | Informational | Blog topic cluster | Existing | P2 |
| araç giydirme / araç kaplama rehberleri | Informational | Blog topic cluster | Existing | P2 |

Important cannibalization rule: the homepage should remain the broad **reklam firması / multi-service** entity page while `/edremit-tabela/` should own the more specific **Edremit tabela** service intent. Fresh Rank Math titles/descriptions must be checked before changing either URL.

## 8. Historical fixes that must not be repeated blindly

Existing 2026-08-10 evidence shows that the following work was already performed:

- Six dedicated service landing pages created and populated.
- Contact + six service pages received H1 fixes.
- LocalBusiness marker/schema was added to the homepage.
- Contextual blog → service internal links were added.
- Six service links were verified in the live footer.
- 20 blog posts were reorganized into five topical categories:
  - `tabela-rehberi`
  - `dijital-baski-rehberi`
  - `arac-giydirme-rehberi`
  - `folyo-cam-giydirme`
  - `reklam-rehberi`
- `Uncategorized` was deleted by the taxonomy fix.

These are historical PASS results only. The new audit rechecks current state where technically possible.

## 9. Current risk / opportunity register

| ID | Priority | Finding | Impact | Risk | Effort | State |
|---|---|---|---|---|---|---|
| T-01 | P0 candidate | HTTP and `www` host normalization was not proven by the previous WAF-intercepted audit; historical runner saw 200/challenge rather than a redirect | High | High if changed blindly | Medium | FRESH VERIFY REQUIRED |
| T-02 | P1 | Public/search index samples still show pre-2026-08-10 homepage title/H1/content | High | Low | Low/Medium | INDEX/CACHE REVALIDATION REQUIRED |
| T-03 | P1 | Search-index samples of older blog pages show `Uncategorized` and duplicate visible H1s | Medium/High | Medium | Medium | SOURCE REVALIDATION REQUIRED |
| T-04 | P1 | WordPress inventory historically exposed `/referans-isler/` while the public indexed references archive is `/referanslar/` | Medium | Medium | Low/Medium | REDIRECT/CANONICAL VERIFY REQUIRED |
| T-05 | P1 | Homepage vs `/edremit-tabela/` primary-query ownership can cannibalize if both target the same exact focus/title intent | High | Medium | Low | RANK MATH HEAD VERIFY REQUIRED |
| T-06 | P1 | Imunify360 intermittently blocks GitHub automation and can make tests return challenge pages as HTTP 200 | High QA impact | Medium | Hosting-dependent | OPEN |
| T-07 | P2 | Fresh robots.txt and Rank Math sitemap output not yet captured in this run | High technical | Low | Low | PENDING |
| T-08 | P2 | Fresh theme/plugin inventory not yet captured | Medium | Low | Low | PENDING |
| T-09 | P2 | Fresh mobile/Lighthouse/CWV execution unavailable | Medium/High | Low | Medium | DATA NOT AVAILABLE |
| T-10 | P2 | GSC query/page/CTR/position opportunity table cannot be truthfully produced | High strategy | Low | External access | DATA NOT AVAILABLE |

## 10. Branch implementation performed in this work

Production-safe repository changes already committed to `seo/full-seo-optimization`:

1. `scripts/full_seo_baseline_queryrest.py`
   - read-only authenticated WordPress inventory
   - redacted safe settings only
   - active plugins/theme inventory
   - page/post/category inventory
   - homepage H1/schema marker audit
   - Rank Math generated head checks for critical URLs
   - host variant checks
   - robots/sitemap checks
   - reference/legacy-reference URL checks

2. `.github/workflows/full-seo-baseline.yml`
   - branch-only execution
   - no WordPress write operation
   - evidence committed only to the SEO branch

3. `scripts/seo_acceptance_gate.py`
   - fail-closed canonical/site URL checks
   - critical commercial-page presence checks
   - homepage H1 gate
   - title/description/canonical/robots checks on critical URLs
   - host redirect normalization checks
   - robots/sitemap checks
   - legacy references consolidation check
   - WAF-obscured checks become `INDETERMINATE`, never false PASS

No production content, DNS, Rank Math metadata, redirects or WordPress settings were changed by this branch work.

## 11. Test status

| Test | Status | Evidence |
|---|---|---|
| Repo access / branch creation | PASS | `seo/full-seo-optimization` created from baseline main HEAD |
| Audit collector committed | PASS | Git commit exists on SEO branch |
| Sensitive settings redaction | PASS (code review) | Collector allowlists safe settings only |
| Fail-closed acceptance gate committed | PASS | Git commit exists on SEO branch |
| Fresh GitHub Actions baseline | PENDING / QUEUED | GitHub has created workflow runs but runner has not started |
| Fresh WordPress REST inventory | NOT RUN YET | Depends on queued runner |
| Fresh Rank Math head validation | NOT RUN YET | Depends on queued runner |
| Fresh robots/sitemap validation | NOT RUN YET | Depends on queued runner |
| Fresh host redirect validation | NOT RUN YET | Depends on queued runner |
| Production SEO changes | NOT PERFORMED | Intentionally blocked until fresh baseline/gates |
| Deployment | NOT PERFORMED | No safe acceptance PASS yet |
| Post-deploy validation | NOT PERFORMED | No deploy performed |

## 12. Acceptance decision

**SEO is NOT complete.**

The current branch must not be merged/deployed as a “completed SEO” change until a fresh read-only baseline is produced and the acceptance gate either passes or produces concrete failures that can be fixed and re-tested.

The largest immediate decision points after fresh evidence are:

1. confirm canonical host redirects (`http` and `www` → canonical HTTPS non-www),
2. confirm robots + sitemap,
3. confirm current Rank Math head for homepage and six service URLs,
4. resolve `/referans-isler/` vs `/referanslar/` if still duplicated,
5. verify whether blog duplicate H1 exists in current WordPress source,
6. split homepage broad local-advertising intent from `/edremit-tabela/` service intent if current metadata still overlaps,
7. run fresh mobile/performance validation before production acceptance.
