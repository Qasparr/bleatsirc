# 93
# ---------------------------------------------------------------------
# chanserv.py -- ChanServ, the channel desk of the house.
#
# "First come, first served. If you don't register the channel and
#  the channel empties and someone else registers it, that's a fair
#  takeover, we will not help with this issue." -- the founder's
#  ruling, CUSTOM-IRCD-SPEC network policy rule 7.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026 / Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: ChanServ is an embedded pseudoclient. It owns no socket
# and no thread; the daemon routes a PRIVMSG addressed to its nick
# into ``handle(server, conn, msg)``, and every answer rides the
# directing user's own connection back out as a NOTICE from
# "ChanServ". Its whole database, for this Proof of Concept, is one
# in-memory dict mapping a lower-cased channel name to the founder
# nick that claimed it.
# DOCTRINE: registration is the channel founder's own duty, and the
# record kept is only the record registration itself requires -- a
# channel name and the nick that founded it. No telemetry, no extra
# custody: the house keeps what the member created, nothing more.
# The founder claim is first-come: once a name is in the book, a
# second REGISTER is refused with the standing founder named, never
# silently overwritten -- dispositions are marked, never vanished.
# ---------------------------------------------------------------------

import inspect

from ircd.protocol import format_msg


# MECHANISM: conn.send is a plain method on the real Conn and a
# recording stub on test doubles; either may return a coroutine.
# Awaiting only when the result is awaitable keeps one helper honest
# against both shapes, so no service ever guesses wrong about the
# transport underneath it.
async def _send(conn, line):
    """Deliver one raw line to a connection, awaiting if needed."""
    result = conn.send(line)
    if inspect.isawaitable(result):
        await result


# MECHANISM: server.broadcast_local may likewise be sync or async
# depending on the daemon (or double) that provides it; the same
# await-if-awaitable discipline applies.
async def _maybe_call(func, *args):
    result = func(*args)
    if inspect.isawaitable(result):
        await result


def _msg_text(msg):
    """Rebuild the command text from a parsed PRIVMSG Message.

    MECHANISM: the canonical shape is params == [target, text] with
    the text riding as the trailing parameter. Doubles that split
    the text into extra middle params are tolerated by re-joining
    everything after the target, so the parse is weighed once and
    never re-read from a raw line that no longer exists here.
    """
    params = list(getattr(msg, "params", []) or [])
    if len(params) > 2:
        return " ".join(params[1:])
    if len(params) == 2:
        return params[1]
    if len(params) == 1:
        return params[0]
    return getattr(msg, "trailing", "") or ""


def _get_channel(server, chan_name):
    """Look a channel up by name, case-insensitively, or return None."""
    channels = getattr(server, "channels", None) or {}
    if not isinstance(channels, dict):
        return None
    if chan_name in channels:
        return channels[chan_name]
    return channels.get(chan_name.lower())


def _is_in_channel(server, conn, chan_name, channel):
    """Decide whether *conn* stands inside *channel* right now.

    MECHANISM: two witnesses are consulted and either suffices --
    the connection's own channel set (names, any case) and the
    channel's member table (which may key by lower-cased nick string
    or by the Conn object itself on some doubles).
    DOCTRINE: a founder must be standing on the ground they claim;
    presence is the proof, so both records of presence are honoured.
    """
    nick_lower = (getattr(conn, "nick", "") or "").lower()
    chan_lower = chan_name.lower()
    for name in getattr(conn, "channels", None) or ():
        if isinstance(name, str) and name.lower() == chan_lower:
            return True
    members = getattr(channel, "members", None) if channel is not None else None
    if isinstance(members, dict):
        if nick_lower in members:
            return True
        for key, value in members.items():
            if value is conn:
                return True
            key_nick = getattr(key, "nick", None)
            if isinstance(key_nick, str) and key_nick.lower() == nick_lower:
                return True
            if isinstance(key, str) and key.lower() == nick_lower:
                return True
    elif members is not None:
        try:
            if conn in members:
                return True
        except TypeError:
            pass
    return False


def _member_conns(channel):
    """Collect the distinct Conn objects standing in a channel."""
    found = []
    seen = set()
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


def _grant_member_mode(channel, nick, letter):
    """Add a member mode letter for *nick* on *channel*.

    MECHANISM: member_modes is keyed by lower-cased nick in the
    canonical build; the entry beneath may be a set, a list, or a
    bare string of letters. Each shape is grown in place where it
    can be, and replaced with a set where it cannot, because the
    wire cares about the letter being present, not its container.
    """
    member_modes = getattr(channel, "member_modes", None)
    if member_modes is None:
        try:
            channel.member_modes = {nick.lower(): {letter}}
        except Exception:
            return False
        return True
    if not isinstance(member_modes, dict):
        return False
    key = nick.lower()
    entry = member_modes.get(key)
    if entry is None:
        # DOCTRINE: fall back to a Conn-keyed entry if the double
        # stores modes against the connection object instead.
        for existing_key, existing_val in list(member_modes.items()):
            existing_nick = getattr(existing_key, "nick", None)
            if isinstance(existing_nick, str) and existing_nick.lower() == key:
                key, entry = existing_key, existing_val
                break
    if entry is None:
        member_modes[key] = {letter}
    elif isinstance(entry, set):
        entry.add(letter)
    elif isinstance(entry, list):
        if letter not in entry:
            entry.append(letter)
    elif isinstance(entry, str):
        if letter not in entry:
            member_modes[key] = set(entry) | {letter}
    else:
        try:
            entry.add(letter)
        except Exception:
            member_modes[key] = {letter}
    return True


class ChanServ:
    """Embedded channel-services pseudoclient.

    MECHANISM: one instance lives in ``server.services`` under its
    nick. ``registrations`` is the entire POC database:
    {channel-name-lower: founder-nick-as-claimed}. ``founders`` is
    the same book under its older name, exposed so no caller has to
    guess which word the desk used.
    """

    nick = "ChanServ"

    def __init__(self):
        self.registrations = {}

    @property
    def founders(self):
        """Alias view of the registrations book (the same dict)."""
        return self.registrations

    async def _notice(self, conn, text):
        """Answer the directing user with a NOTICE from ChanServ."""
        line = format_msg("NOTICE", conn.nick, text, prefix=self.nick)
        await _send(conn, line)

    async def handle(self, server, conn, msg):
        """Dispatch one PRIVMSG addressed to ChanServ.

        MECHANISM: the command word is the first token of the
        trailing text; the rest of the line is its argument. Only
        HELP, REGISTER and OP exist in this phase -- anything else
        is answered with the help text, fail-closed and polite.
        """
        text = _msg_text(msg).strip()
        tokens = text.split()
        if not tokens:
            await self._do_help(conn)
            return
        command = tokens[0].upper()
        if command == "HELP":
            await self._do_help(conn)
        elif command == "REGISTER":
            await self._do_register(server, conn, tokens)
        elif command == "OP":
            await self._do_op(server, conn, tokens)
        else:
            await self._notice(
                conn,
                f"Unknown ChanServ command '{tokens[0]}'. "
                "Try: HELP, REGISTER <#channel>, OP <#channel>.",
            )

    async def _do_help(self, conn):
        """NOTICE the command list, one line per command."""
        lines = [
            "ChanServ -- the channel desk of the house.",
            "HELP - show this help.",
            "REGISTER <#channel> - register a channel you are in as its founder.",
            "OP <#channel> - reclaim +o in a channel you founded.",
        ]
        for line in lines:
            await self._notice(conn, line)

    async def _do_register(self, server, conn, tokens):
        """REGISTER <#chan>: claim a channel the caller stands in.

        DOCTRINE: first come, first served. An unregistered channel
        is unowned ground; the first member standing in it who asks
        becomes its founder, and that claim then stands against
        every later REGISTER until the house itself says otherwise.
        """
        if len(tokens) < 2 or not tokens[1].startswith("#"):
            await self._notice(
                conn, "Usage: REGISTER <#channel> -- the name must start with #."
            )
            return
        chan_name = tokens[1]
        chan_lower = chan_name.lower()
        channel = _get_channel(server, chan_name)
        if channel is None or not _is_in_channel(server, conn, chan_name, channel):
            await self._notice(
                conn,
                f"Cannot register {chan_name}: the channel does not exist "
                "or you are not in it. Join it first, then REGISTER.",
            )
            return
        existing = self.registrations.get(chan_lower)
        if existing is None and channel is not None:
            existing = getattr(channel, "founder", None)
        if existing:
            await self._notice(
                conn,
                f"{chan_name} is already registered to {existing}.",
            )
            return
        # MECHANISM: the book stores the founder nick as claimed
        # (case preserved for display); comparisons elsewhere fold
        # case, per CASEMAPPING. The channel object is stamped too,
        # when it allows it, so channel handlers see the same fact.
        self.registrations[chan_lower] = conn.nick
        if channel is not None:
            try:
                channel.founder = conn.nick
            except Exception:
                pass
        await self._notice(
            conn,
            f"Channel {chan_name} registered to {conn.nick}. "
            "You are its founder.",
        )

    async def _do_op(self, server, conn, tokens):
        """OP <#chan>: a founder reclaims +o in their own channel.

        MECHANISM: founderhood is proven against the registrations
        book first and the channel's own founder stamp second --
        either witness suffices. The grant writes 'o' into the
        channel's member_modes for the caller's nick and announces
        the change on the wire as a ChanServ MODE line, exactly as
        a services uplink would on a split network.
        """
        if len(tokens) < 2 or not tokens[1].startswith("#"):
            await self._notice(conn, "Usage: OP <#channel>.")
            return
        chan_name = tokens[1]
        chan_lower = chan_name.lower()
        channel = _get_channel(server, chan_name)
        founder = self.registrations.get(chan_lower)
        if founder is None and channel is not None:
            founder = getattr(channel, "founder", None)
        if not founder or str(founder).lower() != (conn.nick or "").lower():
            await self._notice(
                conn,
                f"Access denied: only the founder of {chan_name} may use OP.",
            )
            return
        if channel is None:
            await self._notice(
                conn, f"Cannot OP in {chan_name}: the channel does not exist."
            )
            return
        _grant_member_mode(channel, conn.nick, "o")
        line = format_msg("MODE", chan_name, "+o", conn.nick, prefix=self.nick)
        members = _member_conns(channel)
        delivered = 0
        for member in members:
            try:
                await _send(member, line)
                delivered += 1
            except Exception:
                continue
        if delivered == 0:
            # MECHANISM: with no member table to walk, the server
            # broadcast is the fallback road for the same line.
            broadcast = getattr(server, "broadcast_local", None)
            if callable(broadcast):
                try:
                    await _maybe_call(broadcast, line)
                except Exception:
                    pass
        await self._notice(conn, f"You are now +o in {chan_name}.")


# 93 -- Live, Love, and let Love, Live.
