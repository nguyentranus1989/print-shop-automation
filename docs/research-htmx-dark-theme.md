# HTMX-Based Dashboard UI Patterns for Industrial Printer Control

## Executive Summary

HTMX enables lightweight real-time dashboards via Server-Sent Events (SSE), eliminating WebSocket complexity. Pico CSS + dark mode provides semantic HTML styling (7.7 KB gzipped). Industrial CNC/printer UX requires intentional button sizing (12×15mm typical), color-coded status indicators (IEC 60073), and monospace fonts for data displays. This pattern suite fits single-page industrial dashboards with minimal JS overhead.

---

## 1. HTMX Patterns for Real-Time Updates

### SSE Architecture
- **HTMX 4.x** uses `hx-sse:connect="<stream_url>"` to establish uni-directional connection
- Server sends named events; client swaps content via `sse-swap="event_name"` or automatic unnamed-message swap
- Named events dispatch as DOM events—can trigger htmx requests without `sse:` prefix
- Preferred over WebSockets: works through proxies, firewalls; no bi-directional overhead

### Core Swap & Trigger Patterns

```html
<!-- Real-time status: SSE → automatic content swap -->
<div hx-ext="sse" hx-sse:connect="/events/status">
  <span id="machine-status">Idle</span>
</div>

<!-- Polling fallback for older clients (5s interval) -->
<div hx-get="/api/status" hx-trigger="every 5s">
  <div id="status-bar">...</div>
</div>

<!-- Multiple events from single stream -->
<div hx-ext="sse" hx-sse:connect="/events/stream">
  <p sse-swap="message"></p>
  <span sse-swap="counter"></span>
</div>
```

### Key Attributes
- `hx-ext="sse"` — Enable SSE extension
- `hx-sse:connect` — Stream URL
- `sse-swap` — Event name to listen for
- `hx-trigger="every Xs"` — Polling (polling fallback only)
- `hx-swap="innerHTML"` (default) — Swap strategy

### Constraint: SSE is uni-directional
Cannot send messages back to server once connected. Use separate `hx-post`/`hx-put` for control commands.

---

## 2. Dark Theme & Minimal CSS Frameworks

### Pico CSS (Recommended)
- **Size:** 7.7 KB gzipped (single file)
- **Dark Mode:** Automatic—respects `prefers-color-scheme`; no JS required
- **Semantic:** Styles raw HTML (button, input, table, form) without custom classes
- **Industrial Fit:** Neutral, professional color palette; high contrast for readability
- **Usage:** Single CDN link: `<link rel="stylesheet" href="https://cdn.picocss.com/pico.min.css">`
- **Customization:** CSS variables for colors, spacing, fonts

### Alternative Minimal Frameworks
- **MVP.css** (~10 KB gzipped)—Styled form elements, quick MVPs
- **Simple.css** (~4 KB)—Typography-first, maximum readability
- **All support dark mode** via CSS variables or `prefers-color-scheme`

### Dark Theme CSS Pattern
```css
/* Pico auto-detects dark mode */
@media (prefers-color-scheme: dark) {
  body { background: #1e1e1e; color: #e0e0e0; }
  input { background: #2d2d2d; border: 1px solid #444; }
}
```

---

## 3. Industrial Control Panel UX

### Button & Control Sizing
- **Single Button:** 12×15 mm typical (tightly arranged on physical panels)
- **Web Equivalent:** 44–48 px minimum (touch/accessibility)
- **Spacing:** 8–12 px gaps to prevent accidental activation
- **Visual Feedback:** Clear hover/active states (high contrast)

### Layout Principles
- **Grouped Controls:** Related buttons clustered (power, status, diagnostic)
- **Hierarchy:** Large buttons for primary actions (start/stop); smaller for secondary
- **Durability:** No rounded corners on industrial panels (dust/debris); angular edges preferred
- **Readability Distance:** Design for 1–2 meter viewing (factory floor); high contrast essential

### Industrial Colors (IEC 60073 Standard)
- **Green** — Running / Normal operation
- **Red** — Emergency stop / Critical fault
- **Yellow/Amber** — Warning / Maintenance required
- **Blue** — Informational (optional)

---

## 4. Font Choices for Industrial Dashboards

### Monospace (Data Display)
- **JetBrains Mono** — Humanist monospace; excellent readability at small sizes; popular in industrial tech
- **IBM Plex Mono** — Corporate monospace (IBM open-source); consistent with brand systems; good for metrics/logs
- **Usage:** Numeric readouts, status codes, job queues, timestamps

### Sans-Serif (UI & Labels)
- **IBM Plex Sans** — Neutral, professional; pairs with Plex Mono; industrial default
- **DM Sans** — Geometric, clean; good for dashboards; modern without being trendy
- **Space Grotesk** — Wider x-height; excellent readability; modern industrial aesthetic
- **Outfit** — Friendly yet technical; good for control labels; web-friendly weight set
- **Avoid:** Inter, Poppins (too trendy for industrial; don't age well)

### Recommended Pairing
```css
--font-mono: 'JetBrains Mono', monospace;      /* Data: 11–13px */
--font-sans: 'IBM Plex Sans', sans-serif;      /* UI: 14–16px */
/* or Space Grotesk + IBM Plex Mono for bolder look */
```

### Font Sizes
- **Labels/Buttons:** 14–16 px (high-contrast sans-serif)
- **Metrics/Status:** 12–14 px (monospace, higher contrast)
- **Headers:** 20–24 px (bold sans-serif, all-caps for urgency)

---

## 5. Real-Time Status Displays

### Progress Bars (HTML5 Native)
```html
<!-- Native <progress> element, styled with Pico -->
<progress value="75" max="100"></progress>
<!-- Custom via CSS for industrial aesthetics -->
```

### Status Indicator Patterns
```html
<!-- Color-coded status badge -->
<div class="status-badge status-running">
  <span class="indicator-dot"></span> Running
</div>

<!-- Real-time counter (SSE-driven) -->
<div hx-ext="sse" hx-sse:connect="/events/job-counter">
  <span id="jobs-queued" sse-swap="jobs">0</span>
</div>

<!-- Multi-state indicator (stack-light style) -->
<div class="stack-light">
  <div class="light light-red"></div>   <!-- Fault -->
  <div class="light light-yellow"></div> <!-- Warning -->
  <div class="light light-green"></div>  <!-- Running -->
</div>
```

### CSS for Status Indicators
```css
.indicator-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  animation: pulse 2s infinite;
}

.status-running .indicator-dot { background: #2ecc71; } /* Green */
.status-warning .indicator-dot { background: #f39c12; } /* Yellow */
.status-error .indicator-dot { background: #e74c3c; }   /* Red */

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
```

### Real-Time Constraints
- Update frequency: 100–500 ms typical (industrial machines don't change faster)
- SSE overhead: ~1–2 ms per message (minimal server load)
- Fallback: Polling every 5 sec if SSE unavailable

---

## Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Framework** | HTMX + Pico CSS | Minimal, semantic, dark-mode built-in |
| **Real-time** | SSE (HTMX 4.x) | No WebSocket complexity; proxy-friendly |
| **Fonts** | JetBrains Mono + IBM Plex Sans | Readable, professional, industrial default |
| **Colors** | IEC 60073 (green/red/yellow) + dark bg | Standard industrial; high contrast |
| **Components** | Native HTML5 (button, progress, input) | Zero JS framework bloat; Pico handles styling |

---

## Unresolved Questions

- **Button activation delay on printer control:** Does SSE+hx-post add perceptible latency vs. WebSocket? (Needs latency testing <100ms)
- **Dark theme on shop floor displays:** How does monitor glare affect Pico CSS dark palette at 1+ meter distance? (Physical UX testing needed)
- **Font rendering at small sizes:** Which monospace (JetBrains vs. IBM Plex) is sharper at 11–12px on industrial displays? (A/B test required)

---

## Sources
- [htmx Documentation](https://htmx.org/docs/)
- [htmx SSE Extension](https://htmx.org/extensions/sse/)
- [Real-time Notification Streaming using SSE and Htmx](https://medium.com/@soverignchriss/real-time-notification-streaming-using-sse-and-htmx-32798b5b2247)
- [Live website updates with Go, SSE, and htmx](https://threedots.tech/post/live-website-updates-go-sse-htmx/)
- [Pico CSS](https://picocss.com/)
- [The Ultimate Guide to CNC Control Panel](https://www.yeulian.com/news-detail/the-ultimate-guide-to-cnc-control-panel.htm)
- [CNC Control Panel Button Sizing Guide](https://www.paycnc.com/info/buttons-on-cnc-control-panel_i2341.html)
- [IBM Plex Mono - Google Fonts](https://fonts.google.com/specimen/IBM+Plex+Mono)
- [JetBrains Mono Font Pairings](https://maxibestof.one/typefaces/jetbrains-mono)
- [Indicator Lights for Industrial Automation](https://www.allpcb.com/allelectrohub/indicator-lights-for-industrial-automation-enhancing-safety-and-efficiency)
- [Status Light Guide for HMI and Panel Indicators](https://vcclite.com/status-light-guide/)
- [IEC 60073 Color Standards](https://control.com/forums/threads/indicator-light-color-standards.1910/)
