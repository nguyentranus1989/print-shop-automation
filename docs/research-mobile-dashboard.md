# Mobile Dashboard Research: CSS + HTMX + Jinja2

## 1. CSS-Only Responsive Patterns

**Mobile-First Grid + Flexbox**
- Start layouts for small screens, scale up with media queries.
- Use `grid: auto-fit / minmax(min-content, max-content)` for automatic column wrapping.
- Use `gap: clamp(1rem, 2.5vw, 2rem)` for responsive spacing without breakpoints.
- Container queries (93.92% browser support) allow components to respond to container width, not viewport—ideal for modular dashboards.
- CSS `clamp()` eliminates multiple breakpoints: `font-size: clamp(0.875rem, 2vw, 1.25rem)`.

## 2. Bottom Navigation (Mobile Fixed)

**Pure CSS Implementation**
- Use `position: fixed; bottom: 0; width: 100%; height: 65px;`.
- Flexbox with `justify-content: space-around` for icon distribution.
- `scroll-padding-bottom` on main content to prevent overlap.
- Hide on desktop with `@media (min-width: 600px) { display: none; }`.
- Add safe area support for notches: `padding-bottom: max(1rem, env(safe-area-inset-bottom))`.

## 3. Touch-Friendly Controls

**Large Targets & Swipe Support**
- Minimum 48px touch targets (WCAG 2.1 AAA).
- CSS scroll-snap for carousel/swipeable cards: `scroll-snap-type: x mandatory; scroll-snap-align: start;`.
- Use CSS transforms for rotation during swipe: `transform: translateX(var(--swipe-distance)) rotate(var(--swipe-angle));`.
- D-pad/joystick: Grid-based layout with directional buttons (8 positions) + center, use CSS `grid-template-areas` for visual clarity.
- HTMX can add `hx-swap="innerHTML"` to dynamically update jog values on button press.

## 4. Dark Theme Best Practices

**Color & Contrast**
- Use dark gray (#121212, #1C1C1C) instead of pure black—reduces eye strain.
- Soft white (#E0E0E0–#F5F5F5) for text instead of #FFFFFF; applies Google's opacity rule: 87% (high), 60% (medium), 38% (disabled).
- Minimum 4.5:1 contrast for body text, 3:1 for large text (WCAG 2.0 AA). APCA standard coming in 2026.
- Reduce saturation on dark backgrounds; add white/dark-gray tint to colors.

**Elevation Without Shadows**
- Light overlays and subtle borders convey depth on dark UIs.
- Surface elevation: lighter surface color = higher elevation.
- Use `border: 1px solid rgba(255, 255, 255, 0.12);` for subtle dividers.
- Gradients over shadows: `background: linear-gradient(135deg, rgba(255,255,255,0.08), transparent);`.

**Media Query**
- Use `@media (prefers-color-scheme: dark)` to auto-apply dark theme.

## 5. CSS Frameworks for Lightweight Dashboards

**Pico CSS** (Recommended for Jinja2 + HTMX)
- Zero dependencies, no JS, classless (pure semantic HTML).
- Built-in light/dark mode auto-detection.
- Lightweight (~10KB), scales fonts/spacing with viewport.
- Version 2.0 adds 100+ color theme combinations via CDN.
- Perfect for server-rendered templates.

**Open Props**
- CSS custom properties library (~5KB gzipped).
- Modular: import only what you need.
- No framework overhead, pure CSS variables.

**Custom CSS Approach** (Most Control)
- Define color system as CSS variables: `--surface: #1C1C1C`, `--text-primary: #E0E0E0`.
- Build utility classes for typography, spacing, borders.
- Minimal, predictable output.

## 6. Mobile Dashboard Card Patterns

**Swipeable Cards (Pure CSS)**
- Use `scroll-snap-type: x mandatory; scroll-behavior: smooth;` on container.
- Cards auto-snap into position with `scroll-snap-align: start;`.
- No JS required; HTMX can add `hx-trigger="swiperight"` for backend-driven logic.

**Collapsible Sections**
- Use `<details>` + `<summary>` for native collapsible behavior (no CSS needed).
- Style with CSS: `details > *:not(summary) { display: none; } details[open] > *:not(summary) { display: block; }`.

**Pull-to-Refresh** (HTMX + CSS)
- Track touch Y-delta via CSS custom property: `--pull-distance: calc(var(--touch-y) - var(--start-y))`.
- Show refresh UI when distance > threshold.
- HTMX `hx-get` on threshold reach to refetch data.

## 7. Real-Time Data on Mobile

**SSE vs. Polling (Battery Impact)**
- **SSE wins**: Pushes use 75–95% less battery than polling.
- Polling needs 3 round-trips (450ms on 3G); SSE delivers in 75ms.
- **Mobile networks**: More aggressive connection closure; use SSE with auto-reconnect logic.
- **Practical**: On Android/iOS, custom long-lived HTTP or Firebase Cloud Messaging may be required.
- **Recommendation**: Use SSE for ink levels; pause updates during print to save battery.

## 8. Ink Level Visualization (Small Screens)

**Best Approach: Horizontal Bars**
- Vertical bars get "squished" on narrow mobile; horizontal bars extend downward.
- Linear gauges ideal for mobile: less space than radial, clearer on 4–5″ screens.
- Use CSS Grid: `grid-template-columns: 1fr 1fr; gap: 1rem;` for 2-column layout (C, M, Y, K, W).

**Example HTML Structure**
```html
<div class="ink-levels">
  <div class="ink-level" style="--fill: 75%;" data-color="Cyan"></div>
  <div class="ink-level" style="--fill: 50%;" data-color="Magenta"></div>
</div>
```

**CSS**
```css
.ink-levels { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.ink-level {
  background: linear-gradient(to top, var(--primary), transparent var(--fill));
  border-radius: 0.5rem; height: 120px; border: 1px solid rgba(255,255,255,0.12);
}
```

## 9. Movement Controls (Jog/D-Pad)

**Grid-Based Layout**
- 3×3 grid for 8 directions + center (hold = continuous; tap = step).
- CSS: `display: grid; grid-template-columns: repeat(3, 60px); gap: 0.5rem;`.
- Use SVG or Unicode arrows (↑, ↓, ←, →) inside buttons.

**HTMX Integration**
- `hx-post="/jog"` with body params: `{ "axis": "X", "distance": "10", "direction": "+1" }`.
- `hx-trigger="mousedown"` for continuous jog; `hx-trigger="mouseup"` to stop.
- Optional: WebSocket for lower latency if CNC/printer supports it.

**Distance Increments** (Radio Button Group)
- 0.1mm, 1mm, 10mm presets.
- Selected via HTMX: `hx-on="change: hx-trigger(hx-post='/jog')"`.

---

## Summary

**Tech Stack**
- **Styling**: Pico CSS or custom CSS variables + clamp().
- **Responsive**: Mobile-first grid, container queries, scroll-snap for swipe.
- **Real-time**: SSE for ink levels; pause during print.
- **Dark mode**: Built into Pico; or use @media (prefers-color-scheme: dark).
- **Touch**: 48px+ targets, scroll-snap, D-pad grid.

**Key Wins**
- Zero npm/build tools required; pure server-rendered HTML.
- 75–95% battery savings with SSE over polling.
- Pico CSS provides dark mode + responsive scaling out-of-box.
- Horizontal bar charts for ink on small screens.

---

## Sources

- [CSS Grid Responsive Design: Mobile-First Approach](https://medium.com/codetodeploy/css-grid-responsive-design-the-mobile-first-approach-that-actually-works-194bdab9bc52)
- [Responsive Web Design Techniques 2026](https://lovable.dev/guides/responsive-web-design-techniques-that-work)
- [Container Queries in Real Projects 2025](https://medium.com/@vyakymenko/css-2025-container-queries-and-style-queries-in-real-projects-c38af5a13aa2)
- [Dark Mode UI Best Practices 2025](https://www.graphiceagle.com/dark-mode-ui/)
- [Dark Mode CSS Complete Guide](https://design.dev/guides/dark-mode-css/)
- [CSS Variables for Dark Mode](https://www.joshwcomeau.com/react/dark-mode/)
- [Bottom Navigation for Mobile Screens](https://dev.to/ziratsu/bottom-navigation-for-mobile-screens-23mk)
- [Pico CSS Minimal Framework](https://picocss.com/)
- [Swipeable Cards with CSS](https://community.appsmith.com/content/blog/ditch-bloat-building-swipeable-carousel-only-css)
- [SSE vs Polling Battery Impact](https://medium.com/@dasbabai2017/sse-vs-websocket-vs-long-polling-choosing-the-right-real-time-communication-strategy-61d990465ab1)
- [Mobile Gauge Visualization](https://www.visualcinnamon.com/2019/04/mobile-vs-desktop-dataviz/)
- [CNC/3D Printer Joystick Controls](https://github.com/hzeller/joystick-gcode-jog)

