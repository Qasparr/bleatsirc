# 93
# ---------------------------------------------------------------------
# hostserv.py -- HostServ, the vhost desk of the embedded services.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: HostServ keeps one in-process dict, {nick_lower:
# vhost}. SET stores a member's chosen cloak; apply() is the act of
# wearing it -- conn.host is replaced by the stored vhost and the
# member is told so in a NOTICE. NickServ calls apply() the moment
# IDENTIFY succeeds, because the spec seats delivery exactly there:
# on identify, the member's cloak replaces their raw host.
# DOCTRINE: the vhost is the ghost-alias -- the name a member
# chooses to be seen under, in place of the raw host the wire would
# otherwise expose. Privacy toward the person is the house law
# (THE LINE), and the cloak is that law worn on the connection.
# The desk therefore refuses SET to any connection that has not
# identified: a cloak is granted on proof, never on assertion.
# ---------------------------------------------------------------------

import inspect
import re

from ..protocol import format_msg

# MECHANISM: a vhost is a hostname-shaped single token -- letters,
# digits, dots and hyphens, nothing else. Anything carrying spaces,
# slashes, or wire metacharacters is not a hostname and is refused
# at the desk rather than sanitised into something unasked-for.
_VHOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]*$")


async def _send(conn, line):
    """Send one line to a connection, awaiting the send if it awaits.

    MECHANISM: conn.send is a coroutine on the real daemon's Conn
    and a plain recording stub on test doubles; inspect.isawaitable
    lets one helper serve both without caring which it was handed.
    """
    result = conn.send(line)
    if inspect.isawaitable(result):
        await result


class HostServ:
    """The vhost desk: SET a cloak once identified; apply wears it."""

    nick = "HostServ"

    def __init__(self):
        # MECHANISM: the whole store of this Phase 1 desk -- which
        # nick claimed which cloak, keyed by lowercased nick so the
        # claim survives display-case changes on the wire.
        self.vhosts = {}

    # -- wire plumbing -------------------------------------------------

    def _prefix(self, server):
        """This service's wire prefix: HostServ!services@<server>."""
        server_name = "bleats"
        config = getattr(server, "config", None)
        if isinstance(config, dict):
            server_name = config.get("server_name", server_name)
        return f"{self.nick}!services@{server_name}"

    async def _reply(self, server, conn, text):
        """Answer the sender with a NOTICE from the HostServ prefix."""
        line = format_msg("NOTICE", conn.nick, text,
                          prefix=self._prefix(server))
        await _send(conn, line)

    # -- the act of wearing the cloak ----------------------------------

    async def apply(self, server, conn):
        """Put the stored vhost on this connection, if one is stored.

        MECHANISM: conn.host is the field every downstream prefix
        ('nick!user@host') is built from, so replacing it here is
        the whole act -- no channel re-join, no second announcement
        anywhere else. The member hears exactly one line:
        ':HostServ NOTICE <nick> :Your vhost <vhost> is now active'.
        Returns True when a vhost was applied, False when the nick
        has none stored (a normal state, never an error).
        """
        key = (getattr(conn, "nick", "") or "").lower()
        vhost = self.vhosts.get(key)
        if not vhost:
            return False
        conn.host = vhost
        line = format_msg("NOTICE", conn.nick,
                          f"Your vhost {vhost} is now active",
                          prefix=self.nick)
        await _send(conn, line)
        return True

    # -- the desk itself ----------------------------------------------

    async def handle(self, server, conn, msg):
        """Route one PRIVMSG addressed to HostServ.

        MECHANISM: as with every service here, msg.params is
        [target, text] and the text rides as params[-1]; its first
        word is the command, matched uppercase.
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
        elif command == "SET":
            await self._do_set(server, conn, args)
        else:
            await self._reply(
                server, conn,
                f"Unknown command {command}. "
                "Try HELP for the commands HostServ knows.")

    async def _do_help(self, server, conn):
        """HELP: name the desk's commands, one NOTICE line apiece."""
        lines = [
            "HostServ commands:",
            "SET <vhost> - set your virtual host (cloak); it "
            "activates now and on every future IDENTIFY",
            "HELP - show this help",
            "You must IDENTIFY with NickServ before SET will "
            "take a vhost.",
        ]
        for line in lines:
            await self._reply(server, conn, line)

    async def _do_set(self, server, conn, args):
        """SET <vhost>: claim a cloak -- identified connections only.

        DOCTRINE: the gate is the identification mark NickServ left
        on this very connection (conn.state['identified']). No mark,
        no cloak, and the refusal names the road in: identify first.
        """
        state = getattr(conn, "state", None) or {}
        if state.get("identified") is not True:
            await self._reply(
                server, conn,
                "You must identify first: /msg NickServ IDENTIFY "
                "<password> - then SET your vhost.")
            return
        if not args:
            await self._reply(server, conn,
                              "Usage: SET <vhost>")
            return
        vhost = args[0]
        if len(args) > 1 or not _VHOST_RE.match(vhost):
            await self._reply(
                server, conn,
                f"Invalid vhost {vhost}: a vhost is a single token "
                "of letters, digits, dots and hyphens.")
            return
        self.vhosts[conn.nick.lower()] = vhost
        # Wearing follows claiming in the same breath: apply() sets
        # conn.host and speaks the 'now active' NOTICE itself.
        await self.apply(server, conn)


# 93 -- Live, Love, and let Love, Live.
