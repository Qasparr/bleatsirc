# 93
# ---------------------------------------------------------------------
# operserv.py -- OperServ, the IRC-operator desk of the house.
#
# "Transparency toward power; privacy toward the person." -- THE
# LINE, the root privacy doctrine of the house. OperServ is the
# window in that wall: it faces the officers, and only the officers.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026 / Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: OperServ is an embedded pseudoclient answering PRIVMSG
# at its nick. It renders two reads over state the daemon already
# holds: LEDGER, the last ten entries of the house ledger (the
# record every oper act must enter BEFORE it executes), and STATS,
# the live counts of users, channels and *-lines. It keeps no state
# of its own and writes nothing; a read-only desk cannot become a
# second, unaccountable record.
# DOCTRINE: the gate is the point. Only an authenticated oper
# (conn.is_oper) may read the ledger at all -- a member asking gets
# a plain refusal NOTICE, because the ledger faces power, and power
# is inspected by its own, under the same record it inspects.
# ---------------------------------------------------------------------

import inspect

from ircd.protocol import format_msg


# MECHANISM: one send helper for every service in the house -- the
# real Conn's send and a test double's recording send are both
# honoured by awaiting the result only when it is awaitable.
async def _send(conn, line):
    """Deliver one raw line to a connection, awaiting if needed."""
    result = conn.send(line)
    if inspect.isawaitable(result):
        await result


def _msg_text(msg):
    """Rebuild the command text from a parsed PRIVMSG Message.

    MECHANISM: canonical shape is params == [target, text]; extra
    middle params from doubles are re-joined after the target so
    the one parse is never re-done from raw text.
    """
    params = list(getattr(msg, "params", []) or [])
    if len(params) > 2:
        return " ".join(params[1:])
    if len(params) == 2:
        return params[1]
    if len(params) == 1:
        return params[0]
    return getattr(msg, "trailing", "") or ""


def _ledger_entries(server):
    """Return the ledger's entries as a list, or None if unavailable.

    MECHANISM: the Ledger's ``entries`` may be a method (canonical)
    or a plain list attribute on a double; a bare list standing in
    for the whole ledger is honoured too. Every other shape reports
    itself unavailable rather than crashing the desk -- OperServ
    must never fall over because the record is shaped differently
    than expected.
    """
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return None
    if isinstance(ledger, (list, tuple)):
        return list(ledger)
    entries = getattr(ledger, "entries", None)
    if entries is None:
        return None
    try:
        if callable(entries):
            result = entries()
            return list(result) if result is not None else []
        return list(entries)
    except Exception:
        return None


def _entry_field(entry, *names):
    """Read the first present field among *names* from an entry.

    MECHANISM: ledger entries are objects in the canonical build
    and may be dicts on doubles; both are read through one door,
    and a missing field renders as an empty string, never an error.
    """
    for name in names:
        if isinstance(entry, dict):
            if name in entry and entry[name] is not None:
                return entry[name]
        else:
            value = getattr(entry, name, None)
            if value is not None:
                return value
    return ""


def _format_entry(entry):
    """Render one ledger entry as a single inspectable line.

    DOCTRINE: the line names timestamp, actor, act, target, detail
    and via -- who ordered, what was done, to whom, why, and through
    which hand -- because a record that cannot answer the inquiry
    scale is not a record, only a rumour.
    """
    ts = _entry_field(entry, "ts", "timestamp", "time", "when")
    actor = _entry_field(entry, "actor")
    act = _entry_field(entry, "act", "action", "command")
    target = _entry_field(entry, "target")
    detail = _entry_field(entry, "detail", "reason", "details")
    via = _entry_field(entry, "via")
    parts = []
    if ts != "":
        parts.append(str(ts))
    if actor:
        parts.append(f"actor={actor}")
    if act:
        parts.append(f"act={act}")
    if target:
        parts.append(f"target={target}")
    if detail:
        parts.append(f"detail={detail}")
    if via:
        parts.append(f"via={via}")
    return " ".join(parts) if parts else str(entry)


def _count(value):
    """Count a server collection defensively; 0 when uncountable.

    MECHANISM: dicts and lists answer len() directly; store objects
    (the *-line store) answer through their mapping surface --
    items()/keys() -- or an entries attribute when len() refuses.
    """
    if value is None:
        return 0
    try:
        return len(value)
    except Exception:
        pass
    for attr in ("items", "keys"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return len(list(method()))
            except Exception:
                continue
    entries = getattr(value, "entries", None)
    if entries is not None:
        try:
            return len(list(entries() if callable(entries) else entries))
        except Exception:
            return 0
    return 0


class OperServ:
    """Embedded operator-services pseudoclient (opers only).

    MECHANISM: HELP, LEDGER and STATS are the whole surface in this
    phase. Every branch first proves conn.is_oper; the refusal is a
    NOTICE with no data in it, so a refused read leaks nothing about
    what the ledger holds.
    """

    nick = "OperServ"

    def __init__(self):
        # MECHANISM: OperServ is stateless by design; the explicit
        # constructor documents that the absence is deliberate.
        pass

    async def _notice(self, conn, text):
        """Answer the directing oper with a NOTICE from OperServ."""
        line = format_msg("NOTICE", conn.nick, text, prefix=self.nick)
        await _send(conn, line)

    async def handle(self, server, conn, msg):
        """Dispatch one PRIVMSG addressed to OperServ.

        DOCTRINE: fail closed. The oper check stands before the
        command parse, so even HELP is an officers-only door in
        this phase -- there is no public surface here to probe.
        """
        if not getattr(conn, "is_oper", False):
            await self._notice(
                conn,
                "Access denied: OperServ answers authenticated IRC "
                "operators only.",
            )
            return
        text = _msg_text(msg).strip()
        tokens = text.split()
        if not tokens:
            await self._do_help(conn)
            return
        command = tokens[0].upper()
        if command == "HELP":
            await self._do_help(conn)
        elif command == "LEDGER":
            await self._do_ledger(server, conn)
        elif command == "STATS":
            await self._do_stats(server, conn)
        else:
            await self._notice(
                conn,
                f"Unknown OperServ command '{tokens[0]}'. "
                "Try: HELP, LEDGER, STATS.",
            )

    async def _do_help(self, conn):
        """NOTICE the command list, one line per command."""
        lines = [
            "OperServ -- the IRC-operator desk of the house (opers only).",
            "HELP - show this help.",
            "LEDGER - show the last 10 entries of the house ledger.",
            "STATS - show user, channel and kline counts.",
        ]
        for line in lines:
            await self._notice(conn, line)

    async def _do_ledger(self, server, conn):
        """LEDGER: render the last 10 ledger entries as NOTICEs.

        MECHANISM: entries arrive oldest-first from the store, so
        the tail slice [-10:] is the newest ten, rendered in order;
        an empty or missing ledger is stated plainly, never padded.
        """
        entries = _ledger_entries(server)
        if entries is None:
            await self._notice(conn, "Ledger unavailable on this server.")
            return
        if not entries:
            await self._notice(conn, "Ledger: no entries recorded.")
            return
        await self._notice(conn, "Ledger -- last 10 entries:")
        for entry in entries[-10:]:
            await self._notice(conn, _format_entry(entry))

    async def _do_stats(self, server, conn):
        """STATS: count users, channels and klines, as NOTICEs.

        MECHANISM: the counts are taken live from the server's own
        tables at the moment of asking -- a figure that cannot point
        to its numbers does not ship, so OperServ counts the tables
        themselves rather than trusting any cached tally.
        """
        users = _count(getattr(server, "connections", None))
        channels = _count(getattr(server, "channels", None))
        klines = _count(getattr(server, "lines", None))
        await self._notice(conn, "Network statistics:")
        await self._notice(
            conn, f"users={users} channels={channels} klines={klines}"
        )
        await self._notice(conn, f"Users: {users}")
        await self._notice(conn, f"Channels: {channels}")
        await self._notice(conn, f"K-lines (klines): {klines}")


# 93 -- Live, Love, and let Love, Live.
