import html
import uuid
from collections.abc import Mapping, Sequence

class JSON:
    """A simple tree view for nested dictionaries and lists."""

    def __init__(self, data: Mapping | Sequence, expand_depth: int = 1):
        self.data = data
        self.expand_depth = expand_depth
        self.rendered = json_to_html_tree(self.data, expand_depth=self.expand_depth)

    def _repr_html_(self):
        return self.rendered

#############################################################################
# Internals 
#############################################################################

_INDENT_REM = 0.5  # indent step per level (in rem)

def _to_html(obj, *, expand_depth=1, level=0, seen=None, key=None, key_is_index=False):
    """
    Render `obj` as a <details>/<summary> tree.
    - key/key_is_index: when this node is a child, include its key/index inline in <summary>.
    - expand_depth: >0 => node starts open; pass (expand_depth-1) to children.
    - level: used only for computing indent (applied to child rows).
    """
    if seen is None:
        seen = set()

    def esc(x):
        return html.escape(str(x), quote=False)

    def key_prefix_html(k, is_index):
        if k is None:
            return ""
        if is_index:
            return f'<span class="jt-key">[{k}]</span><span class="jt-punct">: </span>'
        return f'<span class="jt-key">"{esc(k)}"</span><span class="jt-punct">: </span>'

    def fmt_primitive(v):
        if isinstance(v, str):
            return f'<span class="jt-str">"{esc(v)}"</span>'
        if v is None:
            return '<span class="jt-null">null</span>'
        if isinstance(v, bool):
            return f'<span class="jt-bool">{"true" if v else "false"}</span>'
        if isinstance(v, (int, float)):
            return f'<span class="jt-num">{v}</span>'
        return f"<span>{esc(repr(v))}</span>"

    is_map = isinstance(obj, Mapping)
    is_seq = isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray))

    # Only track containers for circular refs
    if is_map or is_seq:
        oid = id(obj)
        if oid in seen:
            return '<div class="jt-leaf"><em>[Circular]</em></div>'
        seen.add(oid)

    # ----- dict -----
    if is_map:
        size = len(obj)
        open_attr = " open" if expand_depth > 0 else ""
        # If this dict is a child, show the key inline in its summary
        summary_label = f'{key_prefix_html(key, key_is_index)}{{}} Object <span class="jt-punct">({size})</span>'
        # Build children
        rows = []
        for k, v in obj.items():
            if isinstance(v, Mapping):
                # child container (dict): put key in child's <summary>, indent that <details>
                rows.append(
                    _to_html(
                        v,
                        expand_depth=max(expand_depth - 1, 0),
                        level=level + 1,
                        seen=seen,
                        key=k,
                        key_is_index=False,
                    )
                )
            elif isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
                # child container (list)
                rows.append(
                    _to_html(
                        v,
                        expand_depth=max(expand_depth - 1, 0),
                        level=level + 1,
                        seen=seen,
                        key=k,
                        key_is_index=False,
                    )
                )
            else:
                # primitive child -> single line
                rows.append(
                    f'<div class="jt-leaf" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                    f"{key_prefix_html(k, False)}{fmt_primitive(v)}</div>"
                )
        return (
            f'<details class="jt-details"{open_attr} style="margin-left:{level * _INDENT_REM}rem">'
            f'<summary class="jt-summary">{summary_label}</summary>'
            + "".join(rows)
            + "</details>"
        )

    # ----- list/tuple -----
    if is_seq:
        size = len(obj)
        open_attr = " open" if expand_depth > 0 else ""
        summary_label = f'{key_prefix_html(key, key_is_index)}[] Array <span class="jt-punct">({size})</span>'
        rows = []
        for i, v in enumerate(obj):
            if isinstance(v, Mapping):
                rows.append(
                    _to_html(
                        v,
                        expand_depth=max(expand_depth - 1, 0),
                        level=level + 1,
                        seen=seen,
                        key=i,
                        key_is_index=True,
                    )
                )
            elif isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
                rows.append(
                    _to_html(
                        v,
                        expand_depth=max(expand_depth - 1, 0),
                        level=level + 1,
                        seen=seen,
                        key=i,
                        key_is_index=True,
                    )
                )
            else:
                rows.append(
                    f'<div class="jt-leaf" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                    f"{key_prefix_html(i, True)}{fmt_primitive(v)}</div>"
                )
        return (
            f'<details class="jt-details"{open_attr} style="margin-left:{level * _INDENT_REM}rem">'
            f'<summary class="jt-summary">{summary_label}</summary>'
            + "".join(rows)
            + "</details>"
        )

    # ----- primitive leaf -----
    # (Root can be primitive if called directly.)
    if key is not None:
        return (
            f'<div class="jt-leaf" style="margin-left:{level * _INDENT_REM}rem">'
            f"{key_prefix_html(key, key_is_index)}{fmt_primitive(obj)}</div>"
        )
    return f'<div class="jt-leaf" style="margin-left:{level * _INDENT_REM}rem">{fmt_primitive(obj)}</div>'


def json_to_html_tree(obj, *, key=None, expand_depth=1):
    """Return a UUID-scoped HTML block with styles and the rendered tree."""
    uid = f"jt-{uuid.uuid4().hex[:8]}"
    body = _to_html(
        obj,
        expand_depth=expand_depth,
        level=0,
        seen=set(),
        key=key,
        key_is_index=False,
    )
    style = f"""
<style>
#{uid} {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px; line-height: 1.45;
}}
#{uid} summary {{
  cursor: pointer;
  list-style: none;
  display: inline-flex;
  align-items: baseline;
  gap: 0.25rem;
}}
#{uid} summary::-webkit-details-marker {{ display: none; }}
#{uid} .jt-summary::before {{
  content: "▸";
  display: inline-block;
  width: 1em;
  color: #94a3b8;
}}
#{uid} details[open] > .jt-summary::before {{ content: "▾"; }}

#{uid} .jt-key   {{ color: #1f2937; }}
#{uid} .jt-punct {{ color: #94a3b8; }}
#{uid} .jt-str   {{ color: #059669; }}
#{uid} .jt-num   {{ color: #b45309; }}
#{uid} .jt-bool  {{ color: #2563eb; }}
#{uid} .jt-null  {{ color: #dc2626; }}
@media (prefers-color-scheme: dark) {{
  #{uid} .jt-key {{ color: #e5e7eb; }}
}}
</style>
"""
    return style + f'<div id="{uid}" class="jt">{body}</div>'
