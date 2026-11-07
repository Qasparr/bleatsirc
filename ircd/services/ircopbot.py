# 93
# ---------------------------------------------------------------------
# ircopbot.py -- the IRCopBot, proxy hand of the incognito opers.
#
# "An oper directs it privately, and the bot executes the duty --
#  so the action appears on the wire as the bot's, and the oper is
#  never exposed." -- CUSTOM-IRCD-SPEC, the IRCopBot.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026 / Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: the IRCopBot is an embedded pseudoclient with no
# socket, no timer and NO INITIATIVE. It moves only when an
# authenticated oper (conn.is_oper) directs it by PRIVMSG, and only
# as far as that direction reaches: KLINE lays a server ban and
# drops matching connections, DROP removes one named user, MODE
# intervenes in one channel. Every answer about an execution goes
# back to the directing oper as a PRIVMSG from "IRCopBot".
# DOCTRINE: attribution is two-layered by design. The wire names
# the bot; the house ledger names the directing oper, ALWAYS, and
# the ledger entry is written BEFORE the act executes -- an oper
# act with no ledger entry does not happen. That ordering is the
# companion doctrine and it is structural here, not a courtesy:
# each command's code path records first and acts second, in that
# order, in the same function, so no refactor can quietly invert
# it. Incognito governs the wire, never the record.
# ---------------------------------------------------------------------

import fnmatch
import inspect

from ircd.protocol import format_msg


# -----------------------------------------------------------------
# Fallback stores. MECHANISM: the canonical Ledger (ircd.ledger)
# and Lines (ircd.lines) are imported lazily, at need, so this
# module loads even while its siblings are still landing. If a
# server arrives with neither attached and the import fails, these
# minimal in-memory stores stand in -- because the doctrine is
# "ledger before act", a missing ledger must become a ledger, not
# an excuse to act unrecorded.
# -----------------------------------------------------------------
class _FallbackLedger:
    """Minimal ledger: record() appends, entries() returns a copy."""

    def __init__(self):
        self._entries = []

    def record(self, actor, act, target, detail, via=None):
        entry = {
            "actor": actor,
            "act": act,
            "target": target,
            "detail": detail,
            "via": via,
        }
        self._entries.append(entry)
        return entry

    def entries(self):
        return list(self._entries)


class _FallbackLines:
    """Minimal *-line store: mask -> (reason, setter), glob match."""

    def __init__(self):
        self._lines = {}

    def add(self, mask, reason, setter=None, duration=None, **_kw):
        self._lines[str(mask).lower()] = (reason, setter)
        return mask

    def match(self, candidate):
        candidate_lower = str(candidate).lower()
        for mask in self._lines:
            if fnmatch.fnmatchcase(candidate_lower, mask):
                return True
        return False

    def __len__(self):
        return len(self._lines)


def _get_ledger(server):
    """Return server.ledger, attaching a real/fallback one if absent."""
    ledger = getattr(server, "ledger", None)
    if ledger is not None and hasattr(ledger, "record"):
        return ledger
    candidate = None
    try:
        from ircd.ledger import Ledger

        try:
            candidate = Ledger()
        except TypeError:
            candidate = Ledger(server)
    except Exception:
        candidate = _FallbackLedger()
    try:
        server.ledger = candidate
    except Exception:
        pass
    return candidate


def _get_lines(server):
    """Return server.lines, attaching a real/fallback store if absent."""
    lines = getattr(server, "lines", None)
    if lines is not None and (hasattr(lines, "add") or hasattr(lines, "match")):
        return lines
    candidate = None
    try:
        from ircd.lines import Lines

        try:
            candidate = Lines()
        except TypeError:
            try:
                candidate = Lines(server)
            except Exception:
                candidate = _FallbackLines()
    except Exception:
        candidate = _FallbackLines()
    try:
        server.lines = candidate
    except Exception:
        pass
    return candidate


async def _maybe_await(result):
    if inspect.isawaitable(result):
        await result


async def _send(conn, line):
    """Deliver one raw line to a connection, awaiting if needed."""
    await _maybe_await(conn.send(line))


async def _record(server, actor_nick, act, target, detail):
    """Write the ledger entry. This ALWAYS runs before the act.

    MECHANISM: the canonical signature is keyword-shaped --
    record(actor=, act=, target=, detail=, via='IRCopBot'). A
    store that refuses keywords is retried positionally with via
    appended, so a differently-shaped double still gets its entry
    written first rather than the act proceeding unrecorded.
    """
    ledger = _get_ledger(server)
    try:
        result = ledger.record(
            actor=actor_nick, act=act, target=target, detail=detail,
            via="IRCopBot",
        )
    except TypeError:
        try:
            result = ledger.record(actor_nick, act, target, detail, "IRCopBot")
        except TypeError:
            result = ledger.record(actor_nick, act, target, detail)
    await _maybe_await(result)
    return ledger


async def _lines_add(lines, mask, reason):
    """Add a *-line, tolerating signature drift in the store.

    MECHANISM: setter is recorded as 'IRCopBot' on purpose -- the
    store faces the wire, and the wire names the bot; the ledger
    (written before this call) is where the director is named.
    """
    attempts = (
        lambda: lines.add(mask, reason, setter="IRCopBot"),
        lambda: lines.add(mask, reason, "IRCopBot"),
        lambda: lines.add(mask, reason=reason, setter="IRCopBot"),
        lambda: lines.add(mask, reason),
    )
    last_error = None
    for attempt in attempts:
        try:
            result = attempt()
            await _maybe_await(result)
            return True
        except TypeError as exc:
            last_error = exc
            continue
        except Exception:
            return False
    if last_error is not None:
        raise last_error
    return False


def _lines_match(lines, mask, candidate):
    """Decide whether *candidate* is caught by *mask*.

    MECHANISM: the store's own match() is the first witness (it
    knows its expiries and its canonical mask form); plain glob
    matching of the directed mask against the candidate, folded to
    lower case, is the second. Either witness catching is a catch.
    """
    if lines is not None:
        match = getattr(lines, "match", None)
        if callable(match):
            try:
                if match(candidate):
                    return True
            except Exception:
                pass
    try:
        return fnmatch.fnmatchcase(str(candidate).lower(), str(mask).lower())
    except Exception:
        return False


def _msg_text(msg):
    """Rebuild the command text from a parsed PRIVMSG Message."""
    params = list(getattr(msg, "params", []) or [])
    if len(params) > 2:
        return " ".join(params[1:])
    if len(params) == 2:
        return params[1]
    if len(params) == 1:
        return params[0]
    return getattr(msg, "trailing", "") or ""


def _candidate_strings(target):
    """The strings a *-line mask is weighed against for one user.

    MECHANISM: a mask may aim at any face a user shows the wire --
    the full prefix, the user@host pair, the bare host, the bare
    nick (and its user!host-expanded cousins). All are offered, so
    the form of mask an oper writes is the oper's choice, not a
    trap laid by the matcher.
    """
    nick = getattr(target, "nick", "") or ""
    user = getattr(target, "user", "") or ""
    host = getattr(target, "host", "") or ""
    prefix = getattr(target, "prefix", None)
    if callable(prefix):
        try:
            prefix = prefix()
        except Exception:
            prefix = None
    candidates = []
    for value in (prefix, nick, host, f"{user}@{host}", f"{nick}!{user}@{host}"):
        if value:
            candidates.append(str(value))
    return candidates


def _find_conn(server, nick):
    """Find a connected user by nick, case-insensitively."""
    connections = getattr(server, "connections", None) or {}
    if isinstance(connections, dict):
        direct = connections.get(nick.lower())
        if direct is not None:
            return direct
        for key, value in connections.items():
            value_nick = getattr(value, "nick", None)
            if isinstance(value_nick, str) and value_nick.lower() == nick.lower():
                return value
            if isinstance(key, str) and key.lower() == nick.lower():
                return value
    else:
        try:
            for value in connections:
                if (getattr(value, "nick", "") or "").lower() == nick.lower():
                    return value
        except TypeError:
            pass
    return None


def _get_channel(server, chan_name):
    channels = getattr(server, "channels", None) or {}
    if not isinstance(channels, dict):
        return None
    if chan_name in channels:
        return channels[chan_name]
    return channels.get(chan_name.lower())


def _member_conns(channel):
    """Collect the distinct Conn objects standing in a channel."""
    found, seen = [], set()
    members = getattr(channel, "members", None) if channel is not None else None
    candidates = []
    if isinstance(members, dict):
        candidates.extend(members.keys())
        candidates.extend(members.values())
    elif members is not None:
        try:
            candidates.extend(list(members))
        except TypeError:
            candidates = []
    for cand in candidates:
        if hasattr(cand, "send") and id(cand) not in seen:
            seen.add(id(cand))
            found.append(cand)
    return found


async def _disconnect(server, target, quit_line):
    """Send *quit_line*, close *target*, and erase its presence.

    MECHANISM: the farewell line is sent first (a dropped user is
    told by whom and why -- the bot signs its work on the wire).
    Close is attempted through disconnect() then close(), whichever
    the connection offers; a bare double with neither still loses
    its seat, because removal from the server's tables is done here
    regardless: connections, every channel's member and
    member-mode tables, and the connection's own channel set.
    DOCTRINE: removal is total and in one place, so no ghost seat
    lingers in a channel after its owner is gone.
    """
    nick_lower = (getattr(target, "nick", "") or "").lower()
    try:
        await _send(target, quit_line)
    except Exception:
        pass
    for attr in ("disconnect", "close"):
        method = getattr(target, attr, None)
        if callable(method):
            try:
                await _maybe_await(method())
            except TypeError:
                try:
                    await _maybe_await(method("IRCopBot"))
                except Exception:
                    pass
            except Exception:
                pass
            break
    connections = getattr(server, "connections", None)
    if isinstance(connections, dict):
        for key in list(connections.keys()):
            value = connections.get(key)
            if value is target or (
                isinstance(key, str) and key.lower() == nick_lower
            ):
                try:
                    del connections[key]
                except Exception:
                    pass
    channels = getattr(server, "channels", None) or {}
    if isinstance(channels, dict):
        chan_items = list(channels.items())
    else:
        chan_items = []
    for _name, channel in chan_items:
        for table_name in ("members", "member_modes"):
            table = getattr(channel, table_name, None)
            if isinstance(table, dict):
                for key in list(table.keys()):
                    value = table.get(key)
                    key_nick = getattr(key, "nick", None)
                    if (
                        value is target
                        or key is target
                        or (isinstance(key, str) and key.lower() == nick_lower)
                        or (isinstance(key_nick, str)
                            and key_nick.lower() == nick_lower)
                    ):
                        try:
                            del table[key]
                        except Exception:
                            pass
            elif table is not None:
                try:
                    table.discard(target)
                except Exception:
                    pass
    own_channels = getattr(target, "channels", None)
    if own_channels is not None:
        try:
            own_channels.clear()
        except Exception:
            pass


def _apply_channel_mode(channel, letter, sign):
    """Add or remove a channel mode letter on channel.modes."""
    modes = getattr(channel, "modes", None)
    if modes is None:
        try:
            channel.modes = {letter} if sign == "+" else set()
        except Exception:
            return
        return
    if isinstance(modes, set):
        if sign == "+":
            modes.add(letter)
        else:
            modes.discard(letter)
    elif isinstance(modes, list):
        if sign == "+" and letter not in modes:
            modes.append(letter)
        elif sign == "-" and letter in modes:
            modes.remove(letter)
    elif isinstance(modes, dict):
        if sign == "+":
            modes[letter] = True
        else:
            modes.pop(letter, None)
    elif isinstance(modes, str):
        letters = set(modes)
        if sign == "+":
            letters.add(letter)
        else:
            letters.discard(letter)
        try:
            channel.modes = letters
        except Exception:
            pass


def _apply_member_mode(channel, nick, letter, sign):
    """Add or remove a member mode letter in channel.member_modes."""
    member_modes = getattr(channel, "member_modes", None)
    if member_modes is None:
        try:
            channel.member_modes = (
                {nick.lower(): {letter}} if sign == "+" else {}
            )
        except Exception:
            return
        return
    if not isinstance(member_modes, dict):
        return
    key = nick.lower()
    entry = member_modes.get(key)
    if entry is None:
        for existing_key, existing_val in list(member_modes.items()):
            existing_nick = getattr(existing_key, "nick", None)
            if isinstance(existing_nick, str) and existing_nick.lower() == key:
                key, entry = existing_key, existing_val
                break
    if entry is None:
        if sign == "+":
            member_modes[key] = {letter}
        return
    if isinstance(entry, set):
        if sign == "+":
            entry.add(letter)
        else:
            entry.discard(letter)
    elif isinstance(entry, list):
        if sign == "+" and letter not in entry:
            entry.append(letter)
        elif sign == "-" and letter in entry:
            entry.remove(letter)
    elif isinstance(entry, str):
        letters = set(entry)
        if sign == "+":
            letters.add(letter)
        else:
            letters.discard(letter)
        member_modes[key] = letters


class IRCopBot:
    """Staff-only services bot: the proxy hand of incognito opers.

    MECHANISM: HELP, KLINE, DROP and MODE are the whole surface.
    There is deliberately no timer, no hook and no autonomous path
    into any of them -- the class cannot act until ``handle`` is
    called with an oper's direction, which is the founder's ruling
    ("no initiative of its own") expressed as architecture.
    """

    nick = "IRCopBot"

    def __init__(self):
        # MECHANISM: the bot is stateless; all state it touches
        # (ledger, lines, connections, channels) is the server's.
        pass

    async def _notice(self, conn, text):
        line = format_msg("NOTICE", conn.nick, text, prefix=self.nick)
        await _send(conn, line)

    async def _report(self, conn, text):
        """Report an execution to the directing oper by PRIVMSG.

        DOCTRINE: executions report by PRIVMSG, not NOTICE -- the
        report is a conversation the oper opened, carrying the
        mask/target, the reason, the measured effect, and the
        ledger confirmation, so the officer who ordered the act
        holds its receipt in the same channel they ordered it in.
        """
        line = format_msg("PRIVMSG", conn.nick, text, prefix=self.nick)
        await _send(conn, line)

    async def handle(self, server, conn, msg):
        """Dispatch one PRIVMSG directing the IRCopBot.

        DOCTRINE: fail closed at the door. A non-oper direction is
        refused with a NOTICE and nothing else happens -- no parse
        reaches a command, no ledger entry is written, because an
        unauthorised direction is not an oper act at all.
        """
        if not getattr(conn, "is_oper", False):
            await self._notice(
                conn,
                "Access denied: IRCopBot answers authenticated IRC "
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
        elif command == "KLINE":
            await self._do_kline(server, conn, tokens)
        elif command == "DROP":
            await self._do_drop(server, conn, tokens)
        elif command == "MODE":
            await self._do_mode(server, conn, tokens)
        else:
            await self._notice(
                conn,
                f"Unknown IRCopBot command '{tokens[0]}'. "
                "Try: HELP, KLINE, DROP, MODE.",
            )

    async def _do_help(self, conn):
        lines = [
            "IRCopBot -- proxy hand of the house's operators (opers only).",
            "HELP - show this help.",
            "KLINE <mask> <reason...> - *-line a mask and drop matching users.",
            "DROP <nick> <reason...> - drop one named user, signed by the bot.",
            "MODE <#channel> <modes...> - apply modes as the bot (e.g. MODE #c +o Nick, MODE #c +m).",
            "Every act is entered in the house ledger, under the directing oper's name, BEFORE it executes.",
        ]
        for line in lines:
            await self._notice(conn, line)

    async def _do_kline(self, server, conn, tokens):
        """KLINE <mask> <reason...>: ban a mask, drop its matches.

        ORDER IS DOCTRINE: (1) ledger, (2) line store, (3) drops.
        The entry names the directing oper as actor even though the
        wire will only ever name the bot -- that asymmetry is the
        entire design of the incognito desk.
        """
        if len(tokens) < 2:
            await self._notice(conn, "Usage: KLINE <mask> <reason...>.")
            return
        mask = tokens[1]
        reason = " ".join(tokens[2:]) if len(tokens) > 2 else "No reason given"
        # (1) LEDGER FIRST. Nothing below this line may run before it.
        await _record(server, conn.nick, "KLINE", mask, reason)
        # (2) Lay the line in the store, under the bot's name.
        lines = _get_lines(server)
        try:
            await _lines_add(lines, mask, reason)
        except Exception:
            # MECHANISM: a store that refuses the add does not stop
            # the drops the oper ordered; the ledger already holds
            # the act, and the report says what was measured.
            pass
        # (3) Drop every currently connected user the mask catches.
        connections = getattr(server, "connections", None) or {}
        if isinstance(connections, dict):
            targets = list(connections.values())
        else:
            try:
                targets = list(connections)
            except TypeError:
                targets = []
        dropped = []
        quit_line = format_msg(
            "ERROR",
            f"Closing Link: K-Lined by IRCopBot: {reason}",
            prefix=self.nick,
        )
        for target in targets:
            candidates = _candidate_strings(target)
            if any(_lines_match(lines, mask, cand) for cand in candidates):
                dropped.append(getattr(target, "nick", "?"))
                await _disconnect(server, target, quit_line)
        names = ", ".join(dropped) if dropped else "none"
        await self._report(
            conn,
            f"KLINE executed: mask={mask} reason={reason} "
            f"disconnected={len(dropped)} ({names}) "
            "ledger=recorded (entry written before execution, "
            f"actor={conn.nick} via=IRCopBot).",
        )

    async def _do_drop(self, server, conn, tokens):
        """DROP <nick> <reason...>: remove one named user, bot-signed.

        MECHANISM: the target's farewell line carries the bot's
        signature and the oper's reason -- 'IRCopBot: <reason>' --
        and never the directing oper's nick. The ledger entry,
        written before the drop, is the only place that nick lives.
        """
        if len(tokens) < 2:
            await self._notice(conn, "Usage: DROP <nick> <reason...>.")
            return
        target_nick = tokens[1]
        reason = " ".join(tokens[2:]) if len(tokens) > 2 else "No reason given"
        target = _find_conn(server, target_nick)
        if target is None:
            await self._report(
                conn,
                f"DROP not executed: no user named {target_nick} is "
                "currently connected.",
            )
            return
        # LEDGER FIRST, then the act -- the same unbreakable order.
        await _record(server, conn.nick, "DROP", target_nick, reason)
        quit_line = format_msg(
            "QUIT", f"IRCopBot: {reason}", prefix=self.nick
        )
        await _disconnect(server, target, quit_line)
        await self._report(
            conn,
            f"DROP executed: {target_nick} dropped by IRCopBot "
            f"reason={reason} ledger=recorded (entry written before "
            f"execution, actor={conn.nick} via=IRCopBot).",
        )

    async def _do_mode(self, server, conn, tokens):
        """MODE <#chan> <modes...>: intervene in a channel as the bot.

        MECHANISM: the mode string is walked letter by letter under
        its current sign. Letters of the member ladder (q/a/o/h/v)
        consume the next argument as their target nick and land in
        member_modes; every other letter lands in the channel's own
        mode set. The change is then announced on the wire exactly
        as directed, sourced from the bot.
        """
        if len(tokens) < 3 or not tokens[1].startswith("#"):
            await self._notice(
                conn, "Usage: MODE <#channel> <modes...> (e.g. MODE #c +o Nick)."
            )
            return
        chan_name = tokens[1]
        mode_tokens = tokens[2:]
        detail = " ".join(mode_tokens)
        # LEDGER FIRST, then the act.
        await _record(server, conn.nick, "MODE", chan_name, detail)
        channel = _get_channel(server, chan_name)
        if channel is None:
            await self._report(
                conn,
                f"MODE not executed: channel {chan_name} does not "
                "exist. ledger=recorded (attempt entered before "
                "execution).",
            )
            return
        mode_string = mode_tokens[0]
        args = mode_tokens[1:]
        arg_index = 0
        sign = "+"
        for letter in mode_string:
            if letter in "+-":
                sign = letter
                continue
            if letter in "qaohv" and arg_index < len(args):
                _apply_member_mode(
                    channel, args[arg_index], letter, sign
                )
                arg_index += 1
            elif letter in "qaohv":
                # MECHANISM: a member letter with no nick left to
                # consume cannot be applied to anyone; it is not
                # silently re-homed onto the channel's own modes.
                continue
            else:
                _apply_channel_mode(channel, letter, sign)
        line = format_msg(
            "MODE", chan_name, *mode_tokens, prefix=self.nick
        )
        members = _member_conns(channel)
        delivered = 0
        for member in members:
            try:
                await _send(member, line)
                delivered += 1
            except Exception:
                continue
        if delivered == 0:
            broadcast = getattr(server, "broadcast_local", None)
            if callable(broadcast):
                try:
                    await _maybe_await(broadcast(line))
                except Exception:
                    pass
        await self._report(
            conn,
            f"MODE executed: {chan_name} {detail} "
            "ledger=recorded (entry written before execution, "
            f"actor={conn.nick} via=IRCopBot).",
        )


# 93 -- Live, Love, and let Love, Live.
