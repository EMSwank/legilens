# Accessibility Checklist (per PR)

Every PR touching a frontend route or interactive component must check off each item below before merge. WCAG 2.1 Level AA is the conformance target.

Automated coverage (jest-axe + `@axe-core/playwright`) catches roughly 30–40% of issues. The rest of this list is manual verification.

## Per-route checks

For each new or modified route:

- [ ] **Headings:** single `<h1>`; heading levels descend without skipping
- [ ] **Landmarks:** `<main>` present; nav/footer use semantic landmarks
- [ ] **Page title:** `metadata.title` exports a unique, descriptive title
- [ ] **Reading order:** Tab traversal matches visual order
- [ ] **Skip link:** "Skip to content" link works (still focuses `#main`)
- [ ] **Keyboard:** every interactive element reachable via Tab; no traps; Enter/Space activates
- [ ] **Focus visible:** visible focus ring on every interactive element
- [ ] **Screen reader:** VoiceOver pass — every control announces its name + role + state; status changes announced
- [ ] **Contrast:** sample every text/background pair via Chrome DevTools color picker; ≥4.5:1 text, ≥3:1 UI
- [ ] **Color-only:** no information conveyed by color alone (icons, labels, or text accompany color cues)
- [ ] **Zoom:** 200% browser zoom — no content lost, no overlap
- [ ] **Reflow:** 320px viewport (Chrome DevTools device mode) — no horizontal scroll for prose
- [ ] **Mobile touch targets:** all interactive elements ≥ 44×44 px on small viewport
- [ ] **Reduced motion:** any animations respect `prefers-reduced-motion`
- [ ] **Status messages:** dynamic state changes use `role="status"` or `role="alert"`
- [ ] **Forms:** every control has an associated `<label>`; error messages announced

## Per-component checks

For each new or modified interactive component:

- [ ] **Semantic element:** uses native HTML where possible (`<button>` not `<div onClick>`)
- [ ] **Accessible name:** has visible text, `aria-label`, or `aria-labelledby`
- [ ] **Decorative content:** icons/svgs without semantic meaning use `aria-hidden="true"`
- [ ] **States:** disabled/loading/error states announced and visually distinct (not color-only)

## Tooling

- jest-axe runs in every component test — failures block CI
- `@axe-core/playwright` runs after each E2E page navigation — failures block CI
- Manual VoiceOver (Cmd+F5 on macOS): top-to-bottom read-through per route
- Manual keyboard-only walkthrough per route
