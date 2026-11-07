# 93
# ---------------------------------------------------------------------
# "One parse, one dispatch, no hidden doors."
#
# server.py -- the daemon's plumbing: accept, read, parse once,
# gate, dispatch, clean up.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: asyncio.start_server hands each accepted socket to
# _client_connected, which runs that client's read loop. Every line
# is parsed EXACTLY ONCE by protocol.parse_line and dispatched
# through protocol.Registry -- a hash table of command -> handlers.
# There is deliberately no if-chain over command names here beyond
# the two gates the brief itself rules (registration, unknown).
# DOCTRINE: fail closed. An unregistered connection may speak only
# the registration commands; anything else is answered 451 and
# dropped. An unknown command is answered 421. A handler that
# raises is logged to stderr and the loop survives -- one broken
# command must never silence a user.
# ---------------------------------------------------------------------

import asyncio
import sys
import time
import traceback

try:
    # Normal path: imported as part of the ircd package.
    from .protocol import Registry, format_msg, parse_line
    from .state import Channel, Conn, casefold
except ImportError:  # pragma: no cover - direct-file fallback
    from ircd.protocol import Registry, format_msg, parse_line
    from ircd.state import Channel, Conn, casefold


# MECHANISM: the only commands an unregistered connection may use.
# DOCTRINE: this set IS the fail-closed gate of CODING-BRIEF
# invariant 7 -- PONG and CAP are admitted alongside the brief's
# PASS/NICK/USER/QUIT/PING because a client that cannot answer a
# server PING or negotiate capabilities during registration would
# be locked out by the very gate meant to protect it.
PRE_REGISTRATION_COMMANDS = {"PASS", "NICK", "USER", "QUIT", "PING", "PONG", "CAP"}

# MECHANISM: RFC 1459 caps a message at 512 bytes including CRLF.
# A raw readline() longer than 514 bytes is truncated to 512 before
# decoding, so a hostile or broken peer cannot feed the parser an
# unbounded line. (readline itself is the POC's line source; the
# truncation is the enforced bound the brief asks for.)
MAX_RAW_LINE = 514
TRUNCATED_LINE = 512


class Server:
    """The daemon: registry, population indexes, and configuration.

    MECHANISM: `connections` maps casefolded nick -> Conn and
    `channels` maps casefolded channel name -> Channel. These two
    dicts are the daemon's census; helpers below (index_nick,
    drop_nick, remove_connection, send_to, broadcast_local) are the
    only sanctioned ways handlers mutate or address the census, so
    the indexes can never drift apart from reality by a handler
    editing one and forgetting the other.
    """

    def __init__(self) -> None:
        self.registry = Registry()
        self.connections = {}
        self.channels = {}
        self.started = int(time.time())
        # MECHANISM: one plain dict of configuration; handlers read
        # it, nothing hides elsewhere. `created` is a human date
        # string for the 001 burst, taken from the start time.
        self.config = {
            "server_name": "bleats.local",
            "network": "Bleats",
            "version": "bleats-ircd-poc-0.1",
            "olines": {"Qasparr": "proof-positive"},
            "created": time.strftime(
                "%a %b %d %Y at %H:%M:%S UTC", time.gmtime(self.started)
            ),
        }
        self._srv = None

        # DOCTRINE: Group 2 (services & oper) lands in parallel.
        # The ledger and the lines (KLINE store) are loaded
        # defensively: if their modules are absent or their
        # constructors do not yet match, the daemon runs without
        # them (None) rather than refusing to start. Handlers that
        # need them must check for None -- the ledger-before-act
        # invariant then fails closed in the handler, by design.
        self.ledger = self._instantiate_defensively("ircd.ledger", "Ledger")
        self.lines = self._instantiate_defensively("ircd.lines", "Lines")

        self._load_handlers()

    # -- defensive construction ------------------------------------

    def _instantiate_defensively(self, module_name, class_name):
        """Import module_name.class_name and instantiate, or None.

        MECHANISM: try a no-argument constructor first, then one
        taking this server; any failure leaves None. This is the
        seam that lets independently-built groups share one process
        without a flag day.
        """
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
        except Exception:
            return None
        for args in ((), (self,)):
            try:
                return cls(*args)
            except TypeError:
                continue
            except Exception:
                return None
        return None

    def _load_handlers(self) -> None:
        """Register every handler module that has landed.

        MECHANISM: each handlers module exposes HANDLERS, a list of
        (command, function) pairs using the house convention
        `async def h(server, conn, msg)`. Modules are imported
        defensively (try/except ImportError) so the daemon runs
        with whichever groups have landed; a module that exists but
        is malformed in some other way still raises, because hiding
        a real bug would be worse than crashing at startup.
        DOCTRINE: registration is data. The dispatch table is built
        from lists, never from control flow.
        """
        for module_name in (
            "ircd.handlers_core",
            "ircd.handlers_channel",
            "ircd.handlers_msg",
            "ircd.handlers_oper",
        ):
            try:
                module = __import__(module_name, fromlist=["HANDLERS"])
            except ImportError:
                continue
            for cmd, fn in getattr(module, "HANDLERS", []):
                self.registry.on(cmd, fn)

        # Services (Group 2) attach their pseudoclients through a
        # single hook. Guarded by hasattr AND try/except: the
        # services package may exist as an empty shell before its
        # attach() is written.
        try:
            from ircd import services

            if hasattr(services, "attach"):
                services.attach(self)
        except (ImportError, AttributeError):
            pass

    # -- lifecycle --------------------------------------------------

    async def start(self, host: str = "127.0.0.1", port: int = 6667) -> None:
        """Bind, store the asyncio.Server, and serve forever."""
        self._srv = await asyncio.start_server(self._client_connected, host, port)
        await self._srv.serve_forever()

    async def close(self) -> None:
        """Stop accepting and close the listening socket, if any."""
        if self._srv is not None:
            self._srv.close()
            try:
                await self._srv.wait_closed()
            except Exception:
                pass
            self._srv = None

    # -- census helpers (the handlers' sanctioned interface) --------

    def index_nick(self, conn) -> None:
        """Enter a conn in the census under its (casefolded) nick."""
        if conn.nick:
            self.connections[casefold(conn.nick)] = conn

    def drop_nick(self, conn) -> None:
        """Remove conn's census entry -- only if it maps to conn.

        MECHANISM: the identity check matters: a nick may have been
        re-registered by a newer connection, and dropping the key
        blindly would erase a living user.
        """
        if conn.nick:
            key = casefold(conn.nick)
            if self.connections.get(key) is conn:
                del self.connections[key]

    def remove_connection(self, conn) -> None:
        """Strike a conn from the census and from every channel.

        MECHANISM: channels left empty are deleted outright -- on
        this daemon a room with no one in it does not persist, so
        the next JOIN re-creates it and its creator is founder.
        """
        self.drop_nick(conn)
        for channel_name in list(conn.channels):
            channel = self.channels.get(casefold(channel_name))
            if channel is None:
                channel = self.channels.get(channel_name)
            if channel is not None and conn.nick:
                key = casefold(conn.nick)
                channel.members.pop(key, None)
                channel.member_modes.pop(key, None)
                if not channel.members:
                    self.channels.pop(casefold(channel.name), None)
        conn.channels.clear()

    def send_to(self, nick: str, line: str) -> bool:
        """Send one line to the conn registered as `nick`.

        Returns True when the nick was found and the line handed to
        its transport, False when no such user is connected.
        """
        conn = self.connections.get(casefold(nick))
        if conn is None:
            return False
        conn.send(line)
        return True

    def broadcast_local(self, line: str) -> None:
        """Send one line to every registered connection on this server.

        MECHANISM: iterate a snapshot list -- a send must never
        observe the census dict changing size mid-loop.
        """
        for conn in list(self.connections.values()):
            conn.send(line)

    # -- the per-client read loop -----------------------------------

    async def _client_connected(self, reader, writer) -> None:
        peer = writer.get_extra_info("peername")
        host = peer[0] if peer else "127.0.0.1"
        conn = Conn(self, reader, writer, host)
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    # EOF: the peer went away. Normal, not an error.
                    break
                if len(raw) > MAX_RAW_LINE:
                    raw = raw[:TRUNCATED_LINE]
                line = raw.decode("utf-8", "replace").strip("\r\n")
                if not line.strip():
                    continue

                # THE parse: exactly once per line, here.
                msg = parse_line(line)
                command = msg.command
                if not command:
                    continue
                server_name = self.config["server_name"]
                target = conn.nick or "*"

                # Gate 1 -- fail closed on registration.
                if not conn.registered and command not in PRE_REGISTRATION_COMMANDS:
                    conn.send(
                        format_msg(
                            "451",
                            target,
                            command,
                            "You have not registered",
                            prefix=server_name,
                        )
                    )
                    continue

                # Gate 2 -- unknown commands answer 421.
                if not self.registry.knows(command):
                    conn.send(
                        format_msg(
                            "421",
                            target,
                            command,
                            "Unknown command",
                            prefix=server_name,
                        )
                    )
                    continue

                # Dispatch: hash lookup, handlers in registration
                # order. A raising handler is logged, never fatal.
                for handler in self.registry.handlers_for(command):
                    try:
                        await handler(self, conn, msg)
                    except Exception:
                        print(
                            f"[bleats-ircd] handler for {command} raised:",
                            file=sys.stderr,
                        )
                        traceback.print_exc()
        except (ConnectionResetError, BrokenPipeError):
            # A peer vanishing mid-read is the same as an EOF.
            pass
        finally:
            # Whatever happened, the census must not keep a ghost.
            self.remove_connection(conn)
            conn.close()


# 93 -- Live, Love, and let Love, Live.
