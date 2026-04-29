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

    return {
        "smiles": smiles,
        "stats": finder.extract_statistics(),
        "top_route": {
            "score": top.get("score"),
            "metadata": top.get("route_metadata"),
            "tree": tree.to_dict(),
            "image_png_b64": image_b64,
        },
    }
