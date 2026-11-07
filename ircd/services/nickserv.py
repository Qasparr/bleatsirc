# 93
# ---------------------------------------------------------------------
# nickserv.py -- NickServ, the nick desk of the embedded services.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: NickServ is a pseudoclient, not a process. It owns no
# socket; the daemon routes PRIVMSG lines addressed to the nick
# "NickServ" into NickServ.handle(), and NickServ answers with
# NOTICE lines sent back along the sender's own connection. Its
# whole memory in this Phase 1 proof of concept is one in-process
# dict, {nick_lower: password}, created when REGISTER is spoken and
# consulted when IDENTIFY is spoken. A successful IDENTIFY marks
# the connection itself -- conn.state['identified'] = True -- never
# a global table, so one member's proof can never bleed onto
# another connection.
# DOCTRINE: a nick is a member's name in the house, and the registry
# is a house record kept under the Twin Synergy Telecommunications
# Constitution: the services keep only what registration itself
# requires -- a nick record the member created -- and nothing is
# kept to sort, score, or sell (THE LINE: private is private). The
# password road is the fallback road of the spec; the keypair road
# (SASL EXTERNAL) is reserved to a later phase and is not faked here.
# ---------------------------------------------------------------------

import inspect

from ..protocol import format_msg


async def _send(conn, line):
    """Send one line to a connection, awaiting the send if it awaits.

    MECHANISM: conn.send is a coroutine on the real daemon's Conn
    and a plain recording stub on test doubles; inspect.isawaitable
    lets one helper serve both without caring which it was handed.
    """
    result = conn.send(line)
    if inspect.isawaitable(result):
        await result


class NickServ:
    """The nick desk: REGISTER, IDENTIFY, GHOST, HELP.

    DOCTRINE: NickServ holds accounts, not people. The dict key is
    the lowercased nick because nick identity on this wire is
    case-insensitive in claim even where display case is preserved.
    """

    nick = "NickServ"

    def __init__(self):
        # MECHANISM: one dict, two names. .accounts is the canonical
        # store; .passwords is the same object under the name a test
        # or a sister service might reach for first. They must never
        # diverge, so they are bound to a single dict, not copied.
        self.accounts = {}
        self.passwords = self.accounts

    # -- wire plumbing -------------------------------------------------

    def _prefix(self, server):
        """This service's wire prefix: NickServ!services@<server>."""
        server_name = "bleats"
        config = getattr(server, "config", None)
        if isinstance(config, dict):
            server_name = config.get("server_name", server_name)
        return f"{self.nick}!services@{server_name}"

    async def _reply(self, server, conn, text):
        """Answer the sender with a NOTICE from the NickServ prefix."""
        line = format_msg("NOTICE", conn.nick, text,
                          prefix=self._prefix(server))
        await _send(conn, line)

    # -- the desk itself ----------------------------------------------

    async def handle(self, server, conn, msg):
        """Route one PRIVMSG addressed to NickServ.

        MECHANISM: msg.params is [target, text] for a service
        PRIVMSG, with the text riding as the trailing parameter
        (params[-1]). The first word of the text is the command,
        matched uppercase; the remaining words are its arguments.
        Passwords are single tokens by spec, so a plain split is
        honest -- no trailing-space preservation is needed or faked.
        """
        text = msg.trailing if msg.params else ""
        parts = text.split()
        if not parts:
            await self._reply(server, conn,
                              "No command given. Try: HELP")
            return
        command = parts[0].upper()
        args = parts[1:]

        if command == "HELP":
            await self._do_help(server, conn)
        elif command == "REGISTER":
            await self._do_register(server, conn, args)
        elif command == "IDENTIFY":
            await self._do_identify(server, conn, args)
        elif command == "GHOST":
            await self._do_ghost(server, conn, args)
        else:
            await self._reply(
                server, conn,
                f"Unknown command {command}. "
                "Try HELP for the commands NickServ knows.")

    async def _do_help(self, server, conn):
        """HELP: name every command, one NOTICE line apiece.

        DOCTRINE: a desk that cannot say what it does is a gate, not
        a service -- the help text is the desk's own transparency.
        """
        lines = [
            "NickServ commands:",
            "REGISTER <password> - register your current nick "
            "with a password",
            "IDENTIFY <password> - prove this nick is yours and "
            "sign this connection in",
            "GHOST <nick> <password> - disconnect a stale session "
            "using your nick",
            "HELP - show this help",
        ]
        for line in lines:
            await self._reply(server, conn, line)

    async def _do_register(self, server, conn, args):
        """REGISTER <password>: bind a password to the current nick."""
        if not getattr(conn, "nick", None):
            await self._reply(server, conn,
                              "You have no nick yet; set one first.")
            return
        if not args:
            await self._reply(server, conn,
                              "Usage: REGISTER <password>")
            return
        key = conn.nick.lower()
        if key in self.accounts:
            await self._reply(
                server, conn,
                f"The nick {conn.nick} is already registered.")
            return
        self.accounts[key] = args[0]
        await self._reply(
            server, conn,
            f"The nick {conn.nick} is now registered to you. "
            "Remember your password to IDENTIFY with it.")

    async def _do_identify(self, server, conn, args):
        """IDENTIFY <password>: prove the nick, mark the connection.

        MECHANISM: on success the mark lands on THIS connection's
        state dict -- conn.state['identified'] -- and HostServ is
        then given its turn, because the spec seats vhost delivery
        exactly here: on identify, the member's cloak replaces their
        raw host. On failure nothing is marked and nothing is
        revealed beyond the failure itself.
        """
        if not args:
            await self._reply(server, conn,
                              "Usage: IDENTIFY <password>")
            return
        key = (conn.nick or "").lower()
        stored = self.accounts.get(key)
        if stored is None or stored != args[0]:
            await self._reply(server, conn,
                              "Invalid password for this nick.")
            return
        conn.state["identified"] = True
        await self._reply(
            server, conn,
            f"Password accepted - you are now identified "
            f"as {conn.nick}.")
        # DOCTRINE: the vhost is delivered at the moment of proof,
        # not before it -- HostServ.apply is a no-op for a nick with
        # no stored vhost, so calling it unconditionally is safe.
        services = getattr(server, "services", None) or {}
        hostserv = services.get("hostserv")
        if hostserv is not None and hasattr(hostserv, "apply"):
            result = hostserv.apply(server, conn)
            if inspect.isawaitable(result):
                await result

    async def _do_ghost(self, server, conn, args):
        """GHOST <nick> <password>: reap a stale session on your nick.

        MECHANISM: the account password is the whole credential --
        whoever proves it owns the nick, and the older connection
        wearing that nick is told ERROR, closed if it exposes a
        close/disconnect, and lifted out of the server's connection
        table and channel member lists. The requester's own
        connection is never a valid target: you cannot ghost the
        session you are speaking from.
        """
        if len(args) < 2:
            await self._reply(server, conn,
                              "Usage: GHOST <nick> <password>")
            return
        target_nick, password = args[0], args[1]
        key = target_nick.lower()
        stored = self.accounts.get(key)
        if stored is None or stored != password:
            await self._reply(
                server, conn,
                "GHOST failed: invalid password for that nick.")
            return
        connections = getattr(server, "connections", None) or {}
        target = connections.get(key)
        if target is None or target is conn:
            await self._reply(
                server, conn,
                f"GHOST failed: {target_nick} is not connected "
                "as another session.")
            return
        # Tell the stale session why it is going, then close it by
        # whichever hand the connection object offers.
        try:
            await _send(target, format_msg(
                "ERROR", "Closing link: ghosted by the nick's owner"))
        except Exception:
            pass
        for closer_name in ("close", "disconnect"):
            closer = getattr(target, closer_name, None)
            if callable(closer):
                try:
                    result = closer()
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    pass
                break
        connections.pop(key, None)
        # Lift the ghost out of every channel member list it sat in,
        # tolerating member containers of any common shape.
        channels = getattr(server, "channels", None) or {}
        for chan_name in list(getattr(target, "channels", []) or []):
            channel = channels.get(chan_name)
            members = getattr(channel, "members", None)
            if members is None:
                continue
            try:
                if isinstance(members, dict):
                    members.pop(key, None)
                    members.pop(getattr(target, "nick", ""), None)
                elif isinstance(members, (set, list)):
                    for form in (target, getattr(target, "nick", None),
                                 key):
                        if form in members:
                            members.discard(form) if isinstance(
                                members, set) else members.remove(form)
            except Exception:
                pass
        try:
            target.channels.clear()
        except Exception:
            pass
        await self._reply(
            server, conn,
            f"GHOST succeeded: the stale session on {target_nick} "
            "has been disconnected.")


# 93 -- Live, Love, and let Love, Live.
