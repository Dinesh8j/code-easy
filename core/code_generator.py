"""
core/code_generator.py
───────────────────────
Pure logic for generating Scala case classes and Python dataclasses from JSON.
No Streamlit imports — fully testable in isolation.
"""

import json, re, io, zipfile
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def to_class_name(s: str) -> str:
    return "".join(p.title() for p in s.split("_"))


def strip_comments(raw: str) -> tuple[str, dict]:
    """Remove # and // comments; extract ALLOWED VALUES hints."""
    hints, clean = {}, []
    for line in raw.splitlines():
        m = re.search(r'[#/]+\s*\[?ALLOWED VALUES[-:]?\s*([\w,\s]+)\]?', line, re.IGNORECASE)
        if m:
            vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
            fm = re.search(r'"(\w+)"\s*:', line)
            if fm: hints[fm.group(1)] = vals
        line = re.sub(r'\s*#[^\n"]*$', '', line)
        line = re.sub(r'\s*//[^\n"]*$', '', line)
        clean.append(line)
    return "\n".join(clean), hints


def parse_defaults(raw: str) -> dict:
    """Parse 'fieldName = value' lines into a dict."""
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        fname, val = line.split("=", 1)
        fname, val = fname.strip(), val.strip()
        if fname and val:
            result[fname] = val
    return result


def build_zip(files: list[dict], root_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f["filename"], f["code"])
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Type inference
# ─────────────────────────────────────────────────────────────────────────────

def infer_scala_type(v) -> str:
    if isinstance(v, bool):  return "Boolean"
    if isinstance(v, int):   return "Long" if abs(v) > 2_147_483_647 else "Int"
    if isinstance(v, float): return "Double"
    if isinstance(v, str):   return "String"
    if isinstance(v, list):  return f"Seq[{infer_scala_type(v[0])}]" if v else "Seq[Any]"
    if v is None:            return "Option[String]"
    return "String"


def infer_python_type(v) -> str:
    if isinstance(v, bool):  return "bool"
    if isinstance(v, int):   return "int"
    if isinstance(v, float): return "float"
    if isinstance(v, str):   return "str"
    if isinstance(v, list):  return f"list[{infer_python_type(v[0])}]" if v else "list"
    if v is None:            return "Optional[str]"
    return "str"


# ─────────────────────────────────────────────────────────────────────────────
# Scala generation
# ─────────────────────────────────────────────────────────────────────────────

def _scala_default_expr(ft: str, raw_val: str) -> str:
    raw = raw_val.strip()
    if raw.lower() in ("none", "null"):                      return "None"
    if raw.startswith('"') and raw.endswith('"'):            return raw
    if re.match(r'^-?\d+(\.\d+)?[lLfFdD]?$', raw):         return raw
    if raw.lower() in ("true", "false"):                     return raw.lower()
    if ft.startswith("Option["):
        inner = ft[7:-1]
        return f'Some("{raw}")' if inner == "String" else f'Some({raw})'
    if ft == "String":                                       return f'"{raw}"'
    return raw


def _scala_enum(fn: str, vals: list, pkg: str) -> dict:
    cn = to_class_name(fn)
    L = []
    if pkg: L.append(f"package {pkg}\n")
    L.append("import play.api.libs.json._\n")
    L.append(f"sealed trait {cn}\n\nobject {cn} {{")
    for v in vals: L.append(f"  case object {v} extends {cn}")
    L.append(f"\n  val values: Seq[{cn}] = Seq({', '.join(vals)})\n")
    L.append(f"  implicit val format: Format[{cn}] = new Format[{cn}] {{")
    L.append(f"    override def reads(json: JsValue): JsResult[{cn}] = json match {{")
    for v in vals: L.append(f'      case JsString("{v}") => JsSuccess({v})')
    L.append(f'      case JsString(s) => JsError(s"Unknown {cn}: $s. Allowed: {", ".join(vals)}")')
    L.append( '      case _           => JsError("Expected JSON string for ' + cn + '")')
    L.append( '    }')
    L.append(f'    override def writes(t: {cn}): JsValue = JsString(t.toString)')
    L.append( '  }'); L.append('}')
    return {"filename": f"{cn}.scala", "description": f"Sealed trait · {', '.join(vals)}", "code": "\n".join(L)}


def _scala_case_class(cn: str, fields: dict, nested_map: dict, pkg: str,
                      enum_reg: dict, option_fields=None, defaults=None) -> dict:
    L = []
    if pkg: L.append(f"package {pkg}\n")
    L.append("import play.api.libs.json._\n")
    option_fields = set(option_fields or [])
    defaults      = defaults or {}
    fd = []
    for fn, fv in fields.items():
        if fn in nested_map:
            base_ft = nested_map[fn]
            ft = f"Option[{base_ft}]" if fn in option_fields else base_ft
        elif fn in enum_reg:
            base_ft = enum_reg[fn]
            ft = f"Option[{base_ft}]" if fn in option_fields else base_ft
        elif fv is None:
            ft = "Option[String]"
        elif isinstance(fv, dict):
            base_ft = to_class_name(fn)
            ft = f"Option[{base_ft}]" if fn in option_fields else base_ft
        else:
            ft = infer_scala_type(fv)
            if fn in option_fields and not ft.startswith("Option["):
                ft = f"Option[{ft}]"
        fd.append((fn, ft))
    L.append(f"case class {cn}(")
    for i, (fn, ft) in enumerate(fd):
        default_str = ""
        if fn in defaults:
            default_str = f" = {_scala_default_expr(ft, defaults[fn])}"
        elif ft.startswith("Option["):
            default_str = " = None"
        comma = "," if i < len(fd) - 1 else ""
        L.append(f"  {fn}: {ft}{default_str}{comma}")
    L.append(")\n")
    L.append(f"object {cn} {{")
    L.append(f"  implicit val FORMAT: Format[{cn}] = new Format[{cn}] {{\n")
    L.append(f"    override def reads(json: JsValue): JsResult[{cn}] = {{")
    L.append(f"      val result = {cn}(")
    for i, (fn, ft) in enumerate(fd):
        comma = "," if i < len(fd) - 1 else ""
        if ft.startswith("Option["):
            L.append(f'        {fn} = (json \\ "{fn}").asOpt[{ft[7:-1]}]{comma}')
        elif fn in defaults:
            dexpr = _scala_default_expr(ft, defaults[fn])
            L.append(f'        {fn} = (json \\ "{fn}").asOpt[{ft}].getOrElse({dexpr}){comma}')
        else:
            L.append(f'        {fn} = (json \\ "{fn}").as[{ft}]{comma}')
    L.append("      )\n      JsSuccess(result)\n    }\n")
    L.append(f"    override def writes(obj: {cn}): JsValue = Json.obj(")
    for i, (fn, ft) in enumerate(fd):
        L.append(f'      "{fn}" -> obj.{fn}{"," if i < len(fd) - 1 else ""}')
    L.append("    )\n  }\n}")
    return {"filename": f"{cn}.scala", "description": "Case class · explicit reads/writes", "code": "\n".join(L)}


def generate_scala(raw: str, root: str, pkg: str, extra_enums: dict,
                   option_fields=None, defaults=None) -> list[dict]:
    clean, comment_enums = strip_comments(raw)
    data = json.loads(clean)
    all_enums = {**comment_enums, **extra_enums}
    files, enum_reg = [], {}
    for fn, vals in all_enums.items():
        cn = to_class_name(fn); enum_reg[fn] = cn
        files.append(_scala_enum(fn, vals, pkg))

    def collect(obj, name):
        classes, nm = [], {}
        for k, v in obj.items():
            if isinstance(v, dict):
                nn = to_class_name(k); nm[k] = nn; classes.extend(collect(v, nn))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                nn = to_class_name(k); nm[k] = f"Seq[{nn}]"; classes.extend(collect(v[0], nn))
        classes.append((name, obj, nm)); return classes

    for cn, fields, nm in collect(data, root):
        files.append(_scala_case_class(cn, fields, nm, pkg, enum_reg, option_fields, defaults))
    return files


# ─────────────────────────────────────────────────────────────────────────────
# Python generation
# ─────────────────────────────────────────────────────────────────────────────

def _python_default_expr(ft: str, raw_val: str) -> str:
    raw = raw_val.strip()
    if raw.lower() in ("none", "null"):                return "None"
    if raw.startswith('"') and raw.endswith('"'):      return raw
    if re.match(r'^-?\d+(\.\d+)?$', raw):             return raw
    if raw.lower() in ("true", "false"):               return raw.capitalize()
    if ft in ("str",) or "str" in ft:                 return f'"{raw}"'
    return raw


def _python_enum(fn: str, vals: list) -> dict:
    cn = to_class_name(fn)
    L = ["from enum import Enum", "", f"class {cn}(str, Enum):"]
    for v in vals: L.append(f'    {v} = "{v}"')
    L += [
        "", "    @classmethod", f'    def from_str(cls, value: str) -> "{cn}":',
        "        try:", "            return cls(value)", "        except ValueError:",
        "            allowed = ', '.join(e.value for e in cls)",
        f'            raise ValueError(f"Unknown {cn}: {{value}}. Allowed: {{allowed}}")'
    ]
    return {"filename": f"{cn}.py", "description": f"Enum · {', '.join(vals)}", "code": "\n".join(L)}


def _python_dataclass(cn: str, fields: dict, nested_map: dict, enum_reg: dict,
                      option_fields=None, defaults=None) -> dict:
    imports = {"from dataclasses import dataclass, field", "from typing import Optional, List"}
    for v in enum_reg.values(): imports.add(f"from {v} import {v}")
    for nn in set(nested_map.values()):
        base = nn.replace("List[", "").replace("]", ""); imports.add(f"from {base} import {base}")
    L = list(sorted(imports)) + ["", "", "@dataclass", f"class {cn}:"]
    option_fields = set(option_fields or [])
    defaults      = defaults or {}
    fd = []
    for fname, fv in fields.items():
        if fname in nested_map:
            base_ft = nested_map[fname]
            ft = f"Optional[{base_ft}]" if fname in option_fields else base_ft
        elif fname in enum_reg:
            base_ft = enum_reg[fname]
            ft = f"Optional[{base_ft}]" if fname in option_fields else base_ft
        elif fv is None:
            ft = "Optional[str]"
        elif isinstance(fv, dict):
            base_ft = to_class_name(fname)
            ft = f"Optional[{base_ft}]" if fname in option_fields else base_ft
        else:
            ft = infer_python_type(fv)
            if fname in option_fields and not ft.startswith("Optional["):
                ft = f"Optional[{ft}]"
        fd.append((fname, ft, fv))
        if "List" in ft or "list" in ft:
            L.append(f"    {fname}: {ft} = field(default_factory=list)")
        elif fname in defaults:
            L.append(f"    {fname}: {ft} = {_python_default_expr(ft, defaults[fname])}")
        else:
            L.append(f"    {fname}: {ft} = None")
    L += ["", "    @classmethod", f'    def from_dict(cls, data: dict) -> "{cn}":', "        return cls("]
    for i, (fname, ft, fv) in enumerate(fd):
        comma = "," if i < len(fd) - 1 else ""
        if fname in enum_reg:
            L.append(f'            {fname}={enum_reg[fname]}.from_str(data["{fname}"]){comma}')
        elif fname in nested_map:
            raw = nested_map[fname]
            if "List" in raw:
                inner = raw.replace("List[", "").replace("]", "")
                L.append(f'            {fname}=[{inner}.from_dict(i) for i in data.get("{fname}", [])]{comma}')
            else:
                L.append(f'            {fname}={raw}.from_dict(data["{fname}"]){comma}')
        elif fname in defaults:
            L.append(f'            {fname}=data.get("{fname}", {_python_default_expr(ft, defaults[fname])}){comma}')
        else:
            L.append(f'            {fname}=data.get("{fname}"){comma}')
    L += ["        )", "", "    def to_dict(self) -> dict:", "        result = {}"]
    for fname, ft, fv in fd:
        if fname in enum_reg:
            L.append(f'        if self.{fname}: result["{fname}"] = self.{fname}.value')
        elif fname in nested_map:
            raw = nested_map[fname]
            if "List" in raw:
                L.append(f'        result["{fname}"] = [i.to_dict() for i in self.{fname}]')
            else:
                L.append(f'        if self.{fname}: result["{fname}"] = self.{fname}.to_dict()')
        else:
            L.append(f'        result["{fname}"] = self.{fname}')
    L.append("        return result")
    return {"filename": f"{cn}.py", "description": "Dataclass · from_dict/to_dict", "code": "\n".join(L)}


def generate_python(raw: str, root: str, extra_enums: dict,
                    option_fields=None, defaults=None) -> list[dict]:
    clean, comment_enums = strip_comments(raw)
    data = json.loads(clean)
    all_enums = {**comment_enums, **extra_enums}
    files, enum_reg = [], {}
    for fn, vals in all_enums.items():
        cn = to_class_name(fn); enum_reg[fn] = cn
        files.append(_python_enum(fn, vals))

    def collect(obj, name):
        classes, nm = [], {}
        for k, v in obj.items():
            if isinstance(v, dict):
                nn = to_class_name(k); nm[k] = nn; classes.extend(collect(v, nn))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                nn = to_class_name(k); nm[k] = f"List[{nn}]"; classes.extend(collect(v[0], nn))
        classes.append((name, obj, nm)); return classes

    for cn, fields, nm in collect(data, root):
        files.append(_python_dataclass(cn, fields, nm, enum_reg, option_fields, defaults))
    return files
