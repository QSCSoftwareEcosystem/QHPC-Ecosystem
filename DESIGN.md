---
name: EQO-QSC
description: A QSC orchestration control plane for quantum-HPC workflows
colors:
  quark-red: "#AA1E2E"
  force-blue: "#131E29"
  wave-gray: "#CFD2D3"
  carbon: "#030609"
  paper: "#F4F7F8"
  white: "#FFFFFF"
  success: "#0E7A4B"
  active: "#1668B3"
  warning: "#8A5A08"
typography:
  display:
    fontFamily: "Open Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2rem, 4.5vw, 4.6rem)"
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.045em"
  title:
    fontFamily: "Open Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Open Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.6875rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "0.1em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "28px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.quark-red}"
    textColor: "{colors.white}"
    rounded: "{rounded.sm}"
    padding: "12px 18px"
  command-surface:
    backgroundColor: "{colors.force-blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.lg}"
    padding: "clamp(24px, 4vw, 56px)"
  telemetry-cell:
    backgroundColor: "{colors.carbon}"
    textColor: "{colors.wave-gray}"
    padding: "12px 20px"
---

# Design System: EQO-QSC

## Overview

**Creative North Star: "The Orchestration Control Plane"**

EQO-QSC is composed like a scientific operations console, not a collection of interchangeable cards. A compact navigation dock, continuous telemetry rail, asymmetric command deck, live event stream, and contextual assistant establish one operating surface. The high-resolution static binary field supplies depth and quantum character through negative space; it does not compete with data.

The interface is precise and calm, with a single large hierarchy shift in the first viewport. Open Sans carries the QSC institutional voice while monospaced labels distinguish system state, identifiers, and instrumentation.

## Colors

Quark Red is the decisive action and identity color. Force Blue and carbon form the command environment. Wave Gray supplies readable technical contrast. White and paper surfaces are reserved for dense records, forms, and tables. Semantic green, blue, amber, and red always appear with a glyph or text state.

## Typography

Use Open Sans for all product copy and headings. Use the monospaced system stack only for identifiers, telemetry, code, timestamps, and compact instrumentation labels. The command-deck statement is the display moment; elsewhere use a restrained operational scale with a 14–16px body floor.

## Layout

Desktop uses a 170px navigation dock with a prominent 146px QSC wordmark, a compact command header, and a full-width telemetry band. The overview is a twelve-column asymmetric deck: the orchestration command occupies the larger field, while the QEC instrument and recent-run stream form the secondary column. Avoid four-up metric-card grids.

At tablet widths the dock contracts to 132px with a 112px wordmark and the deck becomes a two-column arrangement with the command field spanning first. On mobile, navigation becomes a horizontally scrollable dock with the 104px wordmark, telemetry remains a single horizontal rail, and the command deck collapses into a deliberate vertical reading order.

## Elevation & Depth

Depth comes primarily from layered translucent carbon/Force Blue planes over the static binary canvas. Use blur and low, broad shadows for separation; use hairline borders and red rules for structure. Dense data surfaces may become nearly opaque for legibility.

## Shapes

Most controls use 6–10px corners. Major command surfaces may use 16px corners. Hexagonal clipping belongs to QSC status marks and small signal details, not every container. Rounded pills are limited to state badges.

## Components

- Navigation dock: compact two-letter signal plus a persistent readable label; active state uses a Quark Red marker.
- Command header: view identity, global tool search, ChatQEC trigger, and refresh action in one continuous bar.
- Telemetry rail: inline measures separated by rules, never individual floating cards.
- Workflow launcher: published workflows are direct launch rows with nodes, outputs, and version visible before action.
- Run stream: compact event rows with workflow, state, target, and time; the whole row opens the run record.
- ChatQEC dock: contextual conversation with shared state and a clear route to the full research-assistant workspace.
- QEC instrument: compact ASCII visualization with a caption and explicit reduced-motion state.

## Do's and Don'ts

- Do expose the static binary field through deliberate negative space.
- Do make the current task, live state, and primary action immediately legible.
- Do preserve exact identifiers and backend-derived values.
- Do keep focus indicators, readable labels, reduced motion, and state text.
- Don't rebuild the overview as a conventional hero followed by rows of cards.
- Don't use decorative purple, generic neon gradients, stock photography, or unverified scientific claims.
- Don't shrink supporting text below a comfortable operational reading size.
