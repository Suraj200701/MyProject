"""Pulling structured parts out of a formatted address string.

Local-business sources hand over one formatted address and rarely a separate
city — Google Maps exports and Mappls POIs both do this. But `city` is what
deduplication matches on and what the leads list filters by, so leaving it null
makes those leads invisible to both. This module derives it.

There is one implementation because there were nearly two: the Mappls adapter
grew its own splitter, and the CSV importer needed the same thing. Two
almost-identical heuristics drift, and then the same address yields a different
city depending on which door it came through.

Approach
--------
Work backwards from the end, which is where administrative components live:

    "MG Road, Indiranagar, Bengaluru, Karnataka 560001, India"
     └ street    └ locality   └ city    └ state+PIN    └ country

Trailing country is dropped, then a component carrying a postal code is treated
as the state (postal codes attach to the state component, or stand alone), which
leaves the city immediately before it. With too few components to be sure, the
interpretation widens rather than mislabelling a city as a state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Deliberately short: only the countries whose names actually appear as the final
# component in the address formats we ingest. A long list would start matching
# city names that happen to collide with country names.
_COUNTRY_TOKENS = {
    "india",
    "usa",
    "united states",
    "united states of america",
    "uk",
    "united kingdom",
    "canada",
    "australia",
    "singapore",
    "uae",
    "united arab emirates",
}

# 5-6 digit postal code (India PIN, US ZIP), optionally with a ZIP+4 suffix.
_POSTAL_RE = re.compile(r"\b(\d{5,6})(?:-\d{4})?\b")


@dataclass(frozen=True)
class AddressParts:
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


def parse_address(address: str | None) -> AddressParts:
    """Best-effort extraction of (city, state, postal_code, country).

    Never raises and never guesses wildly: a component is only labelled when its
    position makes the label likely. Unrecognised shapes yield empty fields, which
    downstream code treats as "unknown" rather than as data.
    """
    if not address:
        return AddressParts()

    parts = [p.strip() for p in str(address).split(",") if p.strip()]
    if not parts:
        return AddressParts()

    country: str | None = None
    if parts[-1].lower() in _COUNTRY_TOKENS:
        country = parts.pop()

    postal_code: str | None = None
    state: str | None = None

    if parts:
        match = _POSTAL_RE.search(parts[-1])
        if match:
            postal_code = match.group(1)
            # The component may be "Karnataka 560001" (state + code) or just
            # "560001". Strip the code; whatever remains is the state.
            remainder = _POSTAL_RE.sub("", parts[-1]).strip(" ,-")
            parts.pop()
            if remainder:
                state = remainder
            elif parts:
                # A bare postal code: the state is the component before it, but
                # only when something is still left to serve as the city.
                if len(parts) >= 2:
                    state = parts.pop()

    city: str | None = None
    if state is not None and parts:
        # The state has been removed, so the city is now the last component.
        city = parts[-1]
    elif len(parts) >= 3:
        # "<street>, ..., <city>, <state>" with no postal code to anchor on.
        city, state = parts[-2], parts[-1]
    elif len(parts) == 2:
        # Genuinely ambiguous: "Wagle Estate, Thane" is locality+city while
        # "Ahmedabad, Gujarat" is city+state, and telling them apart needs a
        # gazetteer we do not have. Taking the last component as the city
        # matches the sources we actually ingest — Google Maps and Mappls both
        # order components least-to-most administrative — and mislabelling a
        # locality as a city is far less damaging than filing every lead in a
        # city named after a state.
        city = parts[-1]
    elif len(parts) == 1:
        # A single remaining component is the most specific place name we have.
        # Treat it as a city when a state was already identified, otherwise as
        # the state — calling "Gujarat" a city would corrupt city filters.
        if state or postal_code:
            city = parts[0]
        else:
            state = parts[0]

    return AddressParts(city=city, state=state, postal_code=postal_code, country=country)
