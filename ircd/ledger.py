# 93
# ---------------------------------------------------------------------
# ledger.py -- the append-only record of oper acts.
#
# "Say It. Spray It. Own It." -- the Bleats motto: an act that is
# owned is an act that is written down, before it happens.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, VII day of November, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: a plain in-memory list of dicts. record() stamps each
# entry with time.time() at the moment of the call and appends it;
# nothing is ever edited or deleted through this class, so the order
# of entries IS the order of acts. entries() hands back copies, so
# a reader can never rewrite history by mutating what it was given.
# DOCTRINE: companion doctrine to the daemon -- the ledger is
# written BEFORE an oper act executes. An oper act with no ledger
# entry does not happen. The ledger is the network's memory of its
# own power, kept in the open, marked never vanished.
# ---------------------------------------------------------------------

import time


class Ledger:
    """Append-only in-memory ledger of oper (and service) acts.

    MECHANISM: entries are dicts of the shape
    {ts, actor, act, target, detail, via}. ``via`` records the road
    an act arrived by (a service nick, a module name) when the
    caller supplies it; it is always present as a key, None when
    the caller named no road, so consumers never guess at keys.
    """

    def __init__(self) -> None:
        # MECHANISM: one list, owned by this instance alone --
        # per-server state never bleeds across servers because each
        # server builds its own Ledger.
        self._entries: list[dict] = []

    def record(self, actor, act, target="", detail="", via=None):
        """Append one entry and return it.

        MECHANISM: the timestamp is taken here, at record time --
        callers record BEFORE acting, so ``ts`` is the moment the
        act was decided, not the moment it finished.
        DOCTRINE: no validation refuses an entry. A ledger that can
        decline to remember is a ledger that can be gamed; odd acts
        are recorded exactly as oddly as they arrived.
        """
        entry = {
            "ts": time.time(),
            "actor": actor,
            "act": act,
            "target": target,
            "detail": detail,
            "via": via,
        }
        self._entries.append(entry)
        return entry

    def entries(self):
        """Return a copy of all entries, oldest first.

        MECHANISM: the list and each dict are copied, so callers
        may sort, filter, or annotate their copy without touching
        the record itself.
        """
        return [dict(e) for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        # MECHANISM: iterate over a copy, for the same reason
        # entries() copies -- the record is read-only to the world.
        return iter(self.entries())

    def __repr__(self) -> str:  # pragma: no cover - diagnostic aid
        return f"<Ledger {len(self._entries)} entries>"


# 93 -- Live, Love, and let Love, Live.
