---
version: alpha
name: Alumni CEG 1 Birni
description: Visual identity for the Alumni CEG 1 Birni — Zinder platform. A digital memory home for the 1980-1985 promotion. Journalistic gravitas, Sahelien restraint.
colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#A04A2C"
  neutral: "#F5F1EA"
  on-primary: "#F5F1EA"
  on-tertiary: "#FFFFFF"
  surface: "#FFFFFF"
  surface-variant: "#EEEAE2"
  in-memoriam: "#5A4A3D"
  whatsapp-green: "#1F6B4F"
  on-whatsapp-green: "#FFFFFF"
  ceremonial-gold: "#C9A227"
  on-ceremonial-gold: "#1A1C1E"
typography:
  display:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.01em
  h1:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.2
  h2:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: 500
    lineHeight: 1.3
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.02em
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1
    letterSpacing: 0.08em
rounded:
  sm: 4px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: 12px
    height: 44px
  button-primary-hover:
    backgroundColor: "#8A3F26"
    textColor: "{colors.on-tertiary}"
  button-secondary:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    height: 44px
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: 24px
  in-memoriam-frame:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.in-memoriam}"
    rounded: "{rounded.md}"
    padding: 32px
  whatsapp-link:
    backgroundColor: "{colors.whatsapp-green}"
    textColor: "{colors.on-whatsapp-green}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 12px
    height: 44px
  promo-badge:
    backgroundColor: "{colors.ceremonial-gold}"
    textColor: "{colors.on-ceremonial-gold}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.full}"
    padding: 4px
    height: 28px
---

# Alumni CEG 1 Birni — Design System

## Overview

The visual identity for the Alumni CEG 1 Birni platform serves a single purpose: to feel like a permanent home for the memory of a generation that shared decisive years in Zinder, Niger, between 1980 and 1985. It is journalistic in posture — unhurried, legible, archival — and Sahelien in palette: warm limestone foundations and a single terra-cotta accent that nods to the earthen architecture of Zinder's old city without resorting to ornamental cliché.

The platform must feel respectful enough to host an In Memoriam, structured enough to function as a directory, and quiet enough to recede when the photographs and testimonies take over. Decoration is restrained. Whitespace is generous. The design should not call attention to itself; it should call attention to the people it remembers.

## Colors

The palette is built around high-contrast neutrals with one warm accent. There is no second accent; chromatic restraint is itself a design decision. Reading the alumni directory or an In Memoriam page should feel like turning the page of a quality print publication, not browsing a corporate web app.

- **Primary (#1A1C1E):** Deep ink for headlines, body copy, and structural elements. Conveys gravity and permanence.
- **Secondary (#6C7278):** Sophisticated slate for borders, captions, dates, profession labels, and metadata. Never used as primary text.
- **Tertiary (#A04A2C):** "Sahel Terre Cuite" — the single interaction color. Used exclusively for primary CTAs ("Je suis un ancien"), active states, and rare highlights. Its scarcity makes each appearance meaningful.
- **Neutral (#F5F1EA):** Warm limestone — the page foundation. Softer than pure white, with a faint earthy undertone.
- **In Memoriam (#5A4A3D):** Earth brown reserved exclusively for In Memoriam frames and copy. Never appears outside that context.

## Typography

The type system pairs **Playfair Display** for editorial weight with **Inter** for utilitarian clarity. The juxtaposition mirrors the platform's dual nature: a place of memory (Playfair) and a place of function (Inter).

- **Display & Headlines:** Playfair Display 600. Used sparingly for major page titles, member names on profile pages, and In Memoriam dedications. Negative letter-spacing tightens display sizes.
- **Body:** Inter 400 at 16px is the floor. Per spec §8.3, the platform's audience is 55-65 years old and 16px is a non-negotiable accessibility baseline.
- **Labels:** Inter 500/600 with positive letter-spacing for metadata, button text, and tags.

Avoid Playfair below 18px — its serifs collapse and undermine readability for older users.

## Layout

A 12-column grid on desktop with 24px gutters; on mobile, content is full-width with 16px page padding. The maximum readable line length for body copy is 65ch — beyond that, prose becomes uncomfortable for the cohort. Card-based components stack vertically on mobile, never carousel-paged. Vertical rhythm follows the spacing scale (8/16/24/32/48/64).

## Components

- **button-primary:** The single CTA color (Sahel Terre Cuite) on neutral background. 44×44 minimum tactile target (spec §8.3). Used at most once per visible viewport.
- **card:** Surface white with 24px padding, 8px radius. Houses member profiles, testimonials, photo entries.
- **in-memoriam-frame:** Bordered surface variant (limestone shade darker than page background), earth-brown copy. Visually distinct from any other component on the site — designed to feel set apart, like a memorial plaque.
- **whatsapp-link:** Pill-shaped button in `whatsapp-green` with white copy. Used **only** for WhatsApp-related affordances (header CTA "Rejoindre le groupe WhatsApp", share-to-WA links, in-message WA-icon links). Never used as a generic UI button.
- **promo-badge:** Small pill with **`ceremonial-gold` background and deep-ink text** (gold-medal feel, WCAG AA compliant). Used for the "Promo 1980-1985" stamp, anniversary milestone marks, and the founding-date footer chip ("Depuis le 1ᵉʳ Septembre 2020"). Decorative role only — never wraps interactive content.

## Logo

The platform's emblem — *Les Retrouvailles* — predates this website. It was created for the WhatsApp group founded on 1 September 2020 and is the community's existing brand mark. We do not redesign it; we **host** it.

The logo combines a green crest (referencing the WhatsApp group's origin), gold laurels and ribbons (promotion / class anniversary), the *CEG 1 BIRNI DE ZINDER* wordmark, and the graduation cap and open book (school identity).

### Where the logo appears

- **Header (every page):** Top-left, 48px tall on mobile, 56px tall on desktop. The site's primary visual anchor.
- **Footer:** Same logo at 32px tall, paired with the founding date chip (`promo-badge`).
- **Favicon:** 32×32px crop of the central crest (deferred to P5 / Soft launch).
- **OG / share images:** Full logo over a `neutral` limestone background.

### Color extracts

The site palette includes two colors **drawn from the logo** and used sparingly to keep the visual link to the WhatsApp origin without saturating the UI:

- `whatsapp-green` (#1F6B4F): a desaturated forest variant of the logo's bright WhatsApp green. **Reserved for WhatsApp-related affordances only** (the `whatsapp-link` component, share icons, "online in WA group" indicators).
- `ceremonial-gold` (#C9A227): a muted version of the laurel/ribbon gold. **Reserved for promotion-anniversary marks** (`promo-badge`, milestone year labels, decorative top borders on commemorative frames).

The terra-cotta accent (`tertiary`, "Sahel Terre Cuite") remains the **single primary call-to-action color** — distinct from both logo-derived colors. This separation is deliberate: WhatsApp green pulls toward "the group we already are"; Sahel terra-cotta pulls toward "the new home we are building." They cohabit without competing.

### Logo do's and don'ts

- **Don't recolor the logo.** No alpha, no monochrome variants, no themed versions. The logo always appears full-color on a neutral or surface background.
- **Don't crop or alter the *Les Retrouvailles* wordmark** in the logo.
- **Don't use `whatsapp-green` as a generic UI primary** (page backgrounds, headers, CTAs unrelated to WhatsApp).
- **Don't use `ceremonial-gold` as text color** for body or labels — its low contrast against limestone fails WCAG AA.

## Do's and Don'ts

- **Do** keep the Sahel Terre Cuite accent for true calls-to-action; reusing it for decorative borders or info badges dilutes its meaning.
- **Don't** introduce a fourth accent color. The design budget is `tertiary` for primary CTAs, `whatsapp-green` for WhatsApp affordances, `ceremonial-gold` for anniversary marks. Any new highlight must come from one of these.
- **Don't** combine `whatsapp-green` and `tertiary` (terra-cotta) in the same component — both pull attention; they fight each other if placed side by side.
- **Do** use generous whitespace around photographs; they are the primary content.
- **Don't** compress vertical rhythm to fit "more above the fold." This audience reads carefully, not skims.
- **Do** keep the In Memoriam visual language reserved for In Memoriam contexts only.
- **Don't** use icon-only buttons (spec §8.3); always pair an icon with a text label.
