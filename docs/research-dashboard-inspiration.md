# Dashboard Design Inspiration Research

**Date:** 2025-03-23
**Focus:** Industrial/manufacturing dashboards + 3D printer control UI patterns for DTG printer mobile-first design

---

## 1. Best-in-Class 3D Printer UIs (Closest Precedent)

### Mainsail (Klipper)
- **Layout:** Desktop sidebar + mobile column-drop responsive
- **Mobile:** Separate mobile/tablet layouts; auto-hides/reorders panels based on screen size
- **Cards:** Collapsible panel system, customizable widget arrangement
- **Strength:** Adaptive dashboard per device class; remembers user layout
- **Pattern:** Responsive column system adapts 4-column desktop to stacked mobile

### Fluidd (Klipper)
- **Layout:** Multi-column widget system (up to 4 columns desktop)
- **Mobile:** "Narrow mode" below 560px; widgets auto-collapse to dropdowns
- **Cards:** Responsive widgets adapt to column width
- **Strength:** Graceful degradation; AppBtnCollapseGroup hides controls into menus
- **Pattern:** Column monitoring detects width; layout persists user preferences

### Bambu Lab App (Consumer 3D Printer)
- **Layout:** Top bar with device switcher; vertical card layout
- **Mobile:** Native app; intuitive swipe/tap controls; real-time webcam
- **Controls:** Left-side menu switches between "Printer" detail view (axis/temp control) and main dashboard
- **Strength:** Seamless device switching; high-res camera feed; smooth animations
- **Pattern:** Multi-device aware; detail page for jogging (XYZ movement controls)

### Creality Cloud App
- **Layout:** Intuitive dashboard with animated buttons + helpful mini-instructions
- **Mobile:** Tablet optimization; refreshed UI/UX; all-in-one slicer + control + repo
- **Controls:** Print 3MF, capture timelapse, real-time fan/performance metrics
- **Strength:** Smooth UX polish; tablet-optimized workflows
- **Pattern:** Integrated slicer + dashboard reduces context switching

### Prusa Connect App
- **Layout:** Sortable printer list (status, temp, filament) + detail view with history
- **Mobile:** Camera snapshot display; print job history; per-printer detail page
- **Controls:** Live camera feed integration; job queue management
- **Strength:** Multi-printer list view; clean detail drill-down
- **Pattern:** List → Detail navigation; printer-centric organization

---

## 2. Industrial SCADA/Grafana Patterns

### Grafana (Industrial IoT Standard)
- **Layout:** Flexible drag-and-drop dashboard grid
- **Design:** Dark theme standard; real-time millisecond updates
- **Cards:** Time-series panels, gauges, heatmaps, stat cards
- **Color:** Professional grays, accent colors for alerts (red/orange/yellow)
- **Strength:** Industry standard for manufacturing; scales from boardroom to shop floor
- **Pattern:** Grid-based, threshold-driven alarms, role-based views

### SCADA (Ignition/ThingsBoard)
- **Layout:** SVG-based responsive symbols; column-drop or layout-shifter patterns
- **Mobile:** Full control on phone/tablet; breakpoint-based reflow
- **Cards:** SVG gauge elements; status indicators; control toggles
- **Color:** High contrast for accessibility; status color coding (green/yellow/red)
- **Strength:** Mobile-responsive SVG scales to any screen; full plant floor control on phone
- **Pattern:** Responsive breakpoints; Layout Shifter (content moves vs. reflows)

---

## 3. Mobile-First Navigation Patterns

### Bottom Navigation Bar (Best for Industrial)
- **Rule:** 3–5 destinations max (odd numbers preferred: 3 or 5)
- **Reach:** "Thumb zone" — lower 30% of screen for comfortable one-handed use
- **Icons:** Simple geometry + short 1-word labels; universally recognizable
- **Tap area:** Larger touch targets reduce errors
- **Best for:** Dashboard, Controls, History, Settings (4–5 tabs)
- **Precedent:** Bambu Lab, Creality Cloud, Prusa Connect all use bottom nav or side nav on mobile

### Hamburger Menu (Alternative)
- **Use when:** More than 5 top-level destinations needed
- **Risk:** Hides content; requires user discovery
- **Avoid for:** Core controls (print, jog, status) — these should be always visible

---

## 4. Visual Design Recommendations

### Color Scheme (Dark Theme)
- **Background:** #1a1a1a or #0f0f0f (dark gray/near-black)
- **Card:** #2a2a2a (slightly lighter panels for contrast)
- **Text:** #ffffff (primary), #b0b0b0 (secondary/dimmed)
- **Accents:**
  - Active/success: #00d084 (bright green)
  - Warning: #ffa500 (orange)
  - Error: #ff4444 (red)
  - Info: #00a8ff (bright blue)
- **Precedent:** Grafana, Ignition, Bambu Lab all use dark with bright accent colors

### Card Design
- **Border:** 1px subtle border (#3a3a3a) or no border (rely on shadow)
- **Spacing:** 16px padding inside cards; 12px gap between cards
- **Shadow:** Minimal (0 2px 8px rgba(0,0,0,0.3))
- **Corner:** 8–12px border-radius (modern, not harsh squares)
- **Icon:** Large, centered, status color; 48–64px for mobile
- **Typography:** 14px body, 18–20px heading, 12px labels

### Status Indicators
- **Dot + text:** 12px colored circle + label (e.g., "Ready" / "Printing" / "Error")
- **Gauge:** Circular gauge for temp, fill, progress (easy to scan)
- **Bar:** Horizontal progress bar for job progress, queue
- **Precedent:** Mainsail, Fluidd use simple text + icons; Grafana uses gauges + numbers

---

## 5. Key Interaction Patterns for DTG Control

| Feature | Pattern | Example |
|---------|---------|---------|
| **Printer Status** | Large status card (top) with temp gauge + job progress | Bambu, Creality |
| **Jogging Controls** | Dedicated "Control" tab; directional pad (±X ±Y ±Z) + increment selector | Bambu detail view |
| **Job Queue** | List view with swipe-to-delete; status badge per job | Prusa list |
| **Settings** | Bottom nav "Settings" tab; collapsible sections (Power, Network, Temps) | Standard mobile UX |
| **History** | Tab with print logs; date filter; stats (time, cost, success rate) | Prusa, Fluidd |
| **Device Switch** | Top bar dropdown or sidebar for multi-printer (if needed) | Bambu Handy |

---

## 6. Mobile Breakpoints (Responsive Strategy)

- **Desktop (≥1200px):** Sidebar + 2–3 column main content; all controls visible
- **Tablet (768px–1199px):** Column drop; sidebar collapses; panels rearrange
- **Mobile (<768px):** Single column; bottom nav; collapsible sections; full-width cards
- **Precedent:** Mainsail/Fluidd use <560px as narrow threshold; Ignition uses Layout Shifter

---

## 7. What Makes It Look "Professional"

✓ Consistent spacing (8–12–16px rhythm)
✓ Dark theme (reduces eye strain in industrial environments)
✓ Large touch targets (44–48px minimum)
✓ Color coding for status (green/yellow/red globally understood)
✓ Real-time updates (no refresh button needed; WebSocket/SSE)
✓ Minimal animations (subtle fades/slides; <300ms)
✓ One-handed navigable (thumb-zone nav at bottom)
✓ Clear labels + icons (no mystery meat)
✓ Responsive breakpoints (not cramped on small screens)
✓ High contrast text (WCAG AA minimum)

---

## Design Inspiration Sources

- [Grafana Industrial IoT Visualization](https://grafana.com/blog/industrial-iot-visualization-how-grafana-powers-industrial-automation-and-iiot/)
- [Mainsail 3D Printer Dashboard](https://docs.mainsail.xyz/features/dashboard-organisation/)
- [Fluidd Responsive Design](https://docs.fluidd.xyz/customize/layout)
- [Bambu Handy App](https://wiki.bambulab.com/en/studio-handy/handy/bambu-handy-quick-start)
- [Creality Cloud App](https://www.creality.com/blog/how-to-control-and-monitor-your-3d-printer-remotely-from-anywhere)
- [Prusa Mobile App](https://blog.prusa3d.com/prusa-mobile-app-for-android-and-ios_102881/)
- [SCADA Mobile-Responsive Patterns](https://inductiveautomation.com/resources/webinar/5-mobileresponsive-layout-strategies)
- [Bottom Navigation Mobile UX (2025)](https://blog.appmysite.com/bottom-navigation-bar-in-mobile-apps-heres-all-you-need-to-know/)
- [Dribbble Dark Dashboard Designs](https://dribbble.com/tags/dark-theme-dashboard)
- [Material Design Navigation](https://m1.material.io/patterns/navigation.html)
