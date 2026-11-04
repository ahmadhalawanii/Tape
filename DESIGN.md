---
name: Tape
description: Flight recorder for AI agents. The orange box over a dark readout.
colors:
  international-orange: "#FF5A1F"
  readout-black: "#0D0D0C"
  readout-panel: "#171716"
  readout-line: "#2B2A27"
  ink: "#F2F0EA"
  dim: "#A9A69D"
  reflective-white: "#FBFAF6"
  ok-green: "#6BD49B"
  warn-amber: "#F2C457"
typography:
  display: { fontFamily: "Archivo", fontWeight: 900, note: "wdth 112-125, uppercase for the hero" }
  heading: { fontFamily: "Archivo", fontWeight: 800 }
  body: { fontFamily: "Archivo", fontWeight: 400 }
  data: { fontFamily: "JetBrains Mono", fontWeight: 400 }
rounded: { sm: "3px", md: "6px" }
---

## Overview
Tape is a flight recorder for AI agents, so the identity is the recorder itself: an international-orange box with black placard lettering and a white reflective stripe, opening onto a near-black readout. Orange is committed at region scale (hero, closing band, report header), never sprinkled as an accent.

## Colors
International orange owns the box and marks alarms on the readout (skipped calls, the divergence). Green means a step that still happens correctly; amber means changed arguments. Text on orange is always readout black, never white.

## Typography
Archivo set wide (width 112-125) and heavy for display, like aviation placards; regular width for body. JetBrains Mono only for code, tool calls and data. The generated report uses system faces so it stays one offline file.

## Components
- Flight-data trace: two recorder tracks (before, after) drawn as black lines with boxed event tags; a dashed line marks where the requests diverged; alarm events are reflective-white tags. It draws once left to right, and top to bottom on phones; it stays still under reduced motion.
- Data plate: bordered spec list with two rivets, orange monospace labels.
- Report track: before and after tool calls aligned on a spine, coloured by skipped, new or changed.

## Do and don't
Do keep one orange region per screen section. Don't add glow, gradients, or hazard stripes; the single reflective stripe is the only band.
