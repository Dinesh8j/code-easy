"""
core/template_generator.py
───────────────────────────
Generates security.xml <jsontemplate> blocks from a JSON sample.
No Streamlit imports — fully testable in isolation.
"""

import json, re


def _infer_xml_type(value) -> tuple[str, int]:
    """Return (xml_type, max_len) for a JSON value."""
    if isinstance(value, dict):   return "JSONObject", 500
    if isinstance(value, list):
        if value and isinstance(value[0], dict): return "JSONArray", 500
        return "JSONArray", 200
    if isinstance(value, bool):   return "Boolean", 10
    if isinstance(value, int):    return "Long", 20
    if isinstance(value, float):  return "Double", 20
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            return "String", 150
        length = max(30, len(value) * 2)
        return "String", min(length, 500)
    return "String", 30


def _to_title(name: str) -> str:
    """snake_case / camelCase → TitleCase for nested template names."""
    words = re.split(r'[_\s]+', name)
    return "".join(w.title() for w in words if w)


def generate_xml_template(raw_json: str, root_template_name: str) -> str:
    """
    Parse JSON and produce security.xml <jsontemplate> blocks.
    Nested objects/arrays-of-objects get their own block.
    """
    data   = json.loads(raw_json)
    blocks: list[tuple[str, list[dict]]] = []

    def process_object(obj: dict, tpl_name: str):
        fields = []
        for key, value in obj.items():
            xml_type, max_len = _infer_xml_type(value)
            entry = {"name": key, "type": xml_type, "max_len": max_len}
            if isinstance(value, dict):
                nested_name = _to_title(key)
                entry["template"] = nested_name
                process_object(value, nested_name)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                nested_name = _to_title(key)
                entry["template"] = nested_name
                process_object(value[0], nested_name)
            fields.append(entry)
        blocks.append((tpl_name, fields))

    process_object(data, root_template_name)

    lines = []
    for idx, (tpl_name, fields) in enumerate(blocks):
        if idx > 0:
            lines.append("")
        lines.append(f'<jsontemplate name="{tpl_name}">')
        for f in fields:
            if "template" in f:
                lines.append(
                    f'    <key name="{f["name"]}" type="{f["type"]}" '
                    f'template="{f["template"]}" max-len="{f["max_len"]}"/>'
                )
            else:
                lines.append(
                    f'    <key name="{f["name"]}" type="{f["type"]}" max-len="{f["max_len"]}"/>'
                )
        lines.append("</jsontemplate>")

    return "\n".join(lines)
