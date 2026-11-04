---
name: Tape
description: Agents drift, Tape keeps the receipts. Warm paper and charcoal, cassette reels made of type, ASCII receipts.
colors:
  paper: "#F1EEE7"
  ink: "#232323"
  soft: "#5E5B55"
  dark: "#1E1E1E"
  rule: "#BDB8AE"
  button: "#DDD9D1"
  dot: "#FF6A1A"
  red: "#E5432B"
  green: "#2E7D4F"
typography:
  heading: { fontFamily: "Geist", fontWeight: 500, letterSpacing: "-0.03em" }
  body: { fontFamily: "Geist", fontWeight: 400 }
  label: { fontFamily: "Geist Mono", fontWeight: 500, note: "uppercase labels, receipts and code" }
rounded: { sm: "6px", md: "10px" }
---

## Overview
Inspired by contentarchitecture.dev and made Tape's own. An agent run is an itemised log, so the site talks in receipts. The hero splits warm paper (copy) from a dark dotted panel holding two cassette reels whose rings are the agent's real recorded calls; side B carries the bug in red. Scrolling reaches a replay receipt that prints line by line while the total counts up to $489.

## Colours
All colours are CSS variables at the top of the page (`scripts/build_site.py`), so the site can be recoloured in one place. Red marks the bug only. The orange dot is a small accent on the primary button and the GitHub link. Green marks passing checks.

## Typography
Geist for headings and body, Geist Mono uppercase for labels, receipts and code.

## Components
- Floating dark nav pill with a ticker (stops under reduced motion).
- Text reels: SVG text on circular paths, stretched to the circumference so each ring wraps once; they turn slowly.
- ASCII receipts generated in Python so borders always align; dot leaders between label and value.
- Dark band with three steps (record, replay, diff), tabbed test and failure output, itemised spec receipt, dark closing band with the install command.

## Motion
Reels idle-rotate; the receipt prints once on first view and the $489 counts up beside it; sections fade up once. All off under reduced motion.
