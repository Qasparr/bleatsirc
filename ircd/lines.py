# 93
# ---------------------------------------------------------------------
# lines.py -- the K-line / G-line store: masks the network refuses.
#
# "Public is public. Private is private. Period." -- the Line: a
# ban-line is a border drawn in the open, with its reason attached.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, VII day of November, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: a dict keyed by the lowercased mask. Each value is a
# LineEntry carrying (reason, expires_ts or None, setter) plus the
# network flag that separates a G-line (network-wide in intent)
# from a K-line (this server). Matching is IRC hostmask matching:
# '*' matches any run, '?' any single character, case-insensitively,
# and pragmatically -- a mask written as '*@host' is tested against
# the user@host and host faces of a candidate, not only against a
# full nick!user@host prefix, because callers hold candidates in
# all three shapes.
# DOCTRINE: every line carries its reason and its setter. A refusal
# without a stated reason and a named hand is not a line, it is a
# gate -- and gates on this network are logged, never silent.
# ---------------------------------------------------------------------

import re
import time
from dataclasses import dataclass


def _wildcard_match(pattern: str, value: str) -> bool:
    """Case-insensitive IRC wildcard match ('*' any run, '?' one char).

    MECHANISM: translate the pattern to an anchored regex by hand
    rather than borrowing fnmatch, whose character-class syntax
    ('[...]') is not part of the IRC mask grammar and would let a
    mask mean something its setter never wrote.
    """
    pat = pattern.lower()
    val = value.lower()
    out = []
    for ch in pat:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.fullmatch("".join(out), val) is not None


def _split_mask(text: str):
    """Split a mask or candidate into (nick, user, host) faces.

    MECHANISM: 'nick!user@host' yields all three; 'user@host' leaves
    nick None; a bare 'host' leaves nick and user None. Missing
    faces are None, never guessed.
    """
    nick = None
    user = None
    host = text
    rest = text
    if "!" in rest:
        nick, _, rest = rest.partition("!")
    if "@" in rest:
        user, _, host = rest.rpartition("@")
    else:
        host = rest
    return nick, user, host


@dataclass
class LineEntry:
    """One stored line: the spec's (reason, expires, setter) tuple,
    kept as a record so the network flag and creation time ride with
    it instead of in a parallel table that could drift apart."""

    mask: str
    reason: str = ""
    expires: float | None = None
    setter: str = ""
    network: bool = False
    created: float = 0.0

    @property
    def expires_ts(self):
        """Alias for ``expires`` -- the name the spec's tuple uses."""
        return self.expires

    def as_tuple(self):
        """The (reason, expires_ts, setter) triple of the brief."""
        return (self.reason, self.expires, self.setter)

    def expired(self, now=None) -> bool:
        if self.expires is None:
            return False
        return (time.time() if now is None else now) >= self.expires


class Lines:
    """The K-line/G-line store for one server.

    MECHANISM: keys are lowercased masks (CASEMAPPING spirit: a
    mask set in one case must bite in every case). Expiry is lazy:
    match() and the readers purge first, so an expired line never
    matches and never has to be reaped by a background clock --
    fail-closed on time, with no moving parts.
    """

    def __init__(self) -> None:
        self._store: dict[str, LineEntry] = {}

    # -- writing ---------------------------------------------------

    def add(self, mask, reason="", setter="", duration=None,
            expires=None, expires_ts=None, network=False):
        """Add (or replace) a line for ``mask`` and return its entry.

        MECHANISM: ``duration`` is seconds-from-now; ``expires`` /
        ``expires_ts`` are absolute timestamps; duration wins when
        both are given because it is the form a command line most
        recently spoke. Neither means permanent (expires None).
        """
        now = time.time()
        exp = expires_ts if expires_ts is not None else expires
        if duration is not None:
            try:
                exp = now + float(duration)
            except (TypeError, ValueError):
                # DOCTRINE: a malformed duration must not silently
                # become permanent OR silently vanish -- treat it
                # as no expiry only when it cannot be read at all,
                # and let the caller's ledger entry carry the act.
                exp = None
        entry = LineEntry(
            mask=str(mask),
            reason=str(reason or ""),
            expires=exp,
            setter=str(setter or ""),
            network=bool(network),
            created=now,
        )
        self._store[str(mask).lower()] = entry
        return entry

    def remove(self, mask):
        """Remove the line for ``mask``; True when one was present."""
        return self._store.pop(str(mask).lower(), None) is not None

    # -- reading ---------------------------------------------------

    def get(self, mask, now=None):
        """The live entry for exactly ``mask``, or None."""
        self.purge_expired(now)
        return self._store.get(str(mask).lower())

    def purge_expired(self, now=None):
        """Drop every expired entry; returns how many were dropped."""
        now = time.time() if now is None else now
        dead = [k for k, e in self._store.items() if e.expired(now)]
        for k in dead:
            del self._store[k]
        return len(dead)

    def items(self, now=None):
        """List of (lowercased-mask, LineEntry) pairs, live only."""
        self.purge_expired(now)
        return list(self._store.items())

    def snapshot(self, now=None):
        """Dict copy of the live store, for inspection and tests."""
        self.purge_expired(now)
        return dict(self._store)

    def __len__(self) -> int:
        self.purge_expired()
        return len(self._store)

    def __contains__(self, mask) -> bool:
        return self.get(mask) is not None

    # -- matching --------------------------------------------------

    def _entry_matches(self, entry: LineEntry, candidate: str) -> bool:
        """Does one stored mask refuse this candidate string?

        MECHANISM: first the literal road -- wildcard-match the
        mask against the candidate exactly as written, and against
        its user@host face when it arrived as a full prefix. Then
        the structured road: compare face to face (nick/user/host),
        where a face the mask does not name imposes no condition,
        and a face the candidate does not carry can only be refused
        by a pure-wildcard mask face. This is what lets
        '*@bad.example' refuse 'user@bad.example', 'bad.example'
        candidates carrying that host, and full prefixes alike,
        while 'op@bad.example' still refuses only that user.
        """
        mask = entry.mask
        cand = str(candidate)
        if _wildcard_match(mask, cand):
            return True
        if "!" in cand and _wildcard_match(mask, cand.split("!", 1)[1]):
            return True

        m_nick, m_user, m_host = _split_mask(mask)
        c_nick, c_user, c_host = _split_mask(cand)

        # MECHANISM: a mask with no '@' and no '!' is a host mask;
        # its whole body is the host pattern.
        if "@" not in mask and "!" not in mask:
            return _wildcard_match(mask, c_host or cand)

        def face_ok(pattern, value):
            if pattern is None:
                return True
            if value is None:
                # DOCTRINE: an unknown face is refused only by a
                # mask face made entirely of wildcards -- '*'
                # names everyone, a literal name names someone the
                # candidate has not proven to be.
                return set(pattern) <= {"*", "?"}
            return _wildcard_match(pattern, value)

        # MECHANISM: when the mask names a host (the normal case)
        # all named faces must agree; when it names none, fall back
        # to the literal roads already tried above.
        if m_host is not None and "@" in mask:
            return (
                face_ok(m_nick, c_nick)
                and face_ok(m_user, c_user)
                and face_ok(m_host, c_host)
            )
        if "!" in mask:
            return face_ok(m_nick, c_nick) and face_ok(m_user, c_user)
        return False

    def find(self, candidate, now=None):
        """The first live entry refusing ``candidate``, or None."""
        self.purge_expired(now)
        for entry in self._store.values():
            if self._entry_matches(entry, candidate):
                return entry
        return None

    def match(self, candidate, now=None) -> bool:
        """True when any live line refuses ``candidate``.

        MECHANISM: ``candidate`` may be a single string or an
        iterable of strings (prefix, user@host, host) -- a user is
        refused when ANY of their faces is refused.
        """
        if candidate is None:
            return False
        if isinstance(candidate, (list, tuple, set)):
            return any(self.match(c, now=now) for c in candidate)
        return self.find(candidate, now=now) is not None


# 93 -- Live, Love, and let Love, Live.
