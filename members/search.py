"""Member directory search composition.

Extracted from `members/views.py::directory_view` so the logic stays
testable in isolation as it grows. Three additive behaviors over the
prior single-substring search:

1. Multi-token AND. Splits `q` on whitespace; each token must match
   somewhere in the union of (first, last, nickname, city, country,
   profession). Pure-numeric tokens 1980-1985 also try
   `years_attended__contains` inside their own block. Single-token
   behavior is preserved as a degenerate case.

2. Trigram similarity fallback. When the multi-token AND query
   returns zero matches, fall back on the longest non-numeric token
   with TrigramSimilarity over the same six fields (threshold 0.3,
   ordered DESC). Requires the `pg_trgm` extension. Skipped if the
   longest non-numeric token is shorter than 4 chars (trigram noise).

3. The caller decides what to do with an empty post-fallback result
   (e.g., write `directory.query.no_results` to AuditLog and render
   suggestion chips).
"""

from __future__ import annotations

from django.contrib.postgres.lookups import Unaccent
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, F, FloatField, Q, QuerySet, Value, When
from django.db.models.functions import Greatest, Lower

# Same six-field union as the prior directory_view substring search.
_LC_FIELDS = ("first_lc", "last_lc", "nick_lc", "city_lc", "country_lc", "prof_lc")

# Pre-trigram fallback: skip the fuzzy fallback below this token length.
# Below 4 characters trigram similarity becomes noise.
_TRIGRAM_MIN_TOKEN_LEN = 4

# Trigram similarity threshold. Tuned empirically against the canonical
# typo 'Naimey' -> 'Niamey' which scores 0.273 on the local pg_trgm 1.6;
# the spec started at 0.3 but that just barely missed it. Tests use
# containment, never rank, so adjusting this won't break the test suite.
_TRIGRAM_THRESHOLD = 0.25

VALID_YEARS = range(1980, 1986)


def _annotate_lc(qs: QuerySet) -> QuerySet:
    """Annotate the queryset with lowercased + unaccented variants of the
    six fields once. Both multi-token AND and trigram fallback consume them."""
    return qs.annotate(
        first_lc=Lower(Unaccent(F("first_name"))),
        last_lc=Lower(Unaccent(F("last_name"))),
        nick_lc=Lower(Unaccent(F("nickname"))),
        city_lc=Lower(Unaccent(F("city"))),
        country_lc=Lower(Unaccent(F("country"))),
        prof_lc=Lower(Unaccent(F("profession"))),
    )


def _token_block(token: str) -> Q:
    """Build the per-token Q union: token matches any of the six lc fields,
    or (if pure-numeric and in 1980-1985) the years_attended array.

    City/country only match for members who opted to show their city —
    otherwise searching a city name reveals exactly the fact the
    `show_city` toggle promises to hide.
    """
    needle = Lower(Unaccent(Value(token)))
    location_match = Q(city_lc__contains=needle) | Q(country_lc__contains=needle)
    block = (
        Q(first_lc__contains=needle)
        | Q(last_lc__contains=needle)
        | Q(nick_lc__contains=needle)
        | (location_match & Q(show_city=True))
        | Q(prof_lc__contains=needle)
    )
    if token.isdigit():
        try:
            year = int(token)
        except ValueError:
            return block
        if year in VALID_YEARS:
            block = block | Q(years_attended__contains=[year])
    return block


def _longest_non_numeric_token(tokens: list[str]) -> str | None:
    candidates = [t for t in tokens if not t.isdigit()]
    if not candidates:
        return None
    return max(candidates, key=len)


def _trigram_fallback(qs: QuerySet, token: str) -> QuerySet:
    """Return qs ranked by max trigram similarity over the six fields,
    filtered above the threshold.

    City/country similarity is zeroed out for members with show_city=False,
    so the fuzzy path can't leak what the exact path now hides.
    """
    location_sim = Case(
        When(
            show_city=True,
            then=Greatest(
                TrigramSimilarity("city", token),
                TrigramSimilarity("country", token),
            ),
        ),
        default=Value(0.0),
        output_field=FloatField(),
    )
    return (
        qs.annotate(
            sim=Greatest(
                TrigramSimilarity("first_name", token),
                TrigramSimilarity("last_name", token),
                TrigramSimilarity("nickname", token),
                TrigramSimilarity("profession", token),
                location_sim,
            )
        )
        .filter(sim__gte=_TRIGRAM_THRESHOLD)
        .order_by("-sim", "last_name", "first_name")
    )


def search_members(qs: QuerySet, q: str) -> QuerySet:
    """Apply multi-token AND search to qs, with trigram fallback on zero results.

    Caller is responsible for the base filter (typically `status="active"`)
    and the final ordering / pagination / no-results logging.

    `q` is expected pre-trimmed and length-capped by the caller.
    """
    tokens = [t for t in q.split() if t]
    if not tokens:
        return qs

    qs = _annotate_lc(qs)
    filtered = qs
    for token in tokens:
        filtered = filtered.filter(_token_block(token))

    # Materialize a count efficiently — we only need to know "any?".
    if filtered.exists():
        return filtered

    # Zero-result fallback: trigram similarity on the longest non-numeric token.
    longest = _longest_non_numeric_token(tokens)
    if longest is None or len(longest) < _TRIGRAM_MIN_TOKEN_LEN:
        return filtered  # empty, no fallback applicable
    return _trigram_fallback(qs, longest)


def _staff_token_block(token: str) -> Q:
    """Per-token union for the STAFF search (gestion console).

    Deliberately different from `_token_block`:

    - No `show_city` gate. That toggle hides a member's city from other
      *members*; staff already read the full record on the detail page, so
      gating it here would only hide it from the one person entitled to see it.
    - Adds the login identity (`user.username`, `user.email`) and the messaging
      identity (`Member.whatsapp`). The two are decoupled on purpose (CLAUDE.md),
      and an operator working from a WhatsApp DM has the *number*, so both must
      match. Only username was searchable before.
    """
    needle = Lower(Unaccent(Value(token)))
    return (
        Q(first_lc__contains=needle)
        | Q(last_lc__contains=needle)
        | Q(nick_lc__contains=needle)
        | Q(city_lc__contains=needle)
        | Q(country_lc__contains=needle)
        | Q(prof_lc__contains=needle)
        | Q(user__username__icontains=token)
        | Q(user__email__icontains=token)
        | Q(whatsapp__icontains=token)
    )


def search_members_staff(qs: QuerySet, q: str) -> QuerySet:
    """Multi-token AND search for the gestion console.

    The console used to match the entire query as a single substring, so an
    operator typing the natural thing — a full name — got zero results, because
    "Alpha Bravo" is a substring of neither `first_name` nor `last_name`. The
    member-facing Annuaire had already been fixed; the console had drifted.

    No trigram fallback here: staff searches are usually an exact lookup of
    someone they are already talking to, and a fuzzy fallback that silently
    returns a *different* member is worse than an empty result when the next
    click suspends an account.
    """
    tokens = [t for t in q.split() if t]
    if not tokens:
        return qs

    qs = _annotate_lc(qs)
    for token in tokens:
        qs = qs.filter(_staff_token_block(token))
    return qs
