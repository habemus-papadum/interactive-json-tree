import html
import uuid
from collections.abc import Mapping, Sequence
from itertools import islice
from typing import Optional


class JSON:
    """
    A simple tree view for nested dictionaries and lists.

    This class provides an interactive HTML representation of JSON-like data structures
    (dictionaries and lists) that can be expanded and collapsed in environments
    that support HTML display, such as Jupyter notebooks.

    Parameters
    ----------
    data : Mapping or Sequence
        The JSON-like data to visualize. Can be a dictionary, list, or any
        object that implements the Mapping or Sequence protocol.
    expand_depth : int, default=1
        The initial depth to which the tree should be expanded.
        Level 1 means only the root level is expanded.
    max_children : int, default=100
        The maximum number of children to display for a node before truncating.
    max_string_length : int, default=2000
        The maximum length for string values before truncating.

    Examples
    --------
    >>> from interactive_json_tree import JSON
    >>> data = {"name": "example", "values": [1, 2, 3], "nested": {"a": 1, "b": 2}}
    >>> JSON(data)
    """

    def __init__(
        self,
        data: Mapping | Sequence,
        *,
        expand_depth: int = 1,
        max_children: int = 100,
        max_string_length: int = 2000,
    ):
        self.data = data
        self.expand_depth = expand_depth
        self.max_children = max_children
        self.max_string_length = max_string_length
        self.rendered = json_to_html_tree(
            self.data,
            expand_depth=self.expand_depth,
            max_children=self.max_children,
            max_string_length=self.max_string_length,
        )

    def _repr_html_(self):
        return self.rendered

#############################################################################
# Internals
#############################################################################

_INDENT_REM = 0.5  # indent step per level (in rem)

def _to_html(
    obj,
    *,
    expand_depth=1,
    level=0,
    seen=None,
    key=None,
    key_is_index=False,
    max_children=100,
    max_string_length=2000,
):
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
            if (
                max_string_length is not None
                and max_string_length >= 0
                and len(v) > max_string_length
            ):
                truncated = v[:max_string_length]
                return f'<span class="jt-str jt-str-trunc">"{esc(truncated)}..."</span>'
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
        visible = size
        if max_children is not None and max_children >= 0:
            visible = min(size, max_children)
        open_attr = " open" if expand_depth > 0 else ""
        # If this dict is a child, show the key inline in its summary
        count_display = f"{visible}/{size}" if visible != size else str(size)
        summary_label = (
            f'{key_prefix_html(key, key_is_index)}{{}} Object '
            f'<span class="jt-punct">({count_display})</span>'
        )
        # Build children
        rows = []
        items_iter = obj.items()
        if max_children is not None and max_children >= 0:
            items_iter = islice(items_iter, max_children)
        for k, v in items_iter:
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
                        max_children=max_children,
                        max_string_length=max_string_length,
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
                        max_children=max_children,
                        max_string_length=max_string_length,
                    )
                )
            else:
                # primitive child -> single line
                rows.append(
                    f'<div class="jt-leaf" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                    f"{key_prefix_html(k, False)}{fmt_primitive(v)}</div>"
                )
        if size > visible:
            remaining = size - visible
            rows.append(
                f'<div class="jt-more" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                f"<em>... {remaining} more item{'s' if remaining != 1 else ''}</em></div>"
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
        visible = size
        if max_children is not None and max_children >= 0:
            visible = min(size, max_children)
        open_attr = " open" if expand_depth > 0 else ""
        count_display = f"{visible}/{size}" if visible != size else str(size)
        summary_label = (
            f'{key_prefix_html(key, key_is_index)}[] Array '
            f'<span class="jt-punct">({count_display})</span>'
        )
        rows = []
        iterable = obj
        if max_children is not None and max_children >= 0:
            iterable = islice(enumerate(obj), max_children)
        else:
            iterable = enumerate(obj)
        for i, v in iterable:
            if isinstance(v, Mapping):
                rows.append(
                    _to_html(
                        v,
                        expand_depth=max(expand_depth - 1, 0),
                        level=level + 1,
                        seen=seen,
                        key=i,
                        key_is_index=True,
                        max_children=max_children,
                        max_string_length=max_string_length,
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
                        max_children=max_children,
                        max_string_length=max_string_length,
                    )
                )
            else:
                rows.append(
                    f'<div class="jt-leaf" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                    f"{key_prefix_html(i, True)}{fmt_primitive(v)}</div>"
                )
        if size > visible:
            remaining = size - visible
            rows.append(
                f'<div class="jt-more" style="margin-left:{(level + 1) * _INDENT_REM}rem">'
                f"<em>... {remaining} more item{'s' if remaining != 1 else ''}</em></div>"
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


def json_to_html_tree(
    obj,
    *,
    key: Optional[str] = None,
    expand_depth: int = 1,
    max_children: int = 100,
    max_string_length: int = 2000,
):
    """
    Convert a Python object to an interactive HTML tree representation.
    This function converts a Python object (typically a JSON-like structure with dictionaries,
    lists, and primitive values) into an HTML tree that can be expanded and collapsed
    interactively in a web browser.
    Parameters
    ----------
    obj : Any
        The Python object to convert to an HTML tree.
    key : Optional[str], default=None
        The key name to display for the root object.
    expand_depth : int, default=1
        The initial depth to which the tree should be expanded.
    max_children : int, default=100
        The maximum number of children to display for arrays and objects.
        If exceeded, remaining items will be summarized.
    max_string_length : int, default=2000
        The maximum length of strings to display before truncating.
    Returns
    -------
    str
        HTML string containing the interactive tree representation with embedded CSS styling.
        The tree includes collapsible sections using HTML <details> elements.
    Notes
    -----
    The generated HTML uses a unique ID for CSS scoping and includes styling for
    different JSON data types with appropriate colors for both light and dark modes.

    """
    uid = f"jt-{uuid.uuid4().hex[:8]}"
    body = _to_html(
        obj,
        expand_depth=expand_depth,
        level=0,
        seen=set(),
        key=key,
        key_is_index=False,
        max_children=max_children,
        max_string_length=max_string_length,
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
#{uid} .jt-str-trunc {{ color: #dc2626; }}
#{uid} .jt-num   {{ color: #b45309; }}
#{uid} .jt-bool  {{ color: #2563eb; }}
#{uid} .jt-null  {{ color: #dc2626; }}
#{uid} .jt-more  {{ color: #94a3b8; }}
@media (prefers-color-scheme: dark) {{
  #{uid} .jt-key {{ color: #e5e7eb; }}
  #{uid} .jt-str-trunc {{ color: #f87171; }}
  #{uid} .jt-more {{ color: #64748b; }}
}}
</style>
"""
    return style + f'<div id="{uid}" class="jt">{body}</div>'
