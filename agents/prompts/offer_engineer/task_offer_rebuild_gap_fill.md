# Seat: Offer Engineer
Source: Doc 00 / Doc 06 — mentioned but NOT given an explicit prompt template
in the 7 handbook docs provided.

## What the docs say about this seat (Doc 00's seat table)
"Called when the data says the offer is the constraint, not the creative.
Rebuilds price/bundle/bonus/guarantee. Refuses to: change live prices
without approval."

## What triggers a route to this seat
From Doc 06:
- Good CTR with bad CPA — elite click-through with sub-breakeven return is
  the signature of an offer problem, not a creative one.
- When the 2-ROAS cap sits under what the account is actually buying at,
  the offer or AOV is the constraint, not the bid.
- The Ecommerce Psychologist and Analyst both flag offer-level problems
  but explicitly refuse to fix them inside a creative or readout pass —
  they route to this seat instead.

## Action needed
No seat-prompt or task-prompt exists for this role in the source material.
Before implementing agents/seats/offer_engineer.py, either:
1. Ask the client for the missing prompt (it may exist outside the 7 docs
   shared so far), or
2. Write one following the same six-part skeleton every other seat prompt
   uses (Identity → Law → Evidence base → Method → Output spec → Refusals),
   using the constraints above as the Law section, and flag to the client
   that this seat's prompt was drafted rather than sourced verbatim.

Do not silently invent this seat's prompt and treat it as equivalent to the
client's own material — it should be visibly flagged as a gap-fill in any
review of the finished repo.
