# 93
# ---------------------------------------------------------------------
# core.py -- the client core: one line in, one Event out.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: every raw line arriving from a server is parsed exactly
# ONCE, by ircd.protocol.parse_line -- the same grammar the daemon
# speaks -- into a Message, and that single parse is then weighed
# into a structured Event. The Event feeds every consumer alike:
# the internal trigger engine, the bridge to external scripts in any
# tongue, and the terminal UI. Nothing downstream re-reads the raw
# line; nothing downstream keeps its own private parser.
# DOCTRINE: one parse, shared by daemon and client both, is the
# house rule that a thing be weighed once, in its own tongue, and
# the weighing shared. A second grammar would be a second truth,
# and two truths about one wire is how state drifts and lies.
#
# MECHANISM: dispatch is a hash Registry (ircd.protocol.Registry),
# never a scan and never a goto chain -- the founder's ruling of
# 2026-11-07. Command handlers register under the uppercased
# command, numeric handlers under the key "NUM:<code>", and generic
# handlers under "*". Lookup is O(1); chains run in registration
# order. The registry is shared and protocol-global, but every
# Event carries its connection_id and all mutable state built from
# the stream (our nick, channel membership, ISUPPORT) lives in a
# per-connection dict, so state from one network never bleeds into
# another -- multiserver means many worlds, kept separate.
# DOCTRINE: per-connection state never bleeds. That invariant is
# the client form of the Line: private is private, server by
# server, and a names list learned on one network is not knowledge
# about any other.
#
# MECHANISM: this module is transport-free and synchronous. It
# opens no socket, spawns no thread, and reads no clock; a caller
# (bridge, TUI, test) owns the wire and simply hands lines to
# feed(). That is what lets the same core sit behind a CLI, an SSH
# attach, a telnet attach, or a unit test without changing a line.
# ---------------------------------------------------------------------

from dataclasses import dataclass, field

from ircd.protocol import Message, Registry, parse_line

# MECHANISM: the mode-prefix characters a 353 names reply may hang
# on a nick -- @ (op), % (halfop), + (voice), ~ (owner), & (admin).
# They describe a member's standing in the channel, not the nick
# itself, so the membership set stores the bare nick with the
# prefix stripped from the front.
_NAME_PREFIX_CHARS = "@%+~&"


@dataclass
class Event:
    """One parsed line, structured for every consumer.

    connection_id: which server connection this line arrived on;
        the multiserver context, carried as a first-class field so
        a handler can scope itself to one network or ride all.
    kind:    'command' | 'numeric' | 'event' | 'raw'. feed()
        produces 'numeric' for a three-digit command, 'command'
        for a named command, and 'raw' for a line that carried no
        usable command at all (the fallback floor: raw passthrough
        underneath, never nothing).
    command: the uppercased command word or three-digit string;
        '' for a raw event.
    numeric: the integer code when kind is 'numeric', else None.
    source:  the originating nick when the prefix is a full
        nick!user@host mask, else the server-name prefix, else
        None when the line carried no prefix.
    target:  the thing the line is aimed at -- a channel or our
        own nick -- derived per command (see feed()); None when
        the line carries no parameter to aim at.
    text:    the trailing parameter, or '' when there was none.
        For PRIVMSG/NOTICE this is the message body; for 353 it is
        the names list; for NICK it is the new nick.
    params:  all parameters exactly as parse_line produced them,
        trailing included as the final element when present.
    raw:     the original line, CRLF stripped -- kept on the event
        so the raw window and the scripting trace can show the wire
        verbatim without anyone re-deriving it.
    """

    connection_id: str
    kind: str
    command: str
    numeric: int | None
    source: str | None
    target: str | None
    text: str
    params: list = field(default_factory=list)
    raw: str = ""


class ClientCore:
    """The event engine: connection state plus hash dispatch.

    MECHANISM: connections is a plain dict, cid -> state dict, and
    the handler table is one ircd.protocol.Registry shared across
    connections (numerics and commands are protocol-global) while
    dispatch itself happens per feed() call, against the Event of
    that one connection. Handlers are synchronous callables taking
    a single Event: fn(event).
    """

    def __init__(self) -> None:
        # Per-connection state, keyed by the caller's connection id.
        self.connections: dict[str, dict] = {}
        # The one dispatch table. Command keys are the uppercased
        # command, numeric keys are "NUM:<code>", the generic key
        # is "*". Registry.on() uppercases keys, which leaves the
        # "NUM:" prefix and "*" untouched in effect.
        self._registry = Registry()

    # -- registration ------------------------------------------------
    # MECHANISM: three thin doors onto the one Registry, so script
    # and trigger code reads in the founder's event vocabulary --
    # on a command, on a numeric, on everything -- while the table
    # underneath stays a single hash of chains.

    def on(self, command: str, fn) -> None:
        """Register fn(event) for a command, or for '*' (all events)."""
        self._registry.on(command, fn)

    def on_numeric(self, code: int, fn) -> None:
        """Register fn(event) for one numeric code, e.g. on_numeric(353, fn)."""
        self._registry.on(f"NUM:{int(code)}", fn)

    # -- connection state ---------------------------------------------
    # MECHANISM: a state dict is {'nick': our nick on that server
    # or None, 'channels': {channel name -> set of member nicks},
    # 'isupport': {token -> value string, or True for a bare flag}}.
    # It is created lazily and owned by exactly one connection.

    def add_connection(self, cid: str) -> dict:
        """Create state for cid; a no-op (never a wipe) if it exists."""
        if cid not in self.connections:
            self.connections[cid] = {
                "nick": None,
                "channels": {},
                "isupport": {},
            }
        return self.connections[cid]

    def remove_connection(self, cid: str) -> None:
        """Drop cid's state if present; absent cids are not an error."""
        self.connections.pop(cid, None)

    def state(self, cid: str) -> dict:
        """Return cid's state dict, auto-creating it if missing."""
        return self.add_connection(cid)

    # -- the one road in ----------------------------------------------

    def feed(self, cid: str, line: str) -> Event:
        """Parse one raw line from connection cid into an Event.

        MECHANISM: strip CRLF, parse once via parse_line, derive
        kind/source/target/text, update this connection's state,
        then dispatch -- numeric chain, command chain, '*' chain --
        and return the Event. State is updated BEFORE dispatch so a
        handler always reads the world as the line left it, never
        as it was one line ago.
        DOCTRINE: feed() never raises. A malformed line is data, not
        a death: it comes back as a raw Event so the fallback floor
        (raw passthrough) holds and the session survives its worst
        line.
        """
        stripped = line.rstrip("\r\n") if isinstance(line, str) else ""
        state = self.state(cid)

        # DOCTRINE: an empty or whitespace-only line says nothing;
        # it is returned raw at once, with no parse and no dispatch,
        # because there is no event in it for anyone to handle.
        if not stripped.strip():
            return Event(
                connection_id=cid,
                kind="raw",
                command="",
                numeric=None,
                source=None,
                target=None,
                text="",
                params=[],
                raw=stripped,
            )

        try:
            msg = parse_line(stripped)
        except Exception:
            # parse_line is total over str input in practice; this
            # guard is the fail-closed floor if that ever changes.
            return Event(
                connection_id=cid,
                kind="raw",
                command="",
                numeric=None,
                source=None,
                target=None,
                text="",
                params=[],
                raw=stripped,
            )

        try:
            event = self._build_event(cid, msg, stripped)
            self._update_state(state, msg, event)
        except Exception:
            # DOCTRINE: a derivation or bookkeeping fault on one
            # line must not kill the core or lose the line itself;
            # fall back to the raw floor for this line only.
            return Event(
                connection_id=cid,
                kind="raw",
                command="",
                numeric=None,
                source=None,
                target=None,
                text="",
                params=[],
                raw=stripped,
            )

        self._dispatch(msg, event)
        return event

    # -- derivation -----------------------------------------------------

    def _build_event(self, cid: str, msg: Message, raw: str) -> Event:
        """Weigh one parsed Message into an Event (no state touched)."""
        command = msg.command
        params = list(msg.params)

        # MECHANISM: kind is read off the command's shape alone --
        # exactly three digits is a numeric reply, a word of letters
        # is a command, and anything else is raw. The grammar admits
        # only letters or three digits in the command seat (RFC 1459
        # section 2.3.1), so a token carrying control characters or
        # punctuation is not a command at all: it degrades to 'raw',
        # the fallback floor, and no handler chain is built on it.
        if len(command) == 3 and command.isdigit():
            kind = "numeric"
            numeric: int | None = int(command)
        elif command.isalpha():
            kind = "command"
            numeric = None
        else:
            kind = "raw"
            numeric = None

        # DOCTRINE: a raw Event has ONE shape wherever it is born --
        # the same empty fields feed() returns for an empty line --
        # so consumers can trust kind='raw' to mean "no weighed
        # fields; read .raw if you want the line itself".
        if kind == "raw":
            return Event(
                connection_id=cid,
                kind="raw",
                command="",
                numeric=None,
                source=None,
                target=None,
                text="",
                params=[],
                raw=raw,
            )

        # MECHANISM: the source is a nick only when the prefix is a
        # full mask (it contains '!'), because a bare prefix is a
        # server name and calling it a nick would forge an author.
        if msg.prefix and "!" in msg.prefix and msg.source_nick:
            source = msg.source_nick
        elif msg.prefix:
            source = msg.prefix
        else:
            source = None

        target = self._derive_target(command, numeric, params)

        return Event(
            connection_id=cid,
            kind=kind,
            command=command,
            numeric=numeric,
            source=source,
            target=target,
            text=msg.trailing,
            params=params,
            raw=raw,
        )

    @staticmethod
    def _derive_target(
        command: str, numeric: int | None, params: list
    ) -> str | None:
        """The line's aim, per command -- one place, one rule each.

        MECHANISM: 353 (names) and 001 (welcome) are special because
        their first parameter is our own nick, not the aim: a names
        reply aims at the channel in params[2], a welcome at the
        nick it confirms in params[0]. JOIN/PART/KICK and
        PRIVMSG/NOTICE all carry their channel-or-nick aim first.
        Everything else falls back to the first parameter, and a
        parameterless line aims at nothing.
        """
        if numeric == 353:
            return params[2] if len(params) > 2 else None
        if numeric == 1:
            return params[0] if params else None
        if command in ("PRIVMSG", "NOTICE"):
            return params[0] if params else None
        if command in ("JOIN", "PART"):
            # parse_line folds a trailing ":#chan" into params, so
            # the channel is params[0] whether it arrived as a
            # middle or a trailing parameter.
            return params[0] if params else None
        if command == "KICK":
            return params[0] if params else None
        return params[0] if params else None

    # -- state bookkeeping ----------------------------------------------
    # MECHANISM: only the lines that change what we know about THIS
    # connection are weighed here: 001 fixes our nick, 005 fills
    # ISUPPORT, JOIN/PART/KICK/353 maintain channel membership, and
    # NICK renames. Everything else is an event and nothing more --
    # the core keeps no state it was not ordered to keep.

    def _update_state(self, state: dict, msg: Message, event: Event) -> None:
        command = msg.command
        params = event.params
        own = state["nick"]
        channels: dict = state["channels"]

        if event.numeric == 1:
            # 001 Welcome: params[0] is the nick the server knows
            # us by -- the authority on our own name on this wire.
            if params:
                state["nick"] = params[0]
            return

        if event.numeric == 5:
            # 005 ISUPPORT: params[0] is our nick and the trailing
            # parameter is prose ("are supported by this server"),
            # so only the tokens between them are capabilities. A
            # KEY=value token records its value; a bare token is a
            # boolean flag and records True.
            for token in params[1:-1]:
                if "=" in token:
                    key, _, value = token.partition("=")
                    state["isupport"][key] = value
                else:
                    state["isupport"][token] = True
            return

        if event.numeric == 353:
            # 353 names reply: params[2] is the channel, the
            # trailing parameter is the space-separated names list.
            # The entry is created if missing -- a names reply may
            # be the first word we hear about a channel we joined
            # before this core started watching.
            if len(params) > 2:
                members = channels.setdefault(params[2], set())
                for name in event.text.split():
                    nick = name.lstrip(_NAME_PREFIX_CHARS)
                    if nick:
                        members.add(nick)
            return

        if command == "JOIN":
            channel = event.target
            if channel is None:
                return
            if event.source is not None and event.source == own:
                # Our own join opens the channel entry; other users'
                # joins only add to an entry we already track, so a
                # stray join for an unwatched channel forges nothing.
                channels.setdefault(channel, set())
            elif channel in channels and event.source is not None:
                channels[channel].add(event.source)
            return

        if command == "PART":
            channel = event.target
            if channel is None:
                return
            if event.source is not None and event.source == own:
                # Our own part ends our knowledge of the channel.
                channels.pop(channel, None)
            elif channel in channels and event.source is not None:
                channels[channel].discard(event.source)
            return

        if command == "KICK":
            if len(params) < 2:
                return
            channel = params[0]
            # MECHANISM: the kicked field may be a comma list --
            # the house multi-kick, KICK #c u1,u2,u3 -- executed
            # from one line, in order. Each victim is weighed on
            # its own: if it is us, the whole channel entry goes;
            # otherwise only that nick leaves the member set.
            for kicked in params[1].split(","):
                kicked = kicked.strip()
                if not kicked:
                    continue
                if own is not None and kicked == own:
                    channels.pop(channel, None)
                elif channel in channels:
                    channels[channel].discard(kicked)
            return

        if command == "NICK":
            # The new nick rides the trailing parameter (or, in the
            # bare form, params[0] -- which IS the trailing slot as
            # parse_line folds it, so trailing covers both).
            new_nick = msg.trailing or (params[0] if params else "")
            if not new_nick or event.source is None:
                return
            if own is not None and event.source == own:
                state["nick"] = new_nick
            # Whoever renamed, the member sets follow the person:
            # swap old for new in every channel that held the old.
            for members in channels.values():
                if event.source in members:
                    members.discard(event.source)
                    members.add(new_nick)
            return

    # -- dispatch ---------------------------------------------------------

    def _dispatch(self, msg: Message, event: Event) -> None:
        """Run the handler chains for one Event, in ruled order.

        MECHANISM: numeric handlers for the code first (numerics
        only), then command handlers for msg.command, then the '*'
        generic handlers that see every event. Each chain runs in
        registration order.
        DOCTRINE: one bad script must not kill the client core.
        Every handler is called inside its own guard; an exception
        is caught per handler and the chain continues, so a broken
        trigger costs that trigger its event and nothing else --
        never the session, never the handlers behind it.
        """
        chains: list = []
        if event.numeric is not None:
            chains.append(self._registry.handlers_for(f"NUM:{event.numeric}"))
        if msg.command:
            chains.append(self._registry.handlers_for(msg.command))
        chains.append(self._registry.handlers_for("*"))

        for chain in chains:
            for fn in chain:
                try:
                    fn(event)
                except Exception:
                    continue


# 93 -- Live, Love, and let Love, Live.
