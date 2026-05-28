---
description: Load design system rules before writing any frontend code for this project
---

You are working on a luxury web project. Before writing any HTML/CSS, apply these rules:

## Fonts
- Headings: Cormorant Garamond (serif, italic for emphasis)
- Body / UI: Inter (sans-serif, weight 300)
- Pair display with clean sans — never use the same font for both

## Colors
- Base: `#121717` (--black-900)
- Surface: `#0f1b1b` (--black-800)
- Accent: `#7B3347`
- Never use default Tailwind blue/indigo as primary

## Typography
- Large headings: `letter-spacing: -0.03em`, `line-height: 0.85–1.1`
- Body: `line-height: 1.65–1.8`, `font-weight: 300`
- Labels / nav: `letter-spacing: 0.15em`, `text-transform: uppercase`, `font-size: 0.6875rem`

## Spacing & Depth
- Use intentional spacing tokens, not random Tailwind steps
- Surfaces have layers: base → elevated → floating
- Shadows: layered, color-tinted, low opacity — never flat `shadow-md`

## Animations
- Only animate `transform` and `opacity`
- Never use `transition-all`
- Use spring-style easing (`power3.out`, `power2.inOut`)
- GSAP for entrance animations, ScrollTrigger for scroll-driven effects

## Interactive States
- Every clickable element needs `hover`, `focus-visible`, and `active` states

## Images
- Add gradient overlay: `linear-gradient(to top, rgba(6,14,14,0.90), transparent)`
- Use `object-fit: cover` on all images

## Hard Rules
- Do not add sections or content not asked for
- Do not "improve" a reference — match it exactly
- Always serve on localhost, never `file:///`
- Active site: `sites/elyse/index.html` at `http://localhost:3000/sites/elyse/`
