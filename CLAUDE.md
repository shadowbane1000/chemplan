# CLAUDE.md

Notes for Claude working in this repo. Keep brief.

## Source of truth on scope

`README.md` is a **product memo**, not a how-to-build doc. The "what's deliberately not here" section is load-bearing — if a request would add something from that list, push back before implementing. v1 is small on purpose.

If `README.md` and this file disagree on scope, `README.md` wins. Update this file or ask; don't drift.

## Stage

- **v0.5** — Ketcher canvas + Claude API chat sidepanel that sees the canvas. No retrosynthesis yet.
- **v1** — adds AiZynthFinder backend, route rendering, and chat context that includes the route tree + selection.

Default to assuming we are building toward v0.5 first unless told otherwise.

## Stack assumptions (until proven wrong)

- Frontend: Ketcher's official NPM package. Whatever framework is lightest around it (React is fine — Ketcher ships a React wrapper).
- Backend (v1): Python, because AiZynthFinder is a Python library. FastAPI is the obvious fit.
- LLM: Claude API directly. Use the latest Sonnet/Opus model id; don't pin to an older one.
- Local-first. No cloud deploy story in v1.

If a different choice is better for a specific reason, name the reason — don't swap silently.

## Working style

- Don't add features outside the v1 list in `README.md`. If something feels missing, the answer is usually "v2".
- Don't introduce auth, persistence, multi-user, or vendor integrations without being asked. Those are explicit cuts.
- The chat's value is *grounded* answers. Anything that erodes grounding (e.g. letting the LLM invent SMILES the canvas doesn't have) is a bug, not a feature.
