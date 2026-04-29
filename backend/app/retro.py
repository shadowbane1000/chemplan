"""AiZynthFinder wrapper.

Models are loaded once on first use and reused — loading takes several seconds
and the ONNX policy network sits at ~100MB resident.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any

from aizynthfinder.aizynthfinder import AiZynthFinder
from rdkit.Chem import AllChem, Draw

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.yml"

_finder: AiZynthFinder | None = None
_lock = Lock()


def _get_finder() -> AiZynthFinder:
    global _finder
    if _finder is None:
        with _lock:
            if _finder is None:
                f = AiZynthFinder(configfile=str(CONFIG_PATH))
                f.stock.select("zinc")
                f.expansion_policy.select("uspto")
                f.filter_policy.select("uspto")
                _finder = f
    return _finder


def _flip_to_forward(rxn_smiles: str) -> str:
    """AiZynthFinder writes reactions in retrosynthesis direction
    (`product >> precursors`). For procedure-card rendering we want the
    forward direction the chemist actually runs (`precursors >> product`).
    """
    if ">>" not in rxn_smiles:
        return rxn_smiles
    left, right = rxn_smiles.split(">>", 1)
    return f"{right}>>{left}"


def _attach_reaction_images(node: dict, depth: int = 0) -> None:
    """Walk the reaction tree and attach a base64 PNG to each reaction node.

    AiZynthFinder reaction nodes carry two SMILES representations:
      - `smiles`: TEMPLATE-mapped reaction (only atoms in the disconnection
         pattern keep their structure; the rest are stubs).
      - `metadata.mapped_reaction_smiles`: full atom-mapped reaction with
         every atom of the actual substrate and product.
    Always prefer the mapped form for rendering — drawing the template
    shows fragments instead of the real molecules. Flip the direction
    before rendering so the image reads as a forward synthesis step.
    """
    if node.get("type") == "reaction":
        rxn_smiles = (node.get("metadata") or {}).get("mapped_reaction_smiles") or node.get("smiles")
        if rxn_smiles:
            try:
                forward = _flip_to_forward(rxn_smiles)
                rxn = AllChem.ReactionFromSmarts(forward, useSmiles=True)
                img = Draw.ReactionToImage(rxn, subImgSize=(220, 220))
                buf = BytesIO()
                img.save(buf, format="PNG")
                node["image_png_b64"] = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:
                # Don't break the response if a single reaction fails to render.
                pass
    for child in node.get("children", []) or []:
        _attach_reaction_images(child, depth + 1)


def plan(smiles: str) -> dict[str, Any]:
    """Run retrosynthesis on a single target SMILES.

    Returns the top route as a nested dict (AiZynthFinder's native format)
    plus a small summary. Tree search is blocking and can take 30s+; the
    caller is responsible for not hammering this endpoint.
    """
    finder = _get_finder()
    finder.target_smiles = smiles
    finder.tree_search()
    finder.build_routes()

    if not finder.routes:
        return {"smiles": smiles, "routes": [], "stats": finder.extract_statistics()}

    top = finder.routes[0]
    tree = top["reaction_tree"]

    buf = BytesIO()
    tree.to_image().save(buf, format="PNG")
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    tree_dict = tree.to_dict()
    _attach_reaction_images(tree_dict)

    return {
        "smiles": smiles,
        "stats": finder.extract_statistics(),
        "top_route": {
            "score": top.get("score"),
            "metadata": top.get("route_metadata"),
            "tree": tree_dict,
            "image_png_b64": image_b64,
        },
    }
