"""Streaming chat endpoint backed by Claude.

Each turn the frontend sends the full message history plus the current
canvas SMILES and the current AiZynthFinder route (if any). We inject a
structured <context> block into the latest user message so the chat is
grounded in actual data, not whatever the model happens to remember.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to backend/.env (see backend/.env.example)."
            )
        _client = Anthropic()
    return _client


SYSTEM_PROMPT = """\
You are a chemistry assistant embedded in chemplan, a retrosynthesis-planning tool. The user draws a target molecule on a Ketcher canvas and runs AiZynthFinder (USPTO-trained, open-source) to get a candidate route. Your job is to help them reason about the target, the route, and the building blocks — grounded in the data they actually have, not chemistry-flavored fluency.

Ground rules:
- The canvas SMILES and the route tree (when present) are the source of truth. Refer to them. If the user asks about a structure or step, look at what's in the <context> block — don't invent.
- Be honest about the limits of what AiZynthFinder gives you. For each step you have: an atom-mapped reaction SMILES, a reaction template, the policy probability, and a USPTO precedent count (how many patent reactions used this template). You do NOT have: solvents, temperatures, catalysts, equivalents, times, yields, or specific patent citations. When the user asks "how do I run this step," frame conditions as plausible defaults for that disconnection class — never as a citation of what was actually used.
- Be concise. Chemists are busy. Dense and accurate beats padded.
- When asked "why this route" or "why not route 2," reason about step count, building-block availability (in-stock vs not), policy probability, chemical sensibility — don't just describe the route.
- Use SMILES strings when referring to specific structures. The user's tool understands them.

What chemplan currently exposes (so you don't invent UI):
- Drawing a target on the Ketcher canvas.
- A single "Plan synthesis" button that runs AiZynthFinder with default settings (USPTO expansion model + filter + ringbreaker, ZINC stock) and shows the top-1 route.
- This chat, which sees the canvas SMILES and the current route.

What chemplan does NOT currently expose:
- Tunable expansion depth, iteration count, or any AiZynthFinder configuration.
- Alternative or expanded stock sets (e.g. Enamine REAL, Sigma, custom in-house).
- Multi-route comparison — only the top-1 route is rendered.
- Per-step condition lookup, vendor pricing, or any settings UI.

When a feature would help the user, name it honestly as "this would require chemplan to add X" — not as "click Y" or "adjust setting Z." Do not suggest the user re-run with different settings; there are no settings to adjust. The current tool is intentionally minimal.
"""


def _build_context_block(canvas_smiles: str | None, plan: dict | None) -> str:
    parts = ["<context>"]

    if canvas_smiles and canvas_smiles.strip():
        parts.append(f"  <canvas_smiles>{canvas_smiles.strip()}</canvas_smiles>")
    else:
        parts.append("  <canvas_smiles>(empty)</canvas_smiles>")

    if plan:
        stats = plan.get("stats", {}) or {}
        parts.append("  <route>")
        parts.append(f"    <solved>{stats.get('is_solved')}</solved>")
        parts.append(f"    <steps>{stats.get('number_of_steps')}</steps>")
        parts.append(f"    <precursors_in_stock>{stats.get('precursors_in_stock', '')}</precursors_in_stock>")
        parts.append(f"    <precursors_not_in_stock>{stats.get('precursors_not_in_stock', '')}</precursors_not_in_stock>")
        top_route = plan.get("top_route") or {}
        score = top_route.get("score") or {}
        if "state score" in score:
            parts.append(f"    <state_score>{score['state score']:.4f}</state_score>")
        tree = top_route.get("tree")
        if tree:
            parts.append("    <tree_json>")
            parts.append(json.dumps(tree, indent=2))
            parts.append("    </tree_json>")
        parts.append("  </route>")
    else:
        parts.append("  <route>(no synthesis plan run yet)</route>")

    parts.append("</context>")
    return "\n".join(parts)


def stream_chat(
    history: list[dict],
    canvas_smiles: str | None,
    plan: dict | None,
) -> Iterator[bytes]:
    """Stream the chat response as NDJSON.

    history must end with a {"role": "user", "content": "..."} entry — the
    new question. Prior turns are passed through as-is.
    """
    if not history or history[-1].get("role") != "user":
        yield (json.dumps({"type": "error", "message": "history must end with a user message"}) + "\n").encode()
        return

    try:
        client = _get_client()
    except Exception as exc:
        yield (json.dumps({"type": "error", "message": str(exc)}) + "\n").encode()
        return

    context = _build_context_block(canvas_smiles, plan)
    last = history[-1]
    augmented = list(history[:-1]) + [{
        "role": "user",
        "content": f"{context}\n\n{last['content']}",
    }]

    try:
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=16000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            messages=augmented,
        ) as stream:
            for text in stream.text_stream:
                yield (json.dumps({"type": "delta", "text": text}) + "\n").encode()
            final = stream.get_final_message()
            usage = final.usage
            yield (json.dumps({
                "type": "done",
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                },
            }) + "\n").encode()
    except Exception as exc:
        yield (json.dumps({"type": "error", "message": str(exc)}) + "\n").encode()
