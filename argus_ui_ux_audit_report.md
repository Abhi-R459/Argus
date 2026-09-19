# Argus Frontend — UI/UX Audit Report (HR Admin + Compliance Auditor portals)

**Prepared for:** Product / Frontend ownership
**Scope:** `frontend/` — all 48 source files (`.tsx`, `.ts`, `.css`), 8,771 lines, plus `tailwind.config.js`, `postcss.config.js`, `index.html`
**Status:** Read-only audit. **No application code was modified.**
**Branch observed:** `feature/abhinav-core`

---

## 0. How this audit was performed (and why you can trust the findings)

Every line of the frontend was read. Findings are not opinions — the two most damaging categories were **proven mechanically**:

1. **Silent CSS failures.** Every Tailwind class used in the codebase was checked against the *actual compiled stylesheet*. I compiled `src/index.css` through the project's real `tailwind.config.js` (Tailwind 3.4.4) in memory and asserted, class by class, whether a rule is emitted. Result: **~90 class usages across the app produce no CSS at all.** They look correct in code review and render as nothing.
2. **Contrast failures.** All foreground/background token pairs actually used were measured with the WCAG 2.1 relative-luminance formula. Several ship below the 4.5:1 AA threshold, including the hover state of the primary button.

Reproduce either check at any time — see Appendix A.

### Severity legend

| Level | Meaning |
|---|---|
| **P0 – Broken** | Renders wrong or invisible today. Fix first. |
| **P1 – Unprofessional** | Visible quality/consistency defect a reviewer will notice immediately. |
| **P2 – Polish** | Refinement that separates "good" from "enterprise-grade". |

### Executive summary

The application's *information architecture and domain modelling are strong*: the two portals are genuinely distinct, the audit/chain/forensic concepts are well expressed, keyboard navigation, error boundaries, reduced-motion support and empty states all exist. The gap to "enterprise-grade" is almost entirely **a broken styling foundation plus inconsistent application of it**:

- The elevation system does not exist (`shadow-xs` / `shadow-2xs` — **69 usages** — generate no CSS in Tailwind 3.4.4).
- The entire motion system for panels/drawers does not exist (`animate-in`, `slide-in-from-*` — 8 usages — require `tailwindcss-animate`, which is not installed).
- Four spacing/padding classes silently collapse layout (`p-4.5`, `h-4.5`, `h-9.5`, `py-0.2`), including **all card padding inside the HR employee drawer** and **the height of every large button**.
- Three design-token names are used but undefined (`text-linear-ink-secondary`, `text-grafana-ink`), so text falls back to inherited colour — in the two portal-mounted modals, near-white text on a white card.
- The HR portal is styled with raw Tailwind palette colours (`slate`, `emerald`, `blue`, `amber`, `rose`) while the Auditor portal uses named tokens — so the two portals cannot share a system and have already drifted (same semantic, different colour in 9 places).
- The primary button's **hover** state fails WCAG (2.87:1), as do the orange CTA (2.91:1), green success button (3.17:1), emerald salary button (3.77:1), and all 28 uses of `text-slate-400` as text (2.56:1).

Fix the token/class foundation (a ~1-day change) and most P1 issues in this document disappear automatically; the rest is consistency work in individual components.

---

## 1. P0 — Critical defects (visible today, every page)

| # | Defect | Evidence | Blast radius | Fix |
|---|---|---|---|---|
| F-01 | **No elevation anywhere.** `shadow-xs` and `shadow-2xs` are not part of Tailwind 3.4.4's shadow scale (they were introduced in v4). Verified absent from compiled CSS. | 38 × `shadow-xs`, 31 × `shadow-2xs` (`tailwind.config.js` has no `boxShadow` extension) | Every card, table, panel, button in both portals | Add to `theme.extend.boxShadow`: `'2xs': '0 1px 2px rgba(16,24,40,0.05)'`, `'xs': '0 1px 3px rgba(16,24,40,0.08), 0 1px 2px rgba(16,24,40,0.04)'` — or standardise on `shadow-sm`/`shadow` and delete the tokens. |
| F-02 | **HR drawer cards have zero padding.** `p-4.5` emits nothing, so children sit flush against the card border. | `components/hr/EmployeeSheet.tsx:338, 389, 425, 614` | The 3 main cards in *Overview* + the compensation card in *Compensation* tab | Use `p-4` or add `4.5` to `theme.extend.spacing`. |
| F-03 | **Large buttons have no height.** `h-9.5` / `w-9.5` emit nothing, so `size="lg"` and `size="icon-lg"` collapse to text height. | `components/common/Button.tsx:71, 75` | `ExportControl` download CTA, `ConcurrencyLab` "Start Simulation", any future `lg` button | Change to `h-9`/`h-10` (or add `9.5` to spacing). |
| F-04 | **Header/sidebar icons are 24px in a 32px box** — `w-4.5 h-4.5` emits nothing, so lucide's default `24px` applies and the glyph crowds/overflows its container. | `layouts/HRAdminLayout.tsx:26`, `layouts/AuditorLayout.tsx:68`, `components/auditor/ChainVisualization.tsx:209` | Both portal logos, all 6 sidebar nav icons' active state, chain actor avatars | Use `w-4 h-4` / `w-5 h-5`. |
| F-05 | **The drawer/panel motion system is dead.** `animate-in`, `fade-in`, `slide-in-from-right`, `slide-in-from-bottom-4` come from `tailwindcss-animate`, which is **not** in `package.json` (`plugins: []`). Drawers, sheets and page transitions snap open with no transition. | `DetailSheet.tsx:125, 132, 181, 184`; `AuditLogPage.tsx:5`; `ConcurrencyLab.tsx:73`; `EmployeeSheet.tsx:319`; `AuditChainPage.tsx:496` | All slide-overs, drawers, the audit-log page enter, the freeze banner | Either install + register `tailwindcss-animate`, or replace with the already-defined `animate-modal-enter` / define `keyframes` for `panel-in` in `index.css`. Also `backdrop-blur-xs` (4 uses) does not exist in v3 → the intended scrim blur is missing. |
| F-06 | **Undefined token → invisible text.** `text-grafana-ink` is not defined (`grafana` has `orange`, `blue`, `neutral`, `surface`, `border`). 17 usages; the two portal-mounted modals inherit `body`'s `text-linear-ink` (`#f7f8f8`, near-white) because `React.createPortal` moves them outside `.portal-hr`, producing **white headings/labels on a white card**. | `forms/EmployeeEditForm.tsx` (9), `forms/SalaryForm.tsx` (5), `common/ErrorBoundary.tsx:59`, `common/LiveStreamBadge.tsx:39,43` | HR edit/salary modals (currently unreferenced — see F-20), HR error boundary, HR live badge | Replace with `text-slate-900`; and stop using Grafana tokens in the HR portal at all. |
| F-07 | **Undefined token → wrong text weight/colour.** `text-linear-ink-secondary` is not defined (only `DEFAULT`, `muted`, `subtle`, `tertiary`). Subtitles inherit `text-linear-ink`, rendering **bright white** instead of muted, which makes page subtitles compete with the H1. | `pages/auditor/AuditLogPage.tsx:9`, `pages/auditor/AnalyticsPage.tsx:9` | Two auditor page subtitles | Use `text-linear-ink-muted` (or add the token). |
| F-08 | **Filter-bar divider renders as a bright line.** `border-inherit/40` is invalid (Tailwind cannot apply an opacity modifier to `inherit`) → verified absent → `border-color` falls back to `currentColor`, i.e. near-white in the auditor portal. | `components/common/FilterBar.tsx:47` | Every `FilterBar` in both portals once a filter is active | Use `border-t border-linear-hairline` (auditor) / `border-slate-100` (HR), or a token-driven divider. |
| F-09 | **`py-0.2` is invalid** (8 usages) → badges/pills have no vertical padding and look "cut" against their borders. | `AuditLogTable.tsx:108`, `ExportControl.tsx:66`, `SecurityPosture.tsx:99,125,151`, `TimeTravelView.tsx:255`, `EmployeeSheet.tsx:674` | Severity/operation/tamper badges, `code` chips | `py-0.5`. |
| F-10 | **Primary button hover fails WCAG.** White on `#828fff` = **2.87:1** vs white on `#5e6ad2` = 4.70:1. Hovering *reduces* legibility below AA. | `Button.tsx` auditor `primary` variant; `linear.primary.hover` in `tailwind.config.js` | Every auditor primary button, sidebar CTA, "Catch Up", "Jump", "Run Verification" | Make hover *darker* (`#4f5ac2`) or keep `#5e6ad2` and change only the border/shadow. |
| F-11 | **Primary link text is under AA at 11–12px.** `#5e6ad2` on `#010102` = **4.44:1**; it is used for hash links, "Full Chain Explorer", inline `code`, `Set Now`, "Change". | auditor tables, `TimeTravelView`, `QueryPanel`, `SecurityPosture` | Dense forensic UI where this colour carries meaning | Lighten the link colour (`#8b93e8`) or upgrade text size/weight. |
| F-12 | **`text-slate-400` as body/label text = 2.56:1** (2.45:1 on `bg-slate-50`). Used 28× for real information: "Hired:", `#employee_id`, department icon, relative timestamps, "PII Encrypted", helper copy. | `EmployeeTable`, `Dashboard`, `EmployeeSheet`, `HRSettings` | HR portal readability | Minimum `text-slate-500` (4.76:1) for text; reserve `slate-400` for decorative icons only. |
| F-13 | **Filled orange / green / emerald buttons fail AA.** White on `#ff671d` = 2.91:1; `#27a644` = 3.17:1; `emerald-600` = 3.77:1. | `AuditorLayout` incident CTA, `ExportControl` selected tab, `EmployeeSheet` "Adjust Salary"/"Record Salary Adjustment" | Every high-stakes action label | Use a dark ink label on light tints, or darken the fills (`#c2410c`, `#15803d`) for white text. |
| F-14 | **Sticky table headers never stick.** `DataTable.Header` uses `sticky top-0`, but its scroll container is the sibling `overflow-x-auto` wrapper (which has no vertical scroll), and the outer `Root` is `overflow-hidden`. Additionally `no-scrollbar` hides the horizontal scrollbar, so on <1400px the right-hand columns are cut off with **no affordance that they scroll**. | `components/common/DataTable.tsx:16–21, 41–42` | Employee directory, Audit Log, Chain Explorer | Move vertical scrolling (and `max-h`) to the table wrapper, or drop `sticky`; keep a visible thin scrollbar for horizontally overflowing tables. |
| F-15 | **Keyboard "focus" looks like a permanent selection.** `focusedRowIndex` initialises to `0`, so row 0 is rendered with the *selected* style on load in both tables, and the HR table adds `ring-1 ring-slate-400` while the auditor table uses a primary-blue left border — two different languages for the same state. | `EmployeeTable.tsx` (`ring-1 ring-inset ring-slate-400`), `AuditLogTable.tsx:186`, `DataTable.tsx:104–138` | Both directories/logs | Start at `-1` (nothing focused) and use one shared focus treatment. |

---

## 2. Class-level defect inventory (verified against compiled CSS)

All classes below are used in source and produce **no CSS rule**. Verified by compiling `index.css` with the project's Tailwind config.

| Class | Uses | Why it fails | Visual consequence | Replacement |
|---|---|---|---|---|
| `shadow-xs` | 38 | Not in Tailwind 3 shadow scale | No elevation on cards/buttons | `shadow-sm` or token (F-01) |
| `shadow-2xs` | 31 | Not in Tailwind 3 shadow scale | No elevation on chips/rows | token or `shadow-sm` |
| `text-linear-ink-secondary` | 2 | Token does not exist | Subtitle renders near-white (F-07) | `text-linear-ink-muted` |
| `text-grafana-ink` | 17 | Token does not exist | Near-white text on white card (F-06) | `text-slate-900` |
| `h-9.5` / `w-9.5` | 2 | `9.5` not in default spacing scale | `lg` buttons lose height (F-03) | `h-9`/`h-10` |
| `p-4.5` | 4 | `4.5` not in spacing scale | Drawer cards have 0 padding (F-02) | `p-4` |
| `w-4.5` / `h-4.5` | 3 | `4.5` not in spacing scale | Icons render at 24px in 32px boxes (F-04) | `w-4 h-4` / `w-5 h-5` |
| `py-0.2` | 8 | `0.2` not in spacing scale | Badges have no vertical padding (F-09) | `py-0.5` |
| `border-inherit/40` | 1 | Opacity modifier unsupported on `inherit` | Bright divider line (F-08) | explicit border colour |
| `backdrop-blur-xs` | 4 | Not in Tailwind 3 blur scale | Drawer scrims are not blurred | `backdrop-blur-sm` |
| `animate-in` `fade-in` `slide-in-from-right` `slide-in-from-bottom-4` | 8 | Requires `tailwindcss-animate` plugin (not installed) | No panel/drawer motion (F-05) | install plugin *or* define local keyframes |
| `animate-drawer-in` / `animate-drawer-out` | 0 | Defined in `tailwind.config.js` but **never used** | — | dead config; remove or adopt in `DetailSheet` |

**Aggregate:** ~90 class usages, touching every screen in the product. This single category is the largest single cause of the "unpolished" impression.

---

## 3. Colour system audit

### 3.1 There is no shared token layer for the HR portal

`tailwind.config.js` defines exactly two systems: `linear.*` (dark) and `grafana.*` (light observability). The **Auditor** portal consumes `linear.*` consistently. The **HR** portal consumes nothing — it is written directly in raw Tailwind palette values: `slate-*`, `emerald-*`, `blue-*`, `amber-*`, `rose-*`. Consequences:

- No way to theme/rebrand the HR portal centrally; every colour change is a find-and-replace.
- The HR portal has accumulated **five accent families**: slate (primary actions), emerald (positive/security), blue (KPIs/keys), amber (warnings), rose (errors). They are used inconsistently (see 3.2).
- The `grafana.*` tokens are being used inside a **third** context — the HR portal (`forms/EmployeeEditForm.tsx`, `forms/SalaryForm.tsx`, `common/LiveStreamBadge.tsx`, `common/ErrorBoundary.tsx`, `common/SkeletonRows.tsx`, `common/RefreshButton.tsx`) — which is why `text-grafana-ink` (undefined) surfaced at all.

**Recommendation:** add a `portal` namespace (`surface`, `canvas`, `hairline`, `ink`, `ink-muted`, `ink-subtle`, `primary`, `success`, `warning`, `danger`) mirroring `linear.*`, and migrate HR to it. Keep `grafana.*` for Grafana-embedded views only, or retire it.

### 3.2 The same semantic state gets different colours in different screens

| Semantic | HR Dashboard / Table | Audit Log | Chain Explorer | Time Travel | Chain Visualization |
|---|---|---|---|---|---|
| INSERT / New hire | emerald-50/700 | `linear-success` | `linear-success` | `linear-success/15` | `linear-success` |
| UPDATE / Profile update | slate-100/700 | `linear-primary` | `linear-primary` | **`amber-500/15`** | `linear-primary` |
| DELETE / Deactivated | **amber-50/700** | **`grafana-orange`** | **`grafana-orange`** | `grafana-orange` | `grafana-orange` |
| Warning severity dot | — | `linear-primary` | **`amber-400`** | — | **`linear-primary`** |
| High severity dot | — | — | **`orange-400`** | — | **`grafana-orange`** |
| Critical severity dot | — | `grafana-orange` | `grafana-orange` | — | `grafana-orange` |

Four independent copies of these maps exist (`AuditLogTable.tsx:26–42`, `ChainVisualization.tsx:10–25`, `pages/auditor/AuditChainPage.tsx:27–38`, `TimeTravelView.tsx` timeline badge ternary) and they **disagree**. `AuditLogTable`'s `WARNING` vs `CRITICAL` differ only by `opacity` and `font-semibold` — indistinguishable at a glance in a compliance tool.

**Recommendation:** one `lib/semantics.ts` exporting `actionStyle`, `severityDot`, `severityChip`; a documented palette where WARNING = amber, CRITICAL = orange, INFO = subtle — applied in all five places.

### 3.3 Severity colours that are visually indistinguishable

`AuditChainPage.tsx:33–38` maps `medium → bg-amber-400 (#fbbf24)`, `high → bg-orange-400 (#fb923c)`, `critical → bg-grafana-orange (#ff671d)` — three adjacent oranges at 1.5px diameter. In `ChainVisualization.tsx:16–21`, `high` and `critical` are **literally the same colour** while `medium` is lavender. This is exactly the "colour cutting in the wrong place" pattern.

### 3.4 Non-token colours inside the Linear dark portal

The dark portal is otherwise rigorously tokenised, then breaks out to raw palette values that were designed for light backgrounds:

- `text-sky-400` (AuditChainPage "External Anchor" metric), `text-amber-400` ("Navigation Window" metric), `bg-amber-400`/`bg-orange-400` (severity), `bg-amber-500/15 text-amber-400` (TimeTravel UPDATE badge), `bg-emerald-500/10 text-emerald-400` / `bg-rose-500/10 text-rose-400` (TimeTravel employee status pills), `bg-rose-500/15 … text-rose-400` (Button `danger`).
- Result: the auditor portal has **two "danger" colours** (`grafana-orange` and `rose-500`), **two "positive" colours** (`linear-success` and `emerald-400`), and uses amber for two unrelated meanings (metric decoration vs severity).

### 3.5 Semantic misuse

- `ExportControl`: the entire card is washed in `linear-success` green and the format tabs use `bg-linear-success text-white`. Green is the *verified/intact* signal in this product; using it for "export" dilutes the one colour that means "the chain is safe".
- HR Dashboard KPI icons: blue (personnel), emerald (ledger), amber (flags) — fine in principle, but blue appears in exactly one place in the HR portal (KPI + the security card in Settings) and nowhere else, so it reads as an accident rather than a system.
- `RefreshButton` spins with `text-grafana-orange` even in the HR portal (`Dashboard.tsx`), introducing an orange that exists nowhere else in HR.

### 3.6 Contrast measurements (computed, WCAG 2.1)

| Foreground / background | Ratio | AA (4.5) | Where |
|---|---|---|---|
| `#94a3b8` on `#ffffff` (`slate-400` on white) | **2.56** | ✗ | 28 usages, HR portal |
| `#94a3b8` on `#f8fafc` | **2.45** | ✗ | `EmployeeSheet` helper text |
| `#ffffff` on `#828fff` (primary hover) | **2.87** | ✗ | every auditor primary button on hover |
| `#ffffff` on `#ff671d` (grafana orange) | **2.91** | ✗ | incident CTA, ExportControl/StatusBanner |
| `#ffffff` on `#27a644` (`linear-success`) | **3.17** | ✗ | ExportControl tabs, success button variant |
| `#8c8ca1` on `#ffffff` (`grafana-neutral`) | **3.29** | ✗ | shared components + dead modals |
| `#62666d` on `#010102` (`ink-tertiary`) | **3.62** | ✗ | ChainVisualization placeholders, chevrons |
| `#ffffff` on `#059669` (`emerald-600`) | **3.77** | ✗ | HR salary CTAs |
| `#5e6ad2` on `#010102` (`linear-primary`) | **4.44** | ✗ (marginal) | all auditor links / hash buttons |
| `#64748b` on `#ffffff` (`slate-500`) | 4.76 | ✓ | HR secondary text |
| `#ffffff` on `#5e6ad2` | 4.70 | ✓ (marginal) | primary buttons |
| `#8a8f98` on `#010102` (`ink-subtle`) | 6.42 | ✓ | auditor secondary text |
| `#d0d6e0` on `#0f1011` (`ink-muted`) | 13.04 | ✓ | auditor body text |

---

## 4. HR Admin portal — page-by-page findings

### 4.1 `layouts/HRAdminLayout.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-16 | **Three status indicators in one 64px header**: an "Operational" emerald pill with `animate-pulse`, a "LIVE" chip with a green label, and `RealtimeClock`'s own `animate-ping` dot — plus a fourth pulsing dot in the sidebar footer. Four simultaneous motion/status signals for one fact. | P1 | Keep one: a single status dot + clock. Drop the "LIVE" prefix and the "Operational" pill (the sidebar footer already states engine health). |
| F-17 | **Three names for one page.** Sidebar = "Employees", breadcrumb = "Employees" (derived from `pathname`), page H1 = "Workforce Directory". Same for "Dashboard" vs "Workforce Overview". | P1 | Single source of truth: one `navTitle` per route, rendered in the header; drop page-level H1s or make them identical. |
| F-18 | **No responsive shell.** `w-64` sidebar is always rendered; no hamburger, no drawer, no collapsed rail. `h-screen` + `overflow-hidden` means <768px the sidebar consumes the viewport and content is pushed off-canvas with no way to reach it. | P0 | Add a collapse breakpoint: `<1024px` → off-canvas sidebar with a trigger; use `h-dvh`. |
| F-19 | Sidebar footer "Argus Core Engine / Operational • Full Access" is static marketing copy, not bound to any health check; the sidebar's active state (`bg-slate-100` + `border-slate-200/80` on white) is a very low-contrast indicator. | P2 | Bind to a real health signal or remove; strengthen the active state (`bg-slate-900/5` + weight + left accent). |
| — | `text-[10px]` for the "HR ADMIN" chip and "Workforce Management" group label — below comfortable legibility. | P2 | 11–12px minimum. |

### 4.2 `pages/hr/Dashboard.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-20 | **Static integrity claims presented as live data.** "Cryptographically Sealed" and "Chain Intact" are hardcoded strings — not derived from `data`. The HR portal asserts chain integrity that it does not verify. | P1 (trust) | Either fetch real status or reword to a non-claim ("All events recorded"). |
| F-21 | **Activity badges disagree with the auditor portal** (see 3.2): `DELETE` is amber here, orange in the auditor, and `salary_history` gets its own blue "Compensation" label that exists nowhere else. | P1 | Share the semantics map (3.2). |
| F-22 | **Manual refresh competes with a 3s poll.** `refetchInterval: 3000` + a "Refresh" button + a "syncing…" indicator = three mechanisms for the same job; the spinner state flickers. | P2 | Keep the poll, drop the button, or make refresh explicit (`staleTime` + manual). |
| F-23 | Activity row alignment is patched with `pl-14 sm:pl-0` to fake an indent that lines up with the badge column; at `sm` the timestamp jumps columns. | P2 | Use a real 2-column grid so the timestamp column is stable. |
| F-24 | "View Full Employee Directory" (link variant) renders a `rightIcon` with `ml-1` **and** a wrapper span → double gap; the same destination is also a primary button in the header. | P2 | One CTA per destination. |

### 4.3 `pages/hr/EmployeeList.tsx` + `components/EmployeeTable.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-25 | **Filter counts and pagination contradict each other.** Department/status are filtered **client-side after server pagination**, while the footer prints "Showing 1–12 of 240 employees" from the server. Filtering to a department with 2 matches on page 3 shows "2 records" next to "Showing 25–36 of 240". | P0 (correctness of UI) | Push `department`/`status` into the query string so the server filters; then counts and pages agree. |
| F-26 | **Column header/content mismatch.** "Annual Compensation" column also carries "Hired: …" (two unrelated fields in one column); "Security & Status" contains a status pill plus the static, identical-on-every-row "PII Encrypted" label — pure noise repeated 12× per page. | P1 | Split into "Compensation" + "Onboarded"; replace the per-row badge with a single page-level assurance note or a column tooltip. |
| F-27 | **Row density fights itself.** `DataTableRow` sets `h-9` (36px) while the row contains a 32px avatar plus two stacked text lines with `py-2` — the real content height is ~46px, so `h-9` is meaningless and the avatar has 2px of breathing room. | P1 | Row height 44–48px for two-line cells, `h-9` for single-line only. |
| F-28 | Row action targets are **`icon-xs` = 24×24px** — below the 32–44px minimum, three of them adjacent, unordered by risk: salary (emerald) → edit (slate) → inspect (secondary). | P1 | 28–32px targets, consistent order (Inspect → Edit → Compensation), and don't colour a *navigation* action emerald. |
| F-29 | The same "Deactivated" state is amber in the toolbar segmented control and slate-grey in the row chip; the segmented control also colours its active label (emerald/amber) while the "All" segment is slate — three colours for one control. | P1 | One neutral active state (white pill + slate-900 text); move status colour into the row chip only. |
| F-30 | Filter icons are inconsistent: `Search` 3.5, `Building2` 3.5, `Filter` 3, and the segmented control has no focus-visible styling at all (the only interactive control in the app with none). | P1 (a11y) | One icon size, add `focus-visible:ring-2`. |
| F-31 | The clear-search `×` button uses `focus-visible:outline-none` with no replacement ring; it is also a raw `×` character while every other close affordance uses the `X` icon. | P1 (a11y) | `X` icon + visible focus ring. |
| F-32 | ID format is three-way inconsistent: `#12` (table), `EMP-0012` (drawer subtitle), `#EMP-0012` (Time Travel). Currency is two-way: `₹85,000` (table/sheet, `maximumFractionDigits: 0`) vs `₹85,000.00` (Time Travel). | P1 | One formatter module: `formatEmployeeRef()`, `formatINR()`. |
| F-33 | No sortable columns, no column visibility control, no bulk selection in a "Workforce Directory" — the table is read-only-ish despite 3 action buttons per row. | P2 | Sortable headers (the sticky header is already there), row selection + bulk deactivate. |
| F-34 | Pagination panel only appears when `pages > 1`; with client-side filtering active the count line disappears entirely, so filtering to 3 rows shows **no** footer context. | P2 | Always render the footer with the current range + page size selector (12 is hardcoded). |

### 4.4 `components/hr/EmployeeSheet.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-35 | `p-4.5` → **0 padding** on the three Overview cards and the Compensation summary card (F-02). The single most visible HR defect. | **P0** | `p-4`. |
| F-36 | **Tab switcher is a third pattern.** HR uses `bg-slate-100/90 p-1 gap-1 rounded-xl border`, RiskPanel uses `bg-linear-canvas p-1 space-x-1 rounded-xl` with `role="tablist"`, ExportControl uses `bg-linear-surface-2 p-1 space-x-1 rounded-xl`. HR's version also lacks `role="tablist"` / `aria-selected`. | P1 | Extract `<SegmentedControl>` and use it in all three. |
| F-37 | **Native `window.confirm()` for a destructive action** — unstyled browser dialog, thread-blocking, inconsistent with the rest of the UI, no typed confirmation, no audit-aware copy. | P1 | Use the existing `DetailSheet`/modal pattern with an explicit consequence sentence. |
| F-38 | **Button variants bypassed with ad-hoc class overrides**: `variant="success"` + `className="bg-emerald-600 hover:bg-emerald-700 text-white"` (twice), `variant="primary"` + `className="bg-slate-900 …"`. The override also breaks the variant's own active/hover contract. | P1 | Add an `emerald`/`accent` variant to the map instead of overriding at call sites. |
| F-39 | Salary tab's "Current annual compensation" card uses `p-4.5` (0 padding) and the emerald CTA is the only emerald-600 fill in the portal (contrast 3.77:1). | P0/P1 | See F-02, F-13. |
| F-40 | Edit tab: switching tabs silently discards dirty form state (no guard, no "unsaved changes" prompt); the role `select`'s first option is labelled "Keep Current: …" so "no change" is indistinguishable from a value. | P1 | Guard `setActiveTab` when `isDirty`; use a disabled placeholder option + explicit "leave unchanged" copy. |
| F-41 | Inputs use `focus:ring-4 focus:ring-slate-900/5` — a 4px, 5%-opacity ring, i.e. an almost invisible focus indicator, while the border jumps to near-black. Everywhere else the app uses 2px rings. | P1 (a11y) | `focus:ring-2 focus:ring-slate-900/15` + keep the border change. |
| F-42 | PII panel shows `•••• •••• ••••` and "AES-256 Symmetric" as static text with `text-slate-400` icons on `bg-slate-50` (2.45:1). | P2 | Raise contrast; consider showing a real masking state from the API. |
| F-43 | "Quick actions" row mixes two `flex-1` buttons with an unlabelled 28px destructive icon button at the far right — a dangerous control in the position users click for "close". | P1 | Move Deactivate into the header overflow menu or the footer, labelled. |

### 4.5 `pages/hr/HRSettings.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-44 | **Misleading copy**: when `twoFactorEnabled` is false the UI still shows "Active (Clerk MFA Enforced)". | P1 (trust) | Show the real state with a warning tone when false. |
| F-45 | Inconsistent page pattern: this page has a header divider (`border-b pb-5`) that Dashboard/EmployeeList lack, and it is constrained to `max-w-4xl` while the other HR pages fill `max-w-7xl` — content width changes as you navigate. | P1 | One page-header primitive, one content width per portal. |
| F-46 | Two visually different `code` chips on the same screen: `bg-slate-200/80 border-slate-300 text-slate-800` (connection card) vs `bg-emerald-50 border-emerald-200 text-emerald-800` (encryption card) for the same kind of token. | P2 | One `<Code>` primitive; colour only when the semantic is real. |
| F-47 | The page duplicates the layout's status chrome and combines blue + emerald + slate accents in adjacent cards. | P2 | See §3.1. |

### 4.6 `components/forms/EmployeeForm.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-48 | The registration drawer is the most-polished HR surface, but its submit button uses `variant="primary"` + `className="bg-slate-900 …"` (redundant override) and it is the only HR form with a `footer` slot; the edit path lives inside a *tab* of a different component. | P1 | Unify: one `EmployeeFormDrawer` with `mode: 'create' \| 'edit'`, footer always. |
| F-49 | 7 fields on one scroll with no grouping/stepper; `National ID` and `Contact` are visually equal-weight to `Full name`, despite very different risk. | P2 | Group as Identity / Assignment / Compensation / Encrypted PII. |
| F-50 | No `autoComplete`, no `inputMode` on the salary field, no required-field indicator, and the date field defaults to "today" silently. | P2 | Add `autoComplete`, `inputMode="decimal"`, required markers. |

---

## 5. Compliance Auditor portal — page-by-page findings

### 5.1 `layouts/AuditorLayout.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-51 | **Five simultaneous attention animations**: sidebar `ALERT` chip (`animate-pulse`), sidebar footer alert dot, a `animate-pulse` `ShieldAlert` in the incident banner, `animate-ping` status dots, and the `animate-pulse` freeze indicator. Attention fatigue destroys the signal. | P1 | One persistent, calm incident affordance; pulse only on state *change*. |
| F-52 | Incident banner markers use `text-white` on `bg-grafana-orange/25` (light-on-mid-tint, weak hierarchy) and stack three orange chips ("CRITICAL SECURITY ALERT", "Tampered Block #n", "External Anchor Mismatch") plus an orange icon tile plus an orange CTA in a 3-line band. | P1 | Reduce to: icon + one-line statement + CTA; move secondary facts into the chain view. |
| F-53 | `flex … hidden md:flex` on the same element — contradictory display utilities that resolve only by Tailwind's internal ordering (`.hidden` sorts after `.flex`; the `md:` variant wins later). Works today by accident. | P2 | Use `hidden md:flex` only. |
| F-54 | Breadcrumb is absent (unlike HR) and `pageTitle` is derived by `pathname.split('/').pop()`: `/auditor/log` → "Log" (nav says "Audit Log"), `/auditor/activity` → "Activity & risk", `/auditor/time-travel` → "Time travel" (`.replace('-', ' ')` only replaces the first hyphen). | P1 | Route→title map (same map used by the nav list). |
| F-55 | Header uses `px-8` while page content is `max-w-7xl mx-auto` with `p-8` — at ≥1440px the title and the page content do not share a left edge; the two portals also disagree on header padding. | P2 | Align header left edge to the content container. |
| F-56 | `w-64` sidebar, no responsive behaviour (same as F-18); `shadow-sm` applied to a dark sidebar where shadows are invisible. | P0/P2 | As F-18; drop shadows on dark surfaces. |
| F-57 | The header badge "Pool: compliance_auditor (Read-Only)" is excellent transparency — but nothing in the UI explains what read-only *prevents*; the nav gives no indication that no write action exists. | P2 | One-line tooltip/copy. |

### 5.2 `pages/auditor/AuditorOverview.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-58 | **Layout shift on load**: the anchor slot renders a `min-h-[220px]` spinner placeholder, then `AnchorStatus` (a taller, `p-5` card) replaces it; the 3-up row reflows. The other two cards use `p-6`, so the row also has three different internal paddings (5 / 6 / 6). | P1 | Skeleton with the real card's dimensions; one card padding token (`p-5`). |
| F-59 | The right-hand "Forensic Incident Queue / Activity & Risk Engine / Open Risk Panel" card duplicates the sidebar item *and* the page title *and* the `RiskPanel`'s own hero card — the same destination is advertised four times on one screen. | P1 | Delete the card; make the sidebar badge the only entry point. |
| F-60 | `text-[10px] uppercase tracking-widest` + `text-lg font-semibold` + body + full-width CTA inside a card that also has an absolute gradient wash and an icon tile: five competing emphasis devices. | P2 | Simplify to icon + title + link. |

### 5.3 `pages/auditor/AuditChainPage.tsx` (831 lines)

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-61 | **Four metric cards with four different icon colours** (lavender / green / sky / amber) in a `rounded-lg` card style that matches nothing else on the page (`rounded-2xl` elsewhere, `rounded-xl` in Time Travel). | P1 | One radius per level; restrict metric icon colours to neutrals + status. |
| F-62 | `text-sky-400` and `text-amber-400` are light-theme palette colours used decoratively inside the dark portal (see 3.4). | P1 | Tokens. |
| F-63 | Metric cards are pure decoration for values already shown elsewhere (block count = table length, integrity = layout banner + freeze banner + hash column). Vertical space spent on redundancy above the fold. | P2 | Collapse to a single status strip. |
| F-64 | The docked inspector is `sticky top-6` inside a `p-8` main, so its top edge sits 8px above the table's top edge — a visible misalignment, and `max-h-[calc(100dvh-3.5rem)]` (56px) does not match the real chrome (64px header + 32px padding), so the panel can overflow the fold. | P1 | `top-8` and `max-h-[calc(100dvh-8rem)]` (or compute from the layout). |
| F-65 | Left pane is `flex-1` with `min-w-0` and the inspector is a **417px** dock at `lg` — at 1024–1280px the 7-column table is compressed until the hash columns wrap/truncate mid-value. | P1 | Dock only at `xl`; below that, use the overlay drawer. |
| F-66 | Inline `(() => { … })()` IIFE inside `footer={}` to compute `empId`, casting `new_value as any` — and the resulting button is always rendered even when no employee id exists (Time-Travel then opens with no target). | P2 | Hoist the computation; disable the action when `empId` is missing. |
| F-67 | Two "Copy" buttons per hash block, each with its own `copiedHash` label comparison (`'drawer_entry_hash'` vs `'drawer_prev_hash'`) plus the table's `hash-${id}` labels — three copy implementations, one of which shows `✓` inside a `<Button>`'s children. | P2 | One `<CopyButton value={…}>` primitive with a transient "Copied" state. |
| F-68 | `title="Click to copy full hash"` and `aria-label="Copy full hash"` are good; but the copy `<Button size="xs">` inside a clickable row also calls `e.stopPropagation()` — the row's `onClick` opens the inspector, so clicking the hash does *not* select the block. Inconsistent with the row's affordance. | P2 | Selecting the block on copy, or make the whole row non-clickable and use an explicit chevron. |
| F-69 | Keyboard hints are printed twice ("Use J/K to navigate, Space to peek") and the global handler `preventDefault()`s **ArrowUp/ArrowDown**, breaking native page scrolling on a long forensic list. | P1 | Restrict arrow-key capture to when the table has focus; add `Home`/`End`; hide hints behind a `?` help affordance. |
| F-70 | `SEVERITY_DOT` medium/high/critical are three near-identical oranges (3.3). | P1 | See §3.3. |

### 5.4 `components/auditor/AuditLogTable.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-71 | Table has **8 columns** inside a `max-w-7xl` container with the scrollbar hidden (F-14): on a 1280px laptop the "Severity"/"When"/expand columns are cut with no visual cue. | P0 | Visible horizontal scroll + `min-w` per column, or drop the redundant "Hash Linkage" column to the expanded panel. |
| F-72 | Expanded diff accordion renders **inside** the table with `colSpan={8}` and `bg-linear-canvas` — it visually breaks the table frame (it is darker than the table surface) and duplicates `DiffViewer`'s own bordered container (nested border inside border). | P1 | Use the same surface as the table, or move the diff into the docked inspector. |
| F-73 | The filter toolbar is a wall of three text inputs (`Table (/)`, `Seq #`, `Blind ID`) plus two selects with no labels, all `font-mono` and `w-24/32/36/40` — the widths are arbitrary and the inputs' purpose is only discoverable via placeholder (which disappears on typing). | P1 | Label each control, align widths, and group behind an advanced-filter disclosure. |
| F-74 | "Seq #" filter uses `type="number"` → the browser spinner appears inside a dark themed input, and holding a key fires a request per keystroke (no debounce, unlike the HR search). | P2 | Debounce + `inputMode="numeric"` + hide spinners. |
| F-75 | The tampered row marker mixes uppercase `TAMPERED` chip + orange dot + row tint + `border-l-2` — four signals for one state, while severity chips reuse the same orange (WARNING/CRITICAL indistinguishable). | P1 | One marker + a distinct severity palette. |
| F-76 | `isSelected` is bound to the keyboard focus index, and the prop is passed as `isSelected={isSelected || isTargetSeq}` — a URL-driven state and a focus state are conflated; the target-sequence row looks identical to the focused row. | P1 | Separate `isFocused` / `isHighlighted` visual states. |

### 5.5 `components/auditor/RiskPanel.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-77 | **Breaks the portal's visual language.** Every other auditor view is a dense `DataTable`; the flag list is `p-6` stacked `rounded-2xl` rows with a completely different header, `min-h-[400px]`, and its own hero card. It reads like a different product. | P1 | Render flags in the shared `DataTable` (or a shared "record list" primitive). |
| F-78 | "Mark Safe" is a **primary lavender** button — the same emphasis as genuine navigation CTAs — for a state-changing review action, with no confirmation and no undo. Notes also reveal `Reviewed by User {flag.reviewed_by}` — an internal numeric id exposed as UI copy. | P1 | Secondary/outline styling, confirm + undo, and resolve reviewer to a name or hide. |
| F-79 | Loading and error states swap the whole panel (a spinner card vs an orange card) causing a large layout jump on entry; the error card uses `text-grafana-orange` for a *network failure*, conflating "compromised" with "offline". | P1 | In-place skeleton + a neutral error tone. |
| F-80 | Row actions are hand-rolled `<Link>`s styled to imitate buttons (`btn-press-sm … px-2 py-1.5 rounded-md`) instead of using `<Button variant="secondary">` — different hover/active/focus from every real button. | P2 | Use `<Button as={Link}>` or a shared `LinkButton`. |

### 5.6 `components/auditor/ChainVisualization.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-81 | **The "hash chain" is not visible in the collapsed row.** The row shows only `truncateHash(entry.hash)`; the `prev → hash` linkage appears only after expanding (and only in the drawer). The vertical "chain" affordance is a 2px, 14px-tall grey stub inside the first cell, and the prop is named `isFirst` while it receives `i === entries.length - 1` — the naming and the visual direction disagree, so the metaphor the component is named for is invisible until you click. | P1 | Put the `prev → hash` arrow in the row (as the Chain Explorer already does) and rename the prop to `isTail`. |
| F-82 | `high` and `critical` share one colour; `medium` is lavender; the row glow map only implements `high`/`critical` — an unfinished severity scale (3.3). | P1 | See §3.3. |
| F-83 | `text-linear-ink-tertiary` "—" placeholders and chevrons measure **3.62:1**; italics are used for empty diffs and the header hint — italic is not part of any other surface in the product. | P1 | `ink-subtle` + drop italics. |
| F-84 | The "Click any row to expand diff" hint sits in the card header as `text-xs italic` — instructional text in a title bar; also `<th>` uses `text-[10px]` and the 8 columns are hardcoded as a data array with per-column classes. | P2 | Move help into a `?` tooltip. |
| F-85 | This component's diff table is a **second, differently-styled diff implementation** (no strikethrough, `bg-linear-surface-3/50` highlight) vs `DiffViewer` (`line-through` + `bg-grafana-orange/5`). Same data, two looks. | P1 | Keep `DiffViewer`; delete the local `DiffRow`/`DiffDrawer`. |

### 5.7 `components/auditor/TimeTravelView.tsx` (637 lines)

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-86 | **Form grid label misalignment**: the row is `items-end` with a 12-col grid, but the "Time (UTC)" cell has an extra label row containing the "Set Now" button (`justify-between mb-1`) while the date cell has a plain label. The two labels sit at different heights above bottom-aligned inputs — visible raggedness in the primary form. | P1 | Put "Set Now" inside the input as a suffix or the field header; equalise label rows. |
| F-87 | **Autocomplete is not accessible**: no `role="combobox"`/`listbox`/`option`, no `aria-expanded`, no arrow-key navigation, no `aria-activedescendant`; the option rows are `<div onClick>` without `role="option"`. The product advertises keyboard-first operation. | P1 (a11y) | Proper combobox pattern or `<datalist>` fallback. |
| F-88 | The employee field accepts free text and silently truncates it: `parseInt("12abc") === 12` → looks up employee 12. | P1 (correctness) | Validate against the loaded employee list. |
| F-89 | `autoFocus={isDropdownOpen && isValidEmpId}` re-focuses the input whenever state changes — focus can jump while the user is interacting elsewhere in the form. | P2 | Remove; rely on explicit focus calls. |
| F-90 | Results: formatted card is `rounded-xl`, the raw-JSON card is `rounded-2xl`; the JSON card is `bg-linear-canvas` with `max-h-[350px]` while the left card grows — the two columns end at different heights with different radii. | P1 | Equal radius; make the JSON panel a fixed-height peer with its own scroll. |
| F-91 | Currency renders `₹85,000.00` here vs `₹85,000` everywhere else (`Intl.NumberFormat` without `maximumFractionDigits`). | P1 | Shared formatter (F-32). |
| F-92 | Error card double-dims its own text (`text-grafana-orange/90` **and** `opacity-80`) and uses the "compromised" orange for a reconstruction failure. | P2 | Neutral error tone. |
| F-93 | The decorative `History` watermark is `absolute top-0 right-0 p-8 opacity-5` inside a card that also holds the "O(log N)" badge — the wash can collide with the badge at narrow widths. | P2 | Remove or clip behind a safe area. |
| F-94 | Three different empty/zero states on one page: dashed `border-2` box ("select an employee"), plain centered text (no mutations), spinner block (loading) — while other auditor pages use an icon+title+hint block, and HR uses a bare sentence. | P1 | One `<EmptyState>` primitive with icon/title/description/action. |
| F-95 | The mutation timeline cards are `<div role="button" tabIndex={0}>` with an internal `stopPropagation` zone for two links — a nested-interactive anti-pattern that is hard to operate by keyboard and impossible by touch. | P1 | Make the card a link and the secondary links a separate toolbar. |

### 5.8 `components/auditor/AnalyticsPage` / `SecurityPosture` / `QueryPanel`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-96 | Page H2 "System Analytics" duplicates the layout header title and the nav item; the same duplication happens on Activity, Chain, Log and Time Travel pages. | P1 | Remove page titles; keep one header. |
| F-97 | `SecurityPosture` uses an inner `md:grid-cols-2` **inside** an `xl:grid-cols-2` parent: between 768–1279px the donut (`w-40`) plus a `border-r pr-8` checklist are squeezed into a half-width column → wrapping/overflow. The `border-r` also renders as a stray line in the single-column (mobile) layout. | P0 (fitting) | Use `grid-cols-1 @[640px]:grid-cols-2` container queries, or stack; apply the divider only when two columns are present. |
| F-98 | `QueryPanel` and `SecurityPosture` are siblings of unequal height in a 2-col grid → a large empty gap under the shorter card; both play `animate-fade-cascade` without stagger. | P1 | Stagger + `items-start`/masonry or rebalance the grid. |
| F-99 | The 3-up metric row (`grid-cols-3 divide-x`) holds long uppercase labels and 24px numbers; below ~640px the labels wrap to 2–3 lines and the row becomes unreadable. | P1 | 1-col on mobile, 3-col at `md`. |
| F-100 | `QueryPanel` metric icons use amber + grafana-blue + lavender decoratively; the "PostgreSQL Active" pill animates a `animate-pulse` dot permanently. | P2 | Neutral icons; no ambient pulse. |
| F-101 | Both panels share one query key but each renders its own header/refresh/status — two refresh buttons within 200px of each other. | P2 | One panel header for the analytics page. |

### 5.9 `components/auditor/VerificationControl.tsx` / `StatusBanner.tsx` / `AnchorStatus.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-102 | **Verification runs automatically every 3 seconds** (`refetchInterval` on a `useQuery` whose `queryFn` performs the verification). The "Run Verification" button is really a `refetch()`. Every poll flips `isFetching`, causing the "Scanning hash chain…" state and the spinner to flicker continuously. | P0 (behaviour + UI) | Manual trigger (mutation) + a calm last-run timestamp; poll only the cheap incident status. |
| F-103 | Two verification surfaces coexist: `StatusBanner` (unused) and `VerificationControl` + the layout's `useIncidentStatus()`; the same incident state drives the sidebar footer, the nav badge, the header banner and the overview card. | P1 | One incident source + one presentation per surface. |
| F-104 | Stats grid: `grid-cols-2` with a conditional 4th tile → the grid becomes 3 items in 2 columns, leaving a half-width orphan tile. | P1 | `grid-cols-2` with the tamper tile spanning both, or always render 4 tiles. |
| F-105 | `AnchorStatus` shows the raw hash in `break-all` inside a `text-[11px]` block, plus the store path and `toLocaleString` — three different ways of rendering the same anchor, in a `p-5` card with five stacked divider sections. | P2 | Hash with copy + truncation; collapse the raw path behind a details toggle. |
| F-106 | `entries_since_anchor > 100` triggers an orange warning with `text-[10px] text-grafana-orange/80` — a comment-like hint at 10px, 80% opacity on a tinted card (well below AA). | P1 | Real warning row with AA contrast. |
| F-107 | `STATUS_STYLES` implies four distinct states but `ANCHORED`, `STALE` and `MISSING` share `bg: 'bg-linear-surface-1'`, and STALE vs MISSING differ only by a 30%→35% border alpha — they are visually indistinguishable. All four also set `glow: 'shadow-xs'`, which is dead (F-01). | P1 | Differentiate stale (amber + clock + "N entries behind") from missing (grey + broken link + "no anchor found"). |

### 5.10 `components/auditor/ExportControl.tsx`

| # | Finding | Severity | Recommendation |
|---|---|---|---|
| F-108 | Green is used as the *brand* colour for the whole export card and for the selected tab (`bg-linear-success text-white`) — green already means "verified intact" in this product. | P1 | Neutral/primary for export; reserve green for verification. |
| F-109 | Button colour acts as the status channel: `variant` switches to `success`/`danger` after export, so the CTA changes colour permanently-ish and the layout shifts (icon changes size 5 vs 5 but the label length changes). | P1 | Keep the button stable; show a toast/inline result. |
| F-110 | Success/error text has no `role="status"`/`aria-live`, so screen readers never hear "Export Complete" or the error. | P1 (a11y) | `aria-live="polite"` region. |
| F-111 | The format description paragraph is swapped by state but always occupies the same block; combined with the nested `py-0.2` badge the tab row is 3 elements wide inside a `text-xs` container and clips at ~360px. | P2 | Stack the badge under the label or shorten to "Air-gapped". |

---

## 6. Shared primitives (`components/common/`)

| # | Component | Findings |
|---|---|---|
| **Button** | `shadow-xs` on every variant (dead). `lg`/`icon-lg` have no height (F-03). Auditor `primary` hover fails contrast (F-10). `danger`/`success` variants for auditor are *tonal* while HR's are light-tinted → the same variant looks completely different per portal. No `as`/`href` support forces styled `<Link>`s (F-80). One clickable-hash usage puts the `✓` inside children and passes `leftIcon` for the only icon (F-67). |
| **DataTable** | Sticky header cannot work + hidden horizontal scrollbar (F-14). `overflow-hidden` on Root clips focus rings and row shadows. Row height `h-9` vs two-line cells (F-27). Three radii/shadows across the two themes (F-01). No sort/selection support despite being the primary surface of both portals. |
| **DetailSheet** | `animate-in`/`slide-in-from-right`/`backdrop-blur-xs` all dead → drawers appear instantly (F-05). No focus trap, no `role="dialog"`, no `aria-modal`, no body scroll lock, no focus restoration. Docked mode `sticky top-6` + `max-h-[calc(100dvh-3.5rem)]` mismatch the layout (F-64). "Responsive" mode renders **both** the mobile overlay and the desktop pane in the DOM at all times (duplicated markup, duplicated `ErrorBoundary`). `bg-linear-surface-2/80` "backdrop-blur" header has nothing behind it — the blur is meaningless. |
| **FilterBar** | Bright divider (F-08). The `children &&` wrapper means any caller passing two flex groups gets them merged into one `justify-between` row, which is how the auditor log toolbar ends up with an unlabelled input wall (F-73). Active-filter chips row lacks `aria-label` semantics and the "Clear all" is a text-button with no focus ring. |
| **FilterChip** | Auditor and HR variants are written as two complete JSX branches (duplicated markup, two sizes: `px-2 py-0.5` vs `px-2.5 py-1`) → chip heights differ between portals for the same concept. Remove button has `focus-visible:ring-1` (thinner than the global 2px). |
| **SkeletonRows** | HR skeleton uses `bg-gray-200/80` + `divide-grafana-border/50` — Grafana tokens and a raw `gray` in the **HR** portal, breaking the slate language. Randomised widths via inline `style` make the skeletons different on every render (causes a re-paint flicker on each poll, every 3s). Column counts are passed manually and can drift from the real header. |
| **LiveStreamBadge** | HR variant uses `text-grafana-ink` (undefined → inherits) and `bg-gray-100`; auditor uses tokens. The "Streaming"/"Paused" label colours are hardcoded (`linear-success` / `grafana-orange`) regardless of theme. |
| **RefreshButton** | Spinner colour is `grafana-orange` in the HR portal where orange exists nowhere else (§3.5). Artificial 650ms minimum spin makes the action *feel* slower than it is (a latency-hiding trick that backfires on fast APIs). `variant='light'|'dark'` is a theme flag smuggled through a variant name. |
| **ErrorBoundary** | `border-inherit` divider (falls back to `currentColor` — bright in dark mode). HR branch uses undefined `text-grafana-ink`. Error message is dumped in raw mono with `break-all` — fine for engineers, alarming for HR users (no "copy error id", no support guidance). |
| **RealtimeClock** | Styled entirely from `linear.*` tokens, so it is near-invisible/mistuned inside the HR (light) header where it is also used. Uses `animate-ping` unconditionally when `showLiveDot` (F-16). |

---

## 7. Typography, spacing, radius and elevation scale

| # | Finding | Evidence | Recommendation |
|---|---|---|---|
| F-112 | **No type scale.** Ten arbitrary sizes: `text-[8px]` (1), `text-[9px]` (3), `text-[10px]` (75), `text-[11px]` (70), `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl`, `text-2xl`, `text-3xl`, `text-4xl`. **149 instances at ≤11px.** | whole codebase | Define 5 steps: `caption 11/14`, `body 13/20`, `body-lg 14/20`, `title 16/24`, `display 20/28`. Ban `text-[10px]` outside true badge labels. |
| F-113 | **Three radii applied semi-randomly to peer surfaces**: `rounded-2xl` (36), `rounded-xl` (64), `rounded-lg` (74). Card surfaces are `rounded-2xl` in HR and on auditor overview/analytics, `rounded-xl` on auditor tables, and `rounded-lg` for AuditChainPage's metric cards. | §4–5 | `radius-lg = 16px` for cards/panels, `radius-md = 8px` for controls/badges (or the inverse) — one rule, everywhere. |
| F-114 | **Elevation is undefined and inconsistent.** Because `shadow-xs`/`shadow-2xs` are dead, cards are flat by accident; the few places using valid `shadow-sm`/`shadow-2xl` therefore look arbitrary (a modal shadow-2xl next to a flat card). | F-01 | 3-step elevation: `resting` (none or 1px hairline only), `raised` (card hover), `overlay` (drawer/modal). Map to real utilities. |
| F-115 | **Padding is not standardised**: cards use `p-4`, `p-4.5`(dead), `p-5`, `p-6`, `p-8`; panel headers use `px-5 py-4`, `px-6 py-5`, `px-6 py-4`, `px-4 py-3`. | §4–5 | `p-4` compact / `p-6` comfortable, applied per component type, not per file. |
| F-116 | **`font-mono` is over-applied** — **132 occurrences** applied to non-code content: buttons ("Jump", "Head", "Sync"), select controls, badges, page subtitles, filter inputs, timestamps, relative times and id labels. Mono for *identifiers/telemetry* is right; mono for *interactive chrome* reads as unfinished. | whole codebase | Mono only for hashes, ids, sequences, JSON, numeric telemetry. |
| F-117 | **Uppercase micro-labels are everywhere**: 58 `uppercase` + 49 `tracking-wider` occurrences, often combined at 9–10px (nav group headers, chips, table headers, section labels, badges). When everything shouts, nothing has hierarchy. | whole codebase | Reserve uppercase + tracking for table headers and nav group labels only. |

---

## 8. Accessibility (beyond contrast)

| # | Finding | Where | Recommendation |
|---|---|---|---|
| F-118 | Focus indicators are inconsistent or absent: `focus-visible:outline-none` with no ring (EmployeeTable clear button, TimeTravel "Change"/"Cancel", the segmented status control, ExportControl inner spans), 1px rings (FilterChip), 2px rings (Button, most links), 4px 5%-opacity rings (HR inputs). | multiple | One `focus-visible` recipe: 2px ring, offset 1, high contrast. |
| F-119 | `DetailSheet` has no `role="dialog"`, `aria-modal`, focus trap, focus restore, or scroll lock — the background remains scrollable and tabbable behind a "modal" drawer. | `DetailSheet.tsx` | Use `inert` on the background + focus management (or a headless dialog). |
| F-120 | Icon-only buttons are good (`aria-label` present) but several *icon-adjacent* controls lack names: the `×` clear button in the auditor log (`Table (/)` input has no label), the date/time fields rely on `<label>` without `htmlFor`/`id` pairing, and the tabs in `EmployeeSheet` lack `role="tab"`/`aria-selected`. | see §4.4, §5.4 | Associate labels, add ARIA roles where a visual pattern implies them. |
| F-121 | Global keyboard handler `preventDefault()`s Arrow keys and Space on every page (breaks scrolling); `/` and `p` are global shortcuts with no way to opt out and no discoverability surface. | `hooks/useKeyboardNav.ts` | Scope listeners to the table region; add a shortcut legend dialog. |
| F-122 | Several status changes have no live region: export result, "Mark Safe" success, feedback banners in `EmployeeSheet` (visual only), the freeze banner. | multiple | `aria-live="polite"` for result banners. |
| F-123 | Touch targets: 24px icon buttons (`size="icon-xs"`), 6px-high chips, 12px-high `py-0.5` badges; tab targets 28px. | HR table, auditor tables | ≥32px for pointer targets, ≥44px on touch breakpoints. |
| F-124 | The HR drawer has no unsaved-changes guard and `Escape` closes it discarding input (the ESC handler in `DetailSheet` only ignores Esc while an input is focused — a textarea/select check that misses contenteditable). | §4.4 | Dirty-state guard. |

---

## 9. Responsiveness and fitting problems (summary)

| # | Finding | Severity |
|---|---|---|
| F-125 | Neither portal has a responsive shell: fixed `w-64` sidebar, `h-screen`, no mobile nav (F-18/F-56). | P0 |
| F-126 | Tables with 7–8 columns hide their horizontal scrollbar and their sticky header does not work (F-14/F-71). | P0 |
| F-127 | `SecurityPosture` squeezes a 2-col layout into a half-width grid column, leaving a stray `border-r` at narrow widths (F-97). | P0 |
| F-128 | `QueryPanel`'s 3-up metric row and `RiskPanel`'s `md:flex-row` rows with fixed `md:w-48`/`md:w-36` columns collapse unpredictably between 640–900px. | P1 |
| F-129 | Docked inspectors overlap/compress content between 1024–1279px (F-65) and their sticky offset does not match the layout padding (F-64). | P1 |
| F-130 | `100dvh`-based sizing is mixed with `h-screen` (mobile browser chrome causes 56–100px of clipping). | P1 |
| F-131 | Long content has no `min-w-0`/`truncate` in several flex rows (actor emails, table names in `RiskPanel`, the `RiskPanel` reason text at `md:w-48`), producing overflow rather than ellipsis. | P1 |

---

## 10. Information architecture and content honesty

| # | Finding | Severity |
|---|---|---|
| F-132 | Page titles are duplicated 3–4× per route: layout header (path-derived) + page H2 + a section headline inside the component (e.g. Chain page: header "Chain", page H1 "Cryptographic Chain Explorer", section "Audit Hash Chain"). | P1 |
| F-133 | "Activity & Risk" hosts both the incident review queue *and* a concurrency stress-test lab — two unrelated jobs (compliance triage vs engineering benchmarking) on one page, under one nav item. | P1 |
| F-134 | Dead placeholder left in the shipped UI: `pages/auditor/AuditLogPage.tsx:16–19` renders an empty `<div className="flex-shrink-0 w-full sm:w-auto">` containing a developer comment about `ExportControl` — an empty flex child that perturbs the header row. | P1 |
| F-135 | Fake progress: `StatusBanner.tsx` awaits `setTimeout(1800)` and calls `onRunVerification()` — a simulation shipped in the UI layer. | P0 (trust) |
| F-136 | Unverified assurance copy: HR Dashboard "Chain Intact"/"Cryptographically Sealed" (F-20); HRSettings "Active (Clerk MFA Enforced)" when 2FA is off (F-44); sidebar "Operational • Full Access" is static (F-19). | P1 |
| F-137 | Emoji inside enterprise chrome: `⚠ Tampering Detected — Immediate Action Required`, `Time-Travel ⏱`, `Catch Up ↑`, `⚠ Compromise Detected` — inconsistent with the icon system that already exists. | P2 |
| F-138 | `Empty states` exist in four different shapes (see F-94), and the auditor tables' empty states are the best of them — that pattern should be the standard. | P1 |
| F-139 | Copy mixes registers: "Forensic Incident Queue", "Keyset Walk", "Air-Gapped", "Automated Checkpoint Trigger" sit next to "No employees found matching the specified parameters." and "Failed to query employee directory from database engine." (raw engineering strings surfaced to HR users). | P2 |

---

## 11. Consistency and duplication (maintainability that shows up as UI drift)

| # | Duplicated logic | Copies | Divergence |
|---|---|---|---|
| F-140 | Relative-time formatting | 6 (`Dashboard`, `AuditLogTable`, `AuditChainPage`, `ChainVisualization`, `AnchorStatus`, `StatusBanner`) | Different thresholds and fallbacks (`d ago` vs `toLocaleDateString()`), so the same timestamp renders differently per page. |
| F-141 | Hash truncation | 4 (`AuditLogTable` `n=8`, `AuditChainPage` `6…4`, `ChainVisualization` `6…4`, `StatusBanner` `12…`) | The same hash shows as `abc12345…` on one screen and `abc123…ef12` on another. |
| F-142 | Action/severity style maps | 4 (+2 severity variants) | See §3.2 — they disagree. |
| F-143 | Status dot (`animate-ping` + solid dot) | 5 inline implementations | Different sizes (1.5/2/2.5px) and colours per site. |
| F-144 | INR formatting | 3 call sites, 2 behaviours | `₹85,000` vs `₹85,000.00`. |
| F-145 | `Intl.NumberFormat` instances constructed inside render | 4 | Per-render allocation on every poll (every 3s). |
| F-146 | Tab/segmented control | 3 visual variants | See F-36. |
| F-147 | Diff rendering | 2 (`DiffViewer`, `ChainVisualization.DiffDrawer`) | Different highlight, strikethrough, and empty-state copy. |
| F-148 | Button import style | mix of `import Button` and `import { Button }` | Works (both exports exist) but signals no convention. |
| F-149 | Card container classes | re-typed in ~40 places (`bg-linear-surface-1 border border-linear-hairline rounded-2xl …`) | No `<Panel>` primitive, so a token change (F-01/§3.1) cannot be applied once. |
| F-150 | Modal scrim | `bg-slate-950/45` (DetailSheet) vs `bg-black/60` (forms) | Two scrims. |

---

## 12. Dead code and cleanup

| # | Item | Evidence | Recommendation |
|---|---|---|---|
| F-151 | `components/forms/EmployeeEditForm.tsx` — **never imported** (superseded by `EmployeeSheet`'s Edit tab) yet still documented in `Argus_docs/FRONTEND_ARCHITECTURE.md` as a key component. Contains 9 of the 17 `text-grafana-ink` violations and 4 dead classes. | no references | Delete (or resurrect properly and update the doc). |
| F-152 | `components/forms/SalaryForm.tsx` — **never imported**; duplicates `EmployeeSheet`'s salary tab. 5 more `text-grafana-ink` violations. | no references | Delete. |
| F-153 | `components/auditor/StatusBanner.tsx` — never rendered; contains a `setTimeout` "simulation" and a second verification UI. | no references | Delete; fold the useful states into `VerificationControl`. |
| F-154 | `tailwind.config.js`: `keyframes.drawerSlideIn/drawerSlideOut` + `animation.drawer-in/drawer-out` are unused; `slate.850/925` are unused; `grafana.*` is used mostly from the HR portal, which is itself a bug. | grep | Prune or use. |
| F-155 | `grafana-btn-primary` / `linear-btn-primary` / `grafana-panel` / `linear-panel*` utility classes in `index.css` — unused (no component references them). | grep | Prune or migrate components onto them. |
| F-156 | Pre-existing naming drift: `SEVERITY_DOT` exists in both `AuditLogTable` (INFO/WARNING/CRITICAL) and `ChainVisualization`/`AuditChainPage` (low/medium/high/critical), the same name for two different key sets. | §3.2 | One module, one type. |

---

## 13. Recommended target state (design-system specification)

### 13.1 Tokens (add to `tailwind.config.js`)

```
colors.portal  // HR light system, mirrors linear.*
  canvas #f8fafc · surface-1 #ffffff · surface-2 #f1f5f9
  hairline #e2e8f0 · hairline-strong #cbd5e1
  ink #0f172a · ink-muted #475569 · ink-subtle #64748b
  primary #0f172a (actions) · accent #047857
  success #15803d · warning #b45309 · danger #be123c · info #1d4ed8
boxShadow: 2xs, xs, sm, lg   // F-01
spacing: 4.5, 9.5 (or stop using them)
borderRadius: card 16, control 8, chip 6
semantic map (lib/semantics.ts): actionStyle, severityDot, severityChip, statusDot
```

### 13.2 Non-negotiable rules

1. No component may reference a raw palette colour (`slate-*`, `emerald-*`, `amber-*`, `rose-*`, `sky-*`, `orange-*`, `gray-*`) — only portal tokens. Enforce with an ESLint `no-restricted-syntax` rule on `className` string literals.
2. No arbitrary type sizes below 11px; mono only for identifiers/telemetry (§7 F-116/F-117).
3. Every interactive element declares the shared `focus-visible` ring.
4. Every colour pairing used for text ships with a measured ratio ≥ 4.5:1 (≥3:1 for ≥18.66px bold) recorded in the token file as a comment.
5. One primitive per concept: `Panel`, `StatusDot`, `Badge`, `SegmentedControl`, `EmptyState`, `Toast`/`InlineResult`, `CopyButton`, `RelativeTime`, `HashText`, `EmployeeRef`, `Money`.
6. Every portal shell collapses to an off-canvas nav below `lg` and uses `h-dvh`.
7. No `animate-pulse` on persistent status; animate only transitions.

---

## 14. Prioritised remediation roadmap

### Batch 1 — Foundation (fixes the largest cluster; ~1 day)

1. Add `boxShadow.2xs/xs` (F-01) and remove the dead `shadow-2xs`/`shadow-xs` at call sites if you prefer standard names.
2. Replace `p-4.5`, `h-4.5`, `w-4.5`, `h-9.5`, `py-0.2`, `border-inherit/40`, `backdrop-blur-xs` (F-02/03/04/08/09 + table in §2).
3. Install `tailwindcss-animate` **or** define a local `panel-in` keyframe and switch `DetailSheet`/`AuditLogPage`/`ConcurrencyLab` to it (F-05).
4. Replace undefined tokens `text-grafana-ink` → `text-slate-900`, `text-linear-ink-secondary` → `text-linear-ink-muted` (F-06/F-07).
5. Delete the three dead components and the AuditLogPage placeholder div (F-134, F-151–153).
6. Fix the primary-button hover colour so hover does not reduce contrast (F-10).

### Batch 2 — Layout integrity (~2 days)

7. Responsive shells for both portals with off-canvas nav + `h-dvh` (F-18/F-56/F-125).
8. `DataTable`: working sticky header, visible horizontal scroll, 44–48px two-line rows, focus vs selection as separate states (F-14/F-27/F-76).
9. Server-side department/status filtering so counts and pagination agree (F-25).
10. Docked-inspector offset/height and `xl`-only docking (F-64/F-65/F-129).
11. `SecurityPosture` container-query layout, removing the stray divider (F-97).

### Batch 3 — Consistency (~3 days)

12. `lib/semantics.ts` + `lib/format.ts` and migrate all 6 time formatters, 4 hash truncators, 4 style maps, 3 currency paths (F-140–F-145).
13. Extract primitives: `Panel`, `SegmentedControl`, `StatusDot`, `EmptyState`, `CopyButton`, `Toast`, `PageHeader` (F-94, F-132, F-143, F-146, F-149).
14. Resolve the HR palette into `portal.*` tokens and remove `grafana.*` from HR (F-06, §3.1).
15. One page-header/content-width rule; delete duplicated page titles (F-45, F-96, F-132).
16. Raise every failing contrast pair to AA (F-11/12/13 + §3.6).

### Batch 4 — Feature-grade polish (~4–6 days)

17. Sortable/selectable/bulk-action directories; page-size selector (F-33/F-34).
18. One combobox primitive with full ARIA; replace Time-Travel's autocomplete (F-87/F-88).
19. Manual verification + a single incident state machine with one calm affordance (F-102/F-103/F-51).
20. Replace `window.confirm` with the shared modal; add unsaved-changes guards (F-37/F-40/F-124).
21. Relative-time/hash tooltips with copy on all identifiers; keyboard-shortcut legend dialog (F-69/F-121).
22. Split "Activity & Risk" into Incident Review + Concurrency Lab (F-133).

---

## Appendix A — How to reproduce the verification

```bash
cd frontend

# 1) Which classes emit no CSS? (compiles the real stylesheet, writes nothing)
node --input-type=module -e "
import postcss from 'postcss'; import tailwindcss from 'tailwindcss'; import fs from 'node:fs';
const out = await postcss([tailwindcss('./tailwind.config.js')]).process(fs.readFileSync('./src/index.css','utf8'),{from:'./src/index.css'});
const all = out.css.split(String.fromCharCode(92)).join('');
for (const c of ['shadow-xs','shadow-2xs','p-4.5','h-9.5','py-0.2','text-grafana-ink','text-linear-ink-secondary','border-inherit/40','backdrop-blur-xs','animate-in','slide-in-from-right'])
  console.log(new RegExp('[.]' + c.split('.').join('[.]')).test(all) ? 'OK      ' : 'MISSING ', c);
"

# 2) Usage counts
grep -rno 'shadow-xs' src | wc -l      # 38
grep -rno 'shadow-2xs' src | wc -l     # 31

# 3) Dead components
grep -rn 'StatusBanner\|EmployeeEditForm\|SalaryForm' src | grep import   # -> none
```

## Appendix B — Files reviewed

`frontend/src/**` (48 files): 2 layouts, 3 HR pages, 6 auditor pages, 12 auditor components, 5 HR/form components, 10 common components, 2 auth components, 1 hook, `lib/api.ts`, `lib/queryClient.ts`, `services/auditService.ts`, `index.css`, `main.tsx`, `App.tsx`; plus `frontend/tailwind.config.js`, `postcss.config.js`, `vite.config.ts`, `index.html`, `package.json`, `playwright.config.ts`, `e2e/example.spec.ts`, and cross-checked against `Argus_docs/FRONTEND_ARCHITECTURE.md`.
