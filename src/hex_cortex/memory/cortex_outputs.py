from __future__ import annotations

_OUTPUTS = [
    {
        "output_id": "write_text",
        "label": "Ecriture de texte",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "write_code",
        "label": "Ecriture de code",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "write_document",
        "label": "Creation de document structure",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "write_structured_data",
        "label": "Creation de donnees structurees",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "generate_plan",
        "label": "Generation de plan",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "request_tool",
        "label": "Demande d'outil gouvernee",
        "state": "candidate",
        "requires_operator": True,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "speak_text",
        "label": "Sortie vocale",
        "state": "candidate",
        "requires_operator": True,
        "raw_input_persistence_allowed": False,
    },
    {
        "output_id": "annotate_visual",
        "label": "Annotation visuelle",
        "state": "candidate",
        "requires_operator": False,
        "raw_input_persistence_allowed": False,
    },
]


def list_cortex_outputs() -> list[dict[str, object]]:
    return [dict(item) for item in _OUTPUTS]


def get_cortex_output(output_id: str) -> dict[str, object]:
    for item in _OUTPUTS:
        if item["output_id"] == output_id:
            return dict(item)
    return {
        "output_id": output_id,
        "state": "blocked",
        "blocker": "unknown_output_capability",
    }
