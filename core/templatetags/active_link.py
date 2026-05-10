"""Template tags for marking the current page in navigation surfaces.

Used by:
- `templates/base.html` (desktop navbar + mobile dropdown)
- `gestion/templates/gestion/base.html` (gestion subnav)

Two tags:
- `{% active_class prefix [exact=True] [active="..."] %}` —
  returns the active CSS class string when `request.path` matches
  `prefix`. Prefix-match by default; pass `exact=True` for exact match
  (used on root-of-section links like Tableau de bord).
- `{% active_aria prefix [exact=True] %}` —
  returns ` aria-current="page"` as a SafeString when active, empty
  string otherwise. Mirrors `active_class`'s matching semantics.
"""

from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

DEFAULT_ACTIVE_CLASS = "bg-base-200 text-tertiary font-medium"


def _is_active(context, prefix: str, *, exact: bool) -> bool:
    request = context.get("request")
    if request is None:
        return False
    path = request.path
    if exact:
        return path == prefix
    return path.startswith(prefix)


@register.simple_tag(takes_context=True)
def active_class(
    context,
    prefix: str,
    exact: bool = False,
    active: str = DEFAULT_ACTIVE_CLASS,
    inactive: str = "",
) -> str:
    """Return `active` when request.path matches `prefix`, else `inactive`.

    By default uses prefix matching (so `/annuaire/` matches `/annuaire/123/`).
    Pass `exact=True` to require an exact path match (used for the gestion
    root link, which would otherwise stay active on every /gestion/* page).
    """
    return active if _is_active(context, prefix, exact=exact) else inactive


@register.simple_tag(takes_context=True)
def active_aria(context, prefix: str, exact: bool = False):
    """Return ` aria-current="page"` (as SafeString) when active, else "".

    Marked safe so the attribute renders unescaped. Includes a leading
    space so the call site can place it directly after the previous
    attribute without manual spacing.
    """
    if _is_active(context, prefix, exact=exact):
        return mark_safe(' aria-current="page"')  # noqa: S308 - static literal
    return ""
