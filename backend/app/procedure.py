"""Per-step procedure expansion.

Given a reaction from an AiZynthFinder route, return a structured
procedure (operations + reagents + conditions + hazards) plus a
grounding tag describing where the procedure came from and how much
to trust it.

v1.5 only implements grounding.source = "llm_only". The schema leaves
room for "ord", "patent_extracted", and "lab_tested" so the same API
contract works once those backends exist.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to backend/.env."
            )
        _client = Anthropic()
    return _client


# ---------- Schema -----------------------------------------------------------


class Reagent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Common chemical name, e.g. 'acetic anhydride'")
    smiles: Optional[str] = Field(
        None, description="SMILES if known. Null for unknown solvents/standard reagents not worth canonicalizing."
    )
    role: Literal[
        "substrate", "reagent", "catalyst", "solvent", "base", "acid", "ligand", "additive"
    ]
    equiv: Optional[float] = Field(
        None, description="Stoichiometric equivalents relative to the limiting substrate. Null for solvents."
    )
    amount_ml_per_mmol: Optional[float] = Field(
        None,
        description="Volume in mL per mmol of substrate, for solvents only. Null for non-solvents.",
    )


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: int = Field(..., description="1-indexed sequential operation number")
    action: Literal[
        "charge", "add", "stir", "heat", "cool", "hold", "filter",
        "wash", "extract", "dry", "concentrate", "distill",
        "recrystallize", "quench", "evaporate", "transfer", "other",
    ]
    description: str = Field(..., description="One-sentence human-readable description")
    reagents: list[Reagent] = Field(default_factory=list)
    temperature_c: Optional[float] = Field(None, description="Target temperature in degrees Celsius. Null for ambient or N/A.")
    duration_min: Optional[float] = Field(None, description="Duration in minutes. Null when not applicable (e.g. instantaneous addition).")
    atmosphere: Optional[Literal["air", "N2", "Ar", "vacuum"]] = None
    notes: Optional[str] = None


class Grounding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["llm_only", "ord", "patent_extracted", "lab_tested"]
    confidence: Literal["low", "medium", "high"]
    cost_usd: float = Field(..., description="Cost incurred to produce this answer (rough estimate, USD).")
    details: str = Field(..., description="One-sentence explanation of how this answer was produced and what its limits are.")


class StepProcedure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaction_smiles: str
    disconnection_summary: str = Field(..., description="One-sentence description of the bond change and reaction class.")
    operations: list[Operation]
    workup: Optional[str] = Field(None, description="Free-text note on isolation/purification not captured in operations.")
    hazards: list[str] = Field(default_factory=list)
    grounding: Grounding


# ---------- Prompt -----------------------------------------------------------


SYSTEM_PROMPT = """\
You generate structured laboratory procedures for individual steps of a retrosynthesis route. The route comes from AiZynthFinder (USPTO-trained); the user is using chemplan to scope what an autonomous lab would need to actually run each step.

Your output must be valid JSON matching the StepProcedure schema. Be concrete: commit to specific equivalents, temperatures, and durations rather than hand-waving with phrases like "for several hours" or "at elevated temperature." Pick plausible defaults for the reaction class.

Rules:
- The atom-mapped reaction SMILES uses AiZynthFinder's retrosynthesis notation: `product >> precursors`. The product (left of `>>`) is what's being made; the precursors (right of `>>`, dot-separated) are what's being combined. Generate the procedure as the FORWARD reaction — combining the precursors to make the product.
- Reagents under operations should reference the precursors from the SMILES by chemical name and SMILES. Add typical solvents, bases, catalysts as appropriate for the disconnection class.
- For amide formations from anhydride + amine: typical conditions are aqueous or alcoholic solvent, mild warming (40-80°C), 30 min to a few hours. No catalyst needed.
- For amide formations from acid + amine: coupling reagent (HATU, EDC, T3P, etc.) + base (DIPEA, Et3N), DMF or DCM, room temperature, several hours.
- For Suzuki couplings: Pd(PPh3)4 or Pd(dppf)Cl2 (1-5 mol%), K2CO3 or Cs2CO3, dioxane/water or toluene/EtOH/water, 80-100°C, 4-12 hours, N2 atmosphere.
- For reductions of nitro to amine: H2 + Pd/C in EtOH at room temp, OR Fe/AcOH, OR SnCl2.
- For acid-catalyzed reactions: strong acid (H2SO4, TfOH), neat or in chlorinated solvent, often warming.
- Default to safe atmospheres (N2 for anything Pd-catalyzed or air-sensitive; air OK for most aqueous/protic chemistry).
- Default workup to standard practice: filter or extract → wash → dry → concentrate → recrystallize/chromatograph.

Grounding (this is required and load-bearing):
- For v1.5, ALWAYS set grounding.source to "llm_only", confidence to "low", cost_usd to your best estimate of the per-call inference cost (typically $0.01-$0.05 for this kind of structured output), and details should plainly say something like "Generated from typical conditions for the reaction class. No precedent lookup performed; specific values like temperature and duration are plausible defaults, not literature-cited."
- Do NOT claim higher confidence or different sources. The honest grounding tag is what makes this useful.

Be concise in `description` and `notes`. Don't pad."""


# ---------- Endpoint ---------------------------------------------------------


def _user_prompt(reaction_smiles: str, metadata: dict[str, Any] | None) -> str:
    # Prefer the fully atom-mapped reaction (with full substrate structures);
    # fall back to the template-mapped form only if it's missing.
    full_rxn = (metadata or {}).get("mapped_reaction_smiles") or reaction_smiles

    parts = [
        "Generate a StepProcedure for the following reaction.",
        "",
        f"Reaction SMILES (full atom-mapped, product >> precursors): {full_rxn}",
    ]
    if metadata:
        if metadata.get("classification") and metadata["classification"] != "0.0 Unrecognized":
            parts.append(f"Classification: {metadata['classification']}")
        if metadata.get("library_occurence"):
            parts.append(f"USPTO precedent count: {metadata['library_occurence']}")
        if metadata.get("policy_probability") is not None:
            parts.append(f"Policy probability: {metadata['policy_probability']:.3f}")
    return "\n".join(parts)


def expand_step(reaction_smiles: str, metadata: dict[str, Any] | None) -> StepProcedure:
    client = _get_client()

    schema = StepProcedure.model_json_schema()

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4000,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
        messages=[{"role": "user", "content": _user_prompt(reaction_smiles, metadata)}],
    )

    # Find the JSON block in the response and parse.
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text

    data = json.loads(text)
    return StepProcedure.model_validate(data)
