# PrintFlow Design Guidelines

> Internal print shop automation dashboard. Dark theme, operator-first, industrial UX.
> Stack: FastAPI + Jinja2 + HTMX 2.0 + Pico CSS (no React/Node)

---

## 1. Design Principles

1. **Operator-first** — Primary users stand at printers wearing gloves. Large touch targets, high contrast, readable at 1-2m distance.
2. **Dark theme mandatory** — Print shop floors are dim; bright screens cause glare and eye strain.
3. **Status at a glance** — Printer state (running/idle/error) visible without interaction. IEC 60073 color coding.
4. **Minimal interaction** — Reduce taps/clicks. Critical actions reachable in 1-2 touches max.
5. **Progressive enhancement** — HTMX enhances server-rendered HTML. Works without JS (degraded).
6. **No cosmetic bloat** — Industrial tool, not a marketing site. Every pixel serves function.

---

## 2. Color System

### 2.1 Background Layers (darkest to lightest)

| Token | Hex | Usage |
|---|---|---|
| `--bg-deepest` | `#0a0a0b` | Page background, body |
| `--bg-surface` | `#141416` | Main content area, sidebar |
| `--bg-card` | `#1e1e22` | Cards, panels, modals |
| `--bg-elevated` | `#2a2a30` | Hover states, dropdowns, active items |
| `--bg-input` | `#1a1a1e` | Input fields, text areas |

### 2.2 Semantic Colors

| Token | Hex | Usage |
|---|---|---|
| `--color-primary` | `#3b82f6` | Action buttons, links, active nav |
| `--color-primary-hover` | `#2563eb` | Primary button hover |
| `--color-primary-muted` | `#1e3a5f` | Primary backgrounds (badges, highlights) |
| `--color-success` | `#22c55e` | Running, complete, healthy |
| `--color-success-muted` | `#15532e` | Success backgrounds |
| `--color-warning` | `#eab308` | Attention needed, maintenance |
| `--color-warning-muted` | `#5c4a0a` | Warning backgrounds |
| `--color-danger` | `#ef4444` | Error, stop, critical fault |
| `--color-danger-muted` | `#5c1a1a` | Danger backgrounds |

### 2.3 Text Colors

| Token | Hex | Usage |
|---|---|---|
| `--text-primary` | `#f4f4f5` | Headings, primary content |
| `--text-secondary` | `#a1a1aa` | Labels, descriptions, secondary info |
| `--text-muted` | `#52525b` | Placeholders, disabled, tertiary |
| `--text-inverse` | `#0a0a0b` | Text on light backgrounds |

### 2.4 Border & Dividers

| Token | Hex | Usage |
|---|---|---|
| `--border-default` | `#27272a` | Card borders, dividers |
| `--border-hover` | `#3f3f46` | Hover state borders |
| `--border-focus` | `#3b82f6` | Focus rings (accessibility) |

### 2.5 IEC 60073 Industrial Standard Reference

- **Green** — Running / Normal operation
- **Red** — Emergency stop / Critical fault
- **Yellow/Amber** — Warning / Maintenance required
- **Blue** — Informational / User action required

---

## 3. Typography

### 3.1 Font Stack

```css
--font-heading: 'Space Grotesk', system-ui, sans-serif;
--font-body: 'IBM Plex Sans', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Courier New', monospace;
```

### 3.2 Google Fonts Import

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
```

### 3.3 Type Scale

| Element | Font | Size | Weight | Line Height |
|---|---|---|---|---|
| Page title (h1) | Space Grotesk | 28px | 700 | 1.2 |
| Section title (h2) | Space Grotesk | 24px | 700 | 1.3 |
| Subsection (h3) | Space Grotesk | 20px | 500 | 1.3 |
| Body text | IBM Plex Sans | 16px | 400 | 1.5 |
| Secondary text | IBM Plex Sans | 14px | 400 | 1.5 |
| Small/caption | IBM Plex Sans | 12px | 400 | 1.4 |
| Data/numbers | JetBrains Mono | 14px | 400 | 1.4 |
| Data large | JetBrains Mono | 20px | 500 | 1.2 |
| KPI number | JetBrains Mono | 32px | 500 | 1.1 |

### 3.4 Usage Rules

- **Headings**: Space Grotesk — wider x-height, modern industrial look
- **UI text** (labels, buttons, paragraphs): IBM Plex Sans — neutral, professional
- **Data displays** (positions, ink %, progress, counts, timestamps): JetBrains Mono — aligned columns, clear digit distinction
- Never use decorative/script fonts
- Minimum font size: 12px (14px preferred for operator readability)

---

## 4. Spacing System

Base unit: **4px**

| Token | Value | Usage |
|---|---|---|
| `--space-1` | 4px | Tight internal padding, icon gaps |
| `--space-2` | 8px | Between related elements |
| `--space-3` | 12px | Card internal padding (compact) |
| `--space-4` | 16px | Standard card padding, section gaps |
| `--space-6` | 24px | Between sections |
| `--space-8` | 32px | Major section breaks |
| `--space-12` | 48px | Page-level margins |

---

## 5. Components

### 5.1 Buttons

| Variant | Min Height | Min Width | Font Size | Usage |
|---|---|---|---|---|
| Primary | 48px | 120px | 16px | Main actions (Print, Save, Add Job) |
| Critical | 56px | 140px | 16px, bold | Dangerous/important (Stop, Cancel, Emergency) |
| Secondary | 40px | 96px | 14px | Secondary actions (Filter, Export) |
| Icon-only | 48px | 48px | — | D-pad arrows, toolbar icons |
| Small | 32px | 80px | 13px | Table row actions, tags |

- Touch target minimum: 44x44px (WCAG 2.5.8)
- Critical buttons: red background, bold text, 56px tall
- All buttons: 8px border-radius, 2px border
- Hover: darken 10%; Active: darken 20%
- Disabled: 40% opacity, cursor not-allowed

### 5.2 Status Indicators

**Status Dot:**
- Size: 12px diameter
- Active states: pulse animation (2s infinite)
- Colors: green (running), yellow (warning), red (error), gray (offline)

```css
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 currentColor; }
  50% { opacity: 0.7; box-shadow: 0 0 0 4px transparent; }
}
```

**Status Badge:**
- Pill shape (999px border-radius)
- Background: muted variant of status color
- Text: bright variant of status color
- Padding: 4px 12px
- Font size: 12px, weight 500

| Status | Background | Text | Dot |
|---|---|---|---|
| Running | `#15532e` | `#22c55e` | green pulse |
| Idle | `#27272a` | `#a1a1aa` | gray static |
| Queued | `#1e3a5f` | `#3b82f6` | blue static |
| Warning | `#5c4a0a` | `#eab308` | yellow pulse |
| Error | `#5c1a1a` | `#ef4444` | red pulse |
| Complete | `#15532e` | `#22c55e` | green static |

### 5.3 Cards

- Background: `--bg-card` (#1e1e22)
- Border: 1px solid `--border-default` (#27272a)
- Border-radius: 8px
- Padding: 16px (standard), 12px (compact/mobile)
- No box-shadow (flat industrial look)
- Hover: border-color shifts to `--border-hover`

### 5.4 Progress Bars

- Height: 8px
- Border-radius: 4px (fully rounded)
- Track background: `--bg-elevated` (#2a2a30)
- Fill color matches status (green for printing, blue for queued)
- Optional: percentage label above in JetBrains Mono

### 5.5 Tables

- Striped rows: alternate between `--bg-card` and `--bg-surface`
- Header: `--bg-elevated` background, uppercase text, 12px, 600 weight
- Cell padding: 12px 16px
- Border-bottom: 1px solid `--border-default`
- Hover row: `--bg-elevated` background

### 5.6 Navigation

**Sidebar:**
- Width: 240px (desktop), collapsible on tablet
- Background: `--bg-surface`
- Active item: `--color-primary-muted` background, `--color-primary` text, left 3px border
- Icon + label layout, 48px row height
- Bottom section: settings, user

**Top Bar:**
- Height: 56px
- Background: `--bg-surface`
- Border-bottom: 1px solid `--border-default`
- Contains: logo, printer status indicators, clock

### 5.7 Inputs & Forms

- Height: 44px
- Background: `--bg-input`
- Border: 1px solid `--border-default`
- Border-radius: 6px
- Focus: `--border-focus` (blue) ring
- Font: IBM Plex Sans, 14px

---

## 6. Layout

### 6.1 Grid System

- CSS Grid for page layout (sidebar + main)
- CSS Grid or Flexbox for card grids
- Printer cards: 3-column on desktop, 1-column on mobile
- KPI strip: 4 equal columns, stack on mobile

### 6.2 Breakpoints

| Name | Width | Layout |
|---|---|---|
| Mobile | < 768px | Single column, sidebar hidden, hamburger menu |
| Tablet | 768-1023px | Sidebar collapsed (icons only), 2-column cards |
| Desktop | >= 1024px | Full sidebar, 3-column printer cards |
| Wide | >= 1440px | Max-width container, comfortable spacing |

### 6.3 Content Width

- Max content width: 1400px (centered)
- Sidebar: 240px fixed (desktop), 64px collapsed (tablet)
- Main area: fluid, with 24px padding

---

## 7. Animations & Transitions

- **Status pulse**: 2s infinite for active printer dots
- **Transitions**: 150ms ease for hover states, 200ms for color changes
- **Page transitions**: none (server-rendered, HTMX swaps are instant)
- **Loading states**: skeleton placeholders with shimmer animation
- **Respect `prefers-reduced-motion`**: disable pulse and shimmer

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 8. Accessibility

- Minimum contrast ratio: 4.5:1 (normal text), 3:1 (large text) — WCAG 2.1 AA
- Focus indicators: 2px solid blue ring on all interactive elements
- ARIA labels on icon-only buttons
- Skip-to-content link (hidden until focused)
- Status changes announced via `aria-live="polite"` regions
- Keyboard navigable: all controls reachable via Tab, actions via Enter/Space
- Touch targets: 44px minimum dimension

---

## 9. HTMX Patterns

### 9.1 Real-Time Updates

```html
<!-- SSE for live printer status -->
<div hx-ext="sse" sse-connect="/events/printer-status">
  <div sse-swap="printer-dtg">...</div>
  <div sse-swap="printer-dtf">...</div>
  <div sse-swap="printer-uv">...</div>
</div>
```

### 9.2 Polling Fallback

```html
<div hx-get="/api/dashboard/kpi" hx-trigger="every 10s" hx-swap="innerHTML">
  ...
</div>
```

### 9.3 Actions

```html
<button hx-post="/api/printer/dtg/pause"
        hx-confirm="Pause DTG printer?"
        hx-target="#printer-dtg-status"
        hx-swap="outerHTML">
  Pause
</button>
```

---

## 10. Iconography

- Style: Outlined, 24px default, 2px stroke
- Source: Lucide Icons (open source, consistent with industrial feel)
- Colors: inherit from text color; semantic icons use status colors
- Critical actions: include text label alongside icon (never icon-only for destructive actions)

---

## 11. Dark Theme Implementation

Override Pico CSS variables:

```css
[data-theme="dark"], :root {
  --pico-background-color: #0a0a0b;
  --pico-card-background-color: #1e1e22;
  --pico-card-border-color: #27272a;
  --pico-color: #f4f4f5;
  --pico-muted-color: #a1a1aa;
  --pico-primary: #3b82f6;
  --pico-primary-hover: #2563eb;
  --pico-form-element-background-color: #1a1a1e;
  --pico-form-element-border-color: #27272a;
}
```

---

## 12. File Naming (Wireframes & Templates)

- Kebab-case: `printer-control.html`, `job-queue.html`
- Partials prefix: `_partial-printer-card.html`, `_partial-kpi-strip.html`
- Layout: `base.html`
- Static assets: `static/css/printflow.css`, `static/js/printflow.js`
