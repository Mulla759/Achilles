"""One Pydantic model, four dialects of JSON Schema.

`achilles/models.py` is the single contract (invariant 4), and every provider
wants that contract expressed slightly differently:

* **Anthropic** takes the Pydantic class directly via the SDK — nothing here is
  needed for it.
* **OpenAI-compatible** (`response_format: json_schema, strict: true`) accepts
  `$defs`/`$ref` but demands that *every* property appear in `required` and that
  every object set `additionalProperties: false`.
* **Google** (`responseSchema`) is an OpenAPI 3.0 subset: no `$ref`, no `$defs`,
  no `additionalProperties`, and it ignores most annotation keywords.

So the transforms are: keep the refs but force everything required (OpenAI), or
inline the refs and strip down to the supported keyword set (Google).

Forcing every field required is safe here precisely because `Resume` was
designed flat and closed — every optional field has a scalar empty default, so a
model that emits `""` or `[]` for one produces exactly the value the default
would have supplied.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

# Keywords Google's responseSchema understands. Everything else is dropped
# rather than passed through, because unknown keywords are a 400 there, not a
# silent ignore.
_GOOGLE_KEEP = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "items",
    "properties",
    "required",
    "propertyOrdering",
    "minItems",
    "maxItems",
}

# Annotation-only keywords that OpenAI's strict mode rejects outright.
_OPENAI_DROP = {"default", "title", "$schema", "examples", "deprecated", "readOnly"}


class SchemaError(RuntimeError):
    """The contract can't be expressed in a provider's dialect.

    Raised at build time from a developer mistake (a recursive model, say), not
    from anything a user can paste, which is why it is not an AchillesError.
    """


def _walk(node: Any, fn: Any) -> Any:
    """Depth-first rewrite of every dict node in a schema tree."""
    if isinstance(node, dict):
        return fn({k: _walk(v, fn) for k, v in node.items()})
    if isinstance(node, list):
        return [_walk(v, fn) for v in node]
    return node


def openai_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Strict-mode JSON Schema: refs preserved, every property required."""
    raw = deepcopy(model.model_json_schema())

    def fix(node: dict[str, Any]) -> dict[str, Any]:
        node = {k: v for k, v in node.items() if k not in _OPENAI_DROP}
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            # Strict mode requires the full property list here; optionality is
            # expressed by the value the model returns, not by omission.
            node["required"] = list(node["properties"].keys())
        return node

    out = _walk(raw, fix)
    out["additionalProperties"] = False
    return out


def google_schema(model: type[BaseModel]) -> dict[str, Any]:
    """OpenAPI-subset schema with every `$ref` inlined."""
    raw = deepcopy(model.model_json_schema())
    defs: dict[str, Any] = raw.pop("$defs", {})

    def inline(node: Any, seen: tuple[str, ...] = ()) -> Any:
        if isinstance(node, list):
            return [inline(v, seen) for v in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            if name in seen:
                raise SchemaError(
                    f"{model.__name__} is recursive through {name!r}; Google's "
                    "responseSchema cannot express that. Flatten the model."
                )
            target = defs.get(name)
            if target is None:
                raise SchemaError(f"Dangling $ref {ref!r} in {model.__name__}.")
            merged = {**deepcopy(target), **{k: v for k, v in node.items() if k != "$ref"}}
            return inline(merged, (*seen, name))

        out: dict[str, Any] = {}
        for key, value in node.items():
            if key not in _GOOGLE_KEEP:
                continue
            if key == "properties" and isinstance(value, dict):
                out[key] = {k: inline(v, seen) for k, v in value.items()}
            else:
                out[key] = inline(value, seen)

        # `const` from a single-value Literal survives as an enum of one.
        if "const" in node and "enum" not in out:
            out["enum"] = [node["const"]]
            out.setdefault("type", "string")

        if out.get("type") == "object" and "properties" in out:
            # Ordering is advisory, but it nudges the model to emit fields in
            # contract order, which makes streamed partial output readable.
            out["propertyOrdering"] = list(out["properties"].keys())
            out["required"] = list(out["properties"].keys())
        return out

    return inline(raw)
