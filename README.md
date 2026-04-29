# chemplan

A grounded retrosynthesis planner. Draw a target, get a real route from AiZynthFinder, and ask a chat partner that actually knows the route why it picked what it picked.

> **Live demo:** _coming soon_ · **Walkthrough (~6 min):** _coming soon_ · **Source:** [GitHub](https://github.com/shadowbane1000/chemplan)

---

## Problem

A chemist planning a synthesis today bounces between three tools that don't talk to each other:

1. **A drawing tool** (ChemDraw, Ketcher) for the structure.
2. **A retrosynthesis engine or paper** for candidate routes.
3. **An LLM chat window** to reason out loud — "why this route, not that one?", "can I avoid this halogenation?", "what's a cheaper building block here?"

The LLM is the appealing part — it's the only one that handles open-ended *why* questions. But it's also the part that hallucinates structures, mis-balances equations, and confidently invents routes that don't exist. Used alone, it's not just unreliable — it's actively misleading.

## Gap

Nothing on the market combines all three:

- A real chemistry canvas you draw on.
- A real retrosynthesis engine that returns grounded routes (not LLM-generated ones).
- A chat that **knows the molecule, the proposed tree, and what the user has selected** — so its answers are grounded in actual data, not chemistry-flavored fluency.

The dedicated retro tools (AiZynthFinder, ASKCOS, IBM RXN) live in CLIs or Jupyter. The chat tools don't see the canvas. The canvas tools don't reason. The product is the seam.

## What I built

<!-- DRAFT — verify each bullet against deployed state before publishing. -->

A single-user web app:

1. **Ketcher canvas** (their official NPM package), dropped in as the drawing surface.
2. **Plan synthesis** button. Backend calls AiZynthFinder — open-source, USPTO-trained, running locally behind a FastAPI endpoint. No external API keys, no licensing.
3. **Route view.** The returned tree renders as a sequence of intermediate structures, with building-block SMILES marked at the leaves.
4. **Side-panel chat**, backed by the Claude API. The chat's context window includes the target SMILES, the full route tree, the building-block list, and whatever node the user has selected. Questions like *"why does it pick route 2 over route 1?"* and *"what if I want to avoid step 3?"* land on real data instead of fluency.

One target in, one annotated route plus a grounded chat partner out. That's the whole product.

## What's deliberately not here

Each cut is a real product someone wants. None of them is the bet I'm making first.

- **No accounts, auth, or persistence.** Single-user, in-memory, lose-on-refresh. The bet is on the interaction, not the workflow.
- **No commercial reaction databases** (Reaxys, SciFinder, CAS). AiZynthFinder + USPTO is enough to demonstrate grounded routes; commercial data is a licensing problem, not a product problem.
- **No quantum chemistry, DFT, yield prediction, or green-chem scoring.** Out of scope for "can the chat reason about a real route?".
- **No literature or patent search**, no per-step citation pulling.
- **No vendor / procurement lookup** for building blocks. Showing SMILES is enough; pricing and availability is a different product.
- **No reaction-condition optimization** (solvent, temperature, catalyst).
- **No 3D conformers, docking, or property prediction.** This is a planning tool, not a modeling tool.
- **No model training or fine-tuning.** AiZynthFinder ships with a pretrained model; I use it as-is.
- **No multi-route comparison UI.** One target → one route. Comparing routes is the obvious next feature and where most of the design work lives — worth doing once the chat is proven useful.

## What I'd do next

In rough priority order:

- **Multi-route view.** Show the top-N AiZynthFinder routes side-by-side, scored on step count, building-block availability, and estimated cost. Chat reasons across all of them. This is the highest-leverage next move — most of the chat questions a chemist actually wants to ask are *comparative*.
- **Building-block availability lookup** against vendor APIs (Sigma, eMolecules) so "is this commercially available?" stops being a guess.
- **Per-step reaction-condition suggestions**, grounded in literature examples pulled from the open patent corpus.
- **Save / share / fork a route.** Minimum viable project model — enough to come back to a plan tomorrow, not enough to be a LIMS.
- **Pluggable retrosynthesis backend.** AiZynthFinder is the default; ASKCOS, IBM RXN, or an internal model should drop in behind the same interface.
- **Literature grounding in chat.** When the user asks "has anyone done this step before?", the chat cites a specific open-patent reaction, not a hallucinated DOI.

Anything that doesn't make routes more trustworthy or the chat more grounded isn't on this list.
