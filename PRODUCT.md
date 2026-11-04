# Tape

Record, replay and diff LLM agent runs, as an open-source Python library with a pytest plugin and a CLI.

## Who it is for
Engineers who ship tool-using LLM agents and need to know when a prompt or code change alters what the agent does. Secondary audience: recruiters and hiring managers reading the project from a CV link.

## What it must prove
A one-line prompt change can silently change an agent's behaviour (the demo: a friendlier prompt makes a refund agent skip its policy check and refund a $489 order). Tape catches it on the first model call, for free, in CI.

## Truths
- Anthropic SDK only for now; streaming not recorded.
- Demo tapes come from a scripted stand-in model, labelled as such.
- No users, benchmarks or adoption numbers exist yet; never claim any.

## Voice
Plain, specific, engineer to engineer. Concrete numbers from the demo, no hype.
