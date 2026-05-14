import json, re


def _to_title(name: str) -> str:
    words = re.split(r'[_\s]+', name)
    return "".join(w.title() for w in words if w)


def _scalar_xml_type(value) -> tuple[str, int]:
    if isinstance(value, bool):  return "Boolean", 10
    if isinstance(value, int):   return "Long", 20
    if isinstance(value, float): return "Double", 20
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            return "String", 150
        length = max(30, len(value) * 2)
        return "String", min(length, 500)
    return "String", 30


def _infer_xml_type(value) -> tuple[str, int]:
    if isinstance(value, dict):  return "JSONObject", 500
    if isinstance(value, list):  return "JSONObject", 16000
    return _scalar_xml_type(value)


def _first_scalar(lst: list):
    for item in lst:
        if isinstance(item, list):
            result = _first_scalar(item)
            if result is not None:
                return result
        elif not isinstance(item, dict):
            return item
    return None

def generate_xml_template(raw_json: str, root_template_name: str) -> str:
    data = json.loads(raw_json)
    blocks: list[tuple[str, list[dict]]] = []

    def process_object(obj: dict, tpl_name: str):
        fields = []
        for key, value in obj.items():

            if isinstance(value, dict):
                nested_name = _to_title(key)
                fields.append({
                    "name": key, "type": "JSONObject",
                    "template": nested_name, "max_len": 500,
                })
                process_object(value, nested_name)

            elif isinstance(value, list):
                _process_array_field(key, value, fields)

            else:
                xml_type, max_len = _scalar_xml_type(value)
                fields.append({"name": key, "type": xml_type, "max_len": max_len})

        blocks.append((tpl_name, fields))

    def _process_array_field(key: str, value: list, parent_fields: list):
        if not value:
            _emit_flat_array(key, "String", 30, parent_fields)
            return

        first = value[0]

        # Case A: list of objects
        if isinstance(first, dict):
            nested_name = _to_title(key)
            parent_fields.append({
                "name": key, "type": "JSONArray",
                "template": nested_name, "max_len": 500,
            })
            process_object(first, nested_name)

        elif isinstance(first, list):
            outer_name = _to_title(key) + "OuterArray"
            inner_name = _to_title(key) + "InnerArray"

            parent_fields.append({
                "name": key, "type": "JSONObject",
                "template": outer_name,
                "array_size": "0-10000", "min_len": 1, "max_len": 16000,
            })

            blocks.append((outer_name, [{
                "is_index_key": True,
                "index": "0-100000",
                "type": "JSONArray",
                "template": inner_name,
                "max_len": 15000,
                "array_size": "0-10000",
            }]))

            # inner template: one index key with scalar type
            scalar = _first_scalar(first)
            s_type, s_max = _scalar_xml_type(scalar) if scalar is not None else ("String", 65)
            blocks.append((inner_name, [{
                "is_index_key": True,
                "index": "0-10000",
                "type": s_type,
                "max_len": s_max,
            }]))

        else:
            s_type, s_max = _scalar_xml_type(first)
            _emit_flat_array(key, s_type, s_max, parent_fields)

    def _emit_flat_array(key: str, s_type: str, s_max: int, parent_fields: list):
        array_tpl_name = _to_title(key) + "Array"
        parent_fields.append({
            "name": key,
            "index": "0-1000",
            "type": "JSONArray",
            "template": array_tpl_name,
            "max_len": 200,
        })
        blocks.append((array_tpl_name, [{
            "is_index_key": True,
            "index": "0-1000",
            "type": s_type,
            "max_len": s_max,
        }]))

    process_object(data, root_template_name)

    lines = []
    for idx, (tpl_name, fields) in enumerate(blocks):
        if idx > 0:
            lines.append("")
        lines.append(f'<jsontemplate name="{tpl_name}">')
        for f in fields:
            lines.append("    " + _render_key(f))
        lines.append("</jsontemplate>")

    return "\n".join(lines)


def _render_key(f: dict) -> str:
    parts = []
    if f.get("is_index_key"):
        parts.append(f'index="{f["index"]}"')
    else:
        parts.append(f'name="{f["name"]}"')
        if "index" in f:           
            parts.append(f'index="{f["index"]}"')

    parts.append(f'type="{f["type"]}"')

    if "template"   in f: parts.append(f'template="{f["template"]}"')
    if "array_size" in f: parts.append(f'array-size="{f["array_size"]}"')
    if "min_len"    in f: parts.append(f'min-len="{f["min_len"]}"')

    parts.append(f'max-len="{f["max_len"]}"')

    return f'<key {" ".join(parts)}/>'
