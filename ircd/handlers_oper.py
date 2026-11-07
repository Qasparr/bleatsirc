# 93
# ---------------------------------------------------------------------
# handlers_oper.py -- OPER, KILL, KLINE, UNKLINE, GLINE, UNGLINE,
# WALLOPS: the operator's hand, and the record it must leave.
#
# "Absolute Authority is not attained by license or permit but thru
# TRVVTH alone." -- an oper's power here is attained through the
# O-line, and every use of it is written before it is wielded.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, VII day of November, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: handlers are `async def h(server, conn, msg)`, exposed
# as HANDLERS = [(command, fn), ...] for the coordinator's registry.
# The Message arrives already parsed ONCE (ircd.protocol); params'
# last element is the trailing parameter. Every send goes through
# _send(), which awaits the result when it is awaitable, because a
# connection's send() may be sync in one harness and async in
# another and the handler must be correct under both.
# DOCTRINE: the ledger is written BEFORE the act -- before the
# mode is granted, before the store changes, before the link is
# closed. Oper acts with no ledger entry do not happen. Staff
# (oper/staff) connections are never disconnected by a line or a
# KILL sweep: the staff-immunity seam, applied silently.
# ---------------------------------------------------------------------

import inspect

from ircd.ledger import Ledger
from ircd.lines import Lines
from ircd.protocol import format_msg

# MECHANISM: the fallback server name, used only when a server
# object carries no config name at all; a configured name always
# wins, so a test's server_name is the prefix on the wire verbatim.
_DEFAULT_SERVER_NAME = "bleats"


# -----------------------------------------------------------------
# Small roads every handler shares
# -----------------------------------------------------------------

def ensure_state(server):
    """Guarantee server.ledger and server.lines exist; return both.

    MECHANISM: integration order varies -- services, handlers, and
    the daemon core may attach in any sequence -- so the first hand
    that needs the ledger or the line store builds them, and every
    later hand uses what is already there untouched. DOCTRINE: an
    existing ledger is never replaced: replacing it would vanish
    the record, and dispositions are marked, never vanished. A spy
    or double installed by a test is likewise respected as-is.
    """
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        ledger = Ledger()
        try:
            server.ledger = ledger
        except Exception:
            pass
    lines = getattr(server, "lines", None)
    if lines is None:
        lines = Lines()
        try:
            server.lines = lines
        except Exception:
            pass
    return ledger, lines


def _server_name(server) -> str:
    """The server's wire name: config first, attributes after."""
    config = getattr(server, "config", None)
    if isinstance(config, dict):
        for key in ("server_name", "servername", "name"):
            value = config.get(key)
            if value:
                return str(value)
    for attr in ("server_name", "name"):
        value = getattr(server, attr, None)
        if value:
            return str(value)
    return _DEFAULT_SERVER_NAME


def _conn_prefix(conn) -> str:
    """conn.prefix when the connection offers one, else built."""
    prefix = getattr(conn, "prefix", None)
    if prefix:
        return str(prefix)
    nick = getattr(conn, "nick", None) or "*"
    user = getattr(conn, "user", None) or nick
    host = getattr(conn, "host", None) or "localhost"
    return f"{nick}!{user}@{host}"


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _send(server, conn, line):
    """Send one line to one connection, sync- or async-send safe.

    MECHANISM: prefer conn.send(line); fall back to
    server.send_to(nick, line) when the connection offers no send.
    A failing send is swallowed: a dead link must not unwind an
    oper act that the ledger has already recorded.
    """
    try:
        send = getattr(conn, "send", None)
        if callable(send):
            await _maybe_await(send(line))
            return True
        send_to = getattr(server, "send_to", None)
        if callable(send_to):
            nick = getattr(conn, "nick", None)
            await _maybe_await(send_to(nick, line))
            return True
    except Exception:
        return False
    return False


def _record(server, actor, act, target="", detail="", via=None):
    """Write one ledger entry, tolerating record() signature drift.

    MECHANISM: the house Ledger accepts (actor, act, target,
    detail, via). A double may accept fewer; try the full call,
    then narrower calls, so the act is recorded under any harness.
    DOCTRINE: this is called BEFORE the act it describes, always.
    """
    ledger, _ = ensure_state(server)
    record = getattr(ledger, "record", None)
    if not callable(record):
        return None
    attempts = []
    if via is not None:
        attempts.append(
            lambda: record(actor, act, target=target, detail=detail,
                           via=via))
    attempts.append(
        lambda: record(actor, act, target=target, detail=detail))
    attempts.append(lambda: record(actor, act, target, detail))
    for attempt in attempts:
        try:
            return attempt()
        except TypeError:
            continue
    return None


async def _numeric(server, conn, code, *rest):
    """Send one server-prefixed numeric to conn."""
    line = format_msg(code, getattr(conn, "nick", None) or "*",
                      *rest, prefix=_server_name(server))
    await _send(server, conn, line)


async def _need_params(server, conn, msg, count, command):
    """461 when the command arrived short; True when it may proceed."""
    if len(getattr(msg, "params", []) or []) >= count:
        return True
    await _numeric(server, conn, "461", command, "Not enough parameters")
    return False


async def _require_oper(server, conn):
    """481 unless conn is an oper; True when it may proceed.

    DOCTRINE: the denial is generic -- it names the missing
    privilege, never anything about anyone else's status.
    """
    if getattr(conn, "is_oper", False):
        return True
    await _numeric(
        server, conn, "481",
        "Permission Denied - You do not have the correct IRC "
        "operator privileges")
    return False


def _all_connections(server):
    """Every connection object the server knows, as a list."""
    conns = getattr(server, "connections", None)
    if isinstance(conns, dict):
        return list(conns.values())
    if isinstance(conns, (list, tuple, set)):
        return list(conns)
    return []


def _find_conn(server, nick):
    """Case-insensitive nick lookup in server.connections."""
    if not nick:
        return None
    conns = getattr(server, "connections", None)
    if isinstance(conns, dict):
        direct = conns.get(str(nick).lower())
        if direct is not None:
            return direct
        direct = conns.get(nick)
        if direct is not None:
            return direct
    for other in _all_connections(server):
        if str(getattr(other, "nick", "")).lower() == str(nick).lower():
            return other
    return None


def _is_staff(conn) -> bool:
    return bool(getattr(conn, "is_oper", False)
                or getattr(conn, "is_staff", False))


def _conn_candidates(conn):
    """The strings a line is matched against for this connection:
    full prefix, user@host, host, nick -- every face they present."""
    nick = getattr(conn, "nick", "") or ""
    user = getattr(conn, "user", "") or ""
    host = getattr(conn, "host", "") or ""
    candidates = []
    try:
        prefix = _conn_prefix(conn)
        if prefix:
            candidates.append(prefix)
    except Exception:
        pass
    if user and host:
        candidates.append(f"{user}@{host}")
    if host:
        candidates.append(host)
    if nick:
        candidates.append(nick)
    return candidates


async def _disconnect(server, target, reason):
    """Close one connection's link and forget it, defensively.

    MECHANISM, in order: the target is told (an ERROR closing-link
    line); any close/disconnect/kill/quit method it offers is
    called (awaited when awaitable); it is removed from
    server.connections under every key that names it; and it is
    removed from every channel's membership, whatever shape that
    membership takes (dict, set, or list, of conns or of nicks).
    No step may fail the act: each road is tried, none is trusted.
    """
    sname = _server_name(server)
    nick = getattr(target, "nick", "") or ""
    closing = format_msg(
        "ERROR", f"Closing Link: {nick} ({reason})", prefix=sname)
    await _send(server, target, closing)

    for name in ("close", "disconnect", "kill", "quit"):
        method = getattr(target, name, None)
        if not callable(method):
            continue
        try:
            await _maybe_await(method())
        except TypeError:
            try:
                await _maybe_await(method(reason))
            except Exception:
                pass
        except Exception:
            pass
        break

    conns = getattr(server, "connections", None)
    if isinstance(conns, dict):
        for key in list(conns.keys()):
            if conns.get(key) is target or \
                    str(key).lower() == str(nick).lower():
                conns.pop(key, None)

    channels = getattr(server, "channels", None)
    channel_objs = []
    if isinstance(channels, dict):
        channel_objs = list(channels.values())
    elif isinstance(channels, (list, tuple, set)):
        channel_objs = list(channels)
    for channel in channel_objs:
        for attr in ("members", "users", "nicks", "connections",
                     "member_nicks"):
            member = getattr(channel, attr, None)
            if isinstance(member, dict):
                for key in list(member.keys()):
                    value = member.get(key)
                    if value is target or \
                            str(key).lower() == str(nick).lower():
                        member.pop(key, None)
            elif isinstance(member, set):
                for item in list(member):
                    if item is target or \
                            str(item).lower() == str(nick).lower():
                        member.discard(item)
            elif isinstance(member, list):
                member[:] = [
                    item for item in member
                    if item is not target
                    and str(item).lower() != str(nick).lower()
                ]

    own = getattr(target, "channels", None)
    try:
        if isinstance(own, (set, list)):
            own.clear()
        elif isinstance(own, dict):
            own.clear()
    except Exception:
        pass


async def _wallops_to_opers(server, text, prefix=None):
    """Deliver one WALLOPS line to every oper connection."""
    line = format_msg("WALLOPS", text,
                      prefix=prefix or _server_name(server))
    for other in _all_connections(server):
        if getattr(other, "is_oper", False):
            await _send(server, other, line)


async def _notice(server, conn, text):
    """A server NOTICE to one connection (oper confirmations)."""
    line = format_msg("NOTICE", getattr(conn, "nick", None) or "*",
                      text, prefix=_server_name(server))
    await _send(server, conn, line)


# -----------------------------------------------------------------
# OPER -- the O-line gate
# -----------------------------------------------------------------

async def h_oper(server, conn, msg):
    """OPER <name> <password> -- become an IRC operator.

    MECHANISM: the O-lines live in server.config['olines'] as
    {name: password}; the name is looked up exactly as configured
    (a case-insensitive retry follows, because nicks are not
    case-bound on this wire), the password compared exactly.
    Success grants is_oper and the 'o' user mode, answered 381.
    Failure is answered 491. DOCTRINE: success and failure alike
    are ledgered BEFORE the reply -- the failed attempt is part of
    the record, for the case file, not an embarrassment erased.
    """
    ensure_state(server)
    if not await _need_params(server, conn, msg, 2, "OPER"):
        return
    name, password = msg.params[0], msg.params[1]

    config = getattr(server, "config", None)
    olines = {}
    if isinstance(config, dict):
        olines = config.get("olines") or {}
    if not isinstance(olines, dict):
        olines = {}

    expected = olines.get(name)
    if expected is None:
        for key, value in olines.items():
            if str(key).lower() == str(name).lower():
                expected = value
                break

    actor = getattr(conn, "nick", None) or name
    if expected is not None and str(expected) == str(password):
        _record(server, actor, "OPER", target=name,
                detail="success", via="handlers_oper")
        conn.is_oper = True
        modes = getattr(conn, "modes", None)
        try:
            if isinstance(modes, set):
                modes.add("o")
            elif isinstance(modes, list) and "o" not in modes:
                modes.append("o")
            elif modes is None:
                conn.modes = {"o"}
        except Exception:
            pass
        await _numeric(server, conn, "381",
                       "You are now an IRC operator")
    else:
        _record(server, actor, "OPER", target=name,
                detail="failed attempt", via="handlers_oper")
        await _numeric(server, conn, "491", "No O-lines for your host")


# -----------------------------------------------------------------
# KILL -- sever one link, by name
# -----------------------------------------------------------------

async def h_kill(server, conn, msg):
    """KILL <nick> :<reason> -- disconnect one user, oper only.

    MECHANISM: the target is found case-insensitively; an absent
    target is answered 401 and nothing else happens. DOCTRINE: the
    ledger entry is written BEFORE the link is closed, and opers
    are told by WALLOPS what was done and why -- power exercised
    in the open, or not at all.
    """
    ensure_state(server)
    if not await _require_oper(server, conn):
        return
    if not await _need_params(server, conn, msg, 1, "KILL"):
        return
    target_nick = msg.params[0]
    reason = msg.trailing if len(msg.params) >= 2 else ""
    if not reason:
        reason = "Killed"

    target = _find_conn(server, target_nick)
    if target is None:
        await _numeric(server, conn, "401", target_nick,
                       "No such nick/channel")
        return

    actor = getattr(conn, "nick", "") or ""
    _record(server, actor, "KILL", target=target_nick,
            detail=reason, via="handlers_oper")
    await _disconnect(server, target, reason)
    await _wallops_to_opers(
        server, f"KILL: {actor} killed {target_nick} ({reason})")


# -----------------------------------------------------------------
# KLINE / UNKLINE / GLINE / UNGLINE -- the line store, wielded
# -----------------------------------------------------------------

def _parse_line_command(msg):
    """Split a KLINE/GLINE command into (duration, mask, reason).

    MECHANISM: both spoken forms are honoured --
    'KLINE <mask> :<reason>' and 'KLINE <duration> <mask> :<reason>'.
    A first parameter that is all digits AND is followed by another
    parameter is the duration; the parameter after it (or the first)
    is the mask; a parameter beyond the mask is the reason.
    """
    params = list(getattr(msg, "params", []) or [])
    duration = None
    idx = 0
    if len(params) >= 2 and params[0].isdigit():
        try:
            duration = int(params[0])
            idx = 1
        except ValueError:
            duration = None
    mask = params[idx] if len(params) > idx else ""
    reason = params[idx + 1] if len(params) > idx + 1 else ""
    return duration, mask, reason or "No reason given"


def _add_line(server, mask, reason, setter, duration, network):
    """Add to the line store, tolerating add() signature drift."""
    _, lines = ensure_state(server)
    add = getattr(lines, "add", None)
    if not callable(add):
        return None
    attempts = [
        lambda: add(mask, reason, setter, duration=duration,
                    network=network),
        lambda: add(mask, reason, setter, duration=duration),
        lambda: add(mask, reason, setter),
        lambda: add(mask, reason=reason, setter=setter),
    ]
    for attempt in attempts:
        try:
            return attempt()
        except TypeError:
            continue
    return None


def _remove_line(server, mask):
    """Remove from the line store; truthy when a line was present."""
    _, lines = ensure_state(server)
    remove = getattr(lines, "remove", None)
    if not callable(remove):
        return False
    try:
        result = remove(mask)
    except Exception:
        return False
    # MECHANISM: house Lines.remove returns a bool; a store that
    # returns the removed entry (or None) is read the same way.
    return bool(result)


def _line_matches(server, target) -> bool:
    """True when the store refuses any face this connection shows."""
    _, lines = ensure_state(server)
    match = getattr(lines, "match", None)
    if not callable(match):
        return False
    for candidate in _conn_candidates(target):
        try:
            if match(candidate):
                return True
        except Exception:
            continue
    return False


async def _do_line(server, conn, msg, command, network):
    """Shared KLINE/GLINE body; ``network`` marks a G-line.

    DOCTRINE: ledger BEFORE the store changes; the store BEFORE
    the sweep; the sweep never touches staff (immunity seam,
    silent). The oper is confirmed by NOTICE either way.
    """
    ensure_state(server)
    if not await _require_oper(server, conn):
        return
    if not await _need_params(server, conn, msg, 1, command):
        return
    duration, mask, reason = _parse_line_command(msg)
    if not mask:
        await _numeric(server, conn, "461", command,
                       "Not enough parameters")
        return

    actor = getattr(conn, "nick", "") or ""
    detail = reason if duration is None else f"[{duration}s] {reason}"
    _record(server, actor, command, target=mask, detail=detail,
            via="handlers_oper")
    _add_line(server, mask, reason, actor, duration, network)

    label = "G-line" if network else "K-line"
    for other in list(_all_connections(server)):
        if other is conn or _is_staff(other):
            continue
        if _line_matches(server, other):
            await _disconnect(
                server, other, f"{label}: {reason}")
    await _notice(server, conn, f"{command} added: {mask} ({reason})")


async def _do_unline(server, conn, msg, command):
    """Shared UNKLINE/UNGLINE body.

    DOCTRINE: the removal is ledgered BEFORE the store changes --
    lifting a line is an oper act exactly as laying one is.
    """
    ensure_state(server)
    if not await _require_oper(server, conn):
        return
    if not await _need_params(server, conn, msg, 1, command):
        return
    mask = msg.params[0]
    actor = getattr(conn, "nick", "") or ""
    _record(server, actor, command, target=mask, detail="removed",
            via="handlers_oper")
    if _remove_line(server, mask):
        await _notice(server, conn, f"{command}: removed {mask}")
    else:
        await _notice(server, conn, f"{command}: no such line {mask}")


async def h_kline(server, conn, msg):
    """KLINE [duration] <mask> :<reason> -- refuse a hostmask here."""
    await _do_line(server, conn, msg, "KLINE", network=False)


async def h_unkline(server, conn, msg):
    """UNKLINE <mask> -- lift a K-line."""
    await _do_unline(server, conn, msg, "UNKLINE")


async def h_gline(server, conn, msg):
    """GLINE [duration] <mask> :<reason> -- refuse a hostmask,
    network-flagged in the same store (the POC's one daemon speaks
    for its network; the flag is what a future link would carry)."""
    await _do_line(server, conn, msg, "GLINE", network=True)


async def h_ungline(server, conn, msg):
    """UNGLINE <mask> -- lift a G-line."""
    await _do_unline(server, conn, msg, "UNGLINE")


# -----------------------------------------------------------------
# WALLOPS -- the opers' wall
# -----------------------------------------------------------------

async def h_wallops(server, conn, msg):
    """WALLOPS :<text> -- write on the wall every oper reads.

    MECHANISM: oper only; the text is the trailing parameter (or
    the joined parameters when no trailing was marked); delivery
    goes to every is_oper connection, the author included, under
    the author's own prefix -- a wall post is signed.
    """
    ensure_state(server)
    if not await _require_oper(server, conn):
        return
    text = msg.trailing if getattr(msg, "params", None) else ""
    if not text:
        text = " ".join(msg.params or [])
    if not text:
        await _numeric(server, conn, "461", "WALLOPS",
                       "Not enough parameters")
        return
    await _wallops_to_opers(server, text, prefix=_conn_prefix(conn))


# -----------------------------------------------------------------
# The registry surface
# -----------------------------------------------------------------

# MECHANISM: registration is data. The coordinator folds these
# pairs into the Registry; no if-chain anywhere names a command.
HANDLERS = [
    ("OPER", h_oper),
    ("KILL", h_kill),
    ("KLINE", h_kline),
    ("UNKLINE", h_unkline),
    ("GLINE", h_gline),
    ("UNGLINE", h_ungline),
    ("WALLOPS", h_wallops),
]


# 93 -- Live, Love, and let Love, Live.
