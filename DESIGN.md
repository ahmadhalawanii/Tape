---
name: Tape
description: The product demo is the design. A calm charcoal developer-tool site where an interactive replay shows what Tape does.
colors:
  charcoal: "#0B0C0E"
  panel: "#121317"
  panel-2: "#17181D"
  raised: "#1D1F25"
  well: "#0F1013"
  line: "#24262D"
  line-2: "#2F323A"
  ink: "#EDEEF0"
  soft: "#C4C7CE"
  dim: "#8B8F98"
  gutter: "#4A4E57"
  lime: "#C8F05A"
  lime-ink: "#11160A"
  coral: "#FF6B57"
  coral-ink: "#1A0B08"
  coral-soft: "#FFB3A8"
  amber: "#F5C350"
  keyword: "#A9B4FF"
typography:
  display: { fontFamily: "Geist", fontWeight: 600, letterSpacing: "-0.045em" }
  body: { fontFamily: "Geist", fontWeight: 400 }
  code: { fontFamily: "Geist Mono", fontWeight: 400 }
rounded: { sm: "6px", md: "10px", lg: "14px", xl: "18px" }
---

## Overview
Tape's site sells by showing. The hero is an interactive replay: switch the refund agent's prompt from v1 to v2, watch one rule disappear, the run replay step by step, `issue_refund $489` light up, and the test turn red. Everything else stays calm so that moment carries the page.

## Colors
Charcoal ground with layered panels. Lime means recorded, passing, or the brand mark. Coral means divergence, a skipped rule, or a failing test. Amber marks changed arguments in the report. Colour is used for state, never decoration.

## Typography
Geist for UI and headings, set tight (-0.045em on the hero); Geist Mono for prompts, tool calls, code and terminals. The generated report lists Geist first but falls back to system faces, because it is a single offline file.

## Components
- Demo panel: segmented control with a sliding thumb, prompt pane, run timeline on a spine, terminal strip with PASSED/FAILED badge.
- Flow: three connected columns (record, replay, diff) on one rule, the last tick lime.
- Editor: tabbed code panel with line numbers; PR comment: the CI markdown summary rendered.
- Spec grid: two columns of short facts on hairlines, the limits stated in the last cell.

## Motion
One authored moment: the demo replays when it first scrolls into view (once), steps rising 380ms apart with an exponential ease-out. Sections fade up on first view. All of it is off under reduced motion.
