# 93
# ---------------------------------------------------------------------
# test_services.py -- unit proof for the Group 2 services and oper
# surface: NickServ/HostServ identity and cloaks, the K-line store,
# the O-line gate, and the IRCopBot's ledger-before-act ordering.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: no sockets are opened. Small doubles stand in for the
# Group 1 server and connection objects, a line is parsed once by
# ircd.protocol.parse_line, and handlers/services are awaited
# directly. The tests therefore weigh the house rules themselves --
# identification state, vhost delivery, line expiry, failed OPER
# accounting, and record-before-act ordering -- rather than a
# transport that belongs to another group's proof.
# DOCTRINE: the sharpest assertion in this file is an ordering: for
# a bot-directed K-line, the ledger's entry must exist before the
# line store changes. The wire may name the bot, but the record
# names the directing oper first.
# ---------------------------------------------------------------------

import unittest

from ircd.handlers_oper import HANDLERS
from ircd.ledger import Ledger
from ircd.lines import Lines
from ircd.protocol import Registry, parse_line
from ircd.services import attach


class FakeConn:
    """A connection double with the coordinator's stated surface."""

    def __init__(self, nick, user=None, host="raw.example", *,
                 registered=True, is_oper=False, is_staff=False):
        self.nick = nick
        self.user = user or nick.lower()
        self.host = host
        self.registered = registered
        self.channels = set()
        self.modes = set()
        self.is_oper = is_oper
        self.is_staff = is_staff
        self.state = {}
        self.sent = []

    @property
    def prefix(self):
        # MECHANISM: the prefix is derived, never stored, so a vhost
        # applied to .host is visible in the very next prefix built.
        return f"{self.nick}!{self.user}@{self.host}"

    def send(self, line):
        self.sent.append(line)

    def sent_text(self):
        return "\n".join(self.sent)


class FakeChannel:
    """The channel fields Group 2 is allowed to touch."""

    def __init__(self, name):
        self.name = name
        self.members = {}
        self.member_modes = {}
        self.modes = set()
        self.topic = ""
        self.founder = None


class FakeServer:
    """A server double carrying exactly the shared build surface."""

    def __init__(self):
        self.registry = Registry()
        self.connections = {}
        self.channels = {}
        self.config = {
            "server_name": "irc.test",
            "olines": {"Qasparr": "proof-positive"},
        }
        self.services = {}
        self.broadcasts = []

    def add_conn(self, conn):
        self.connections[conn.nick.lower()] = conn
        return conn

    def send_to(self, nick, line):
        conn = self.connections.get(str(nick).lower())
        if conn is not None:
            conn.send(line)

    def broadcast_local(self, line):
        self.broadcasts.append(line)


async def dispatch_privmsg(server, conn, text_line):
    """Run the registered PRIVMSG chain as the daemon would."""
    msg = parse_line(text_line)
    for handler in server.registry.handlers_for("PRIVMSG"):
        await handler(server, conn, msg)


class OrderedLedger(Ledger):
    """A ledger spy that witnesses its place in the act's order."""

    def __init__(self, events):
        super().__init__()
        self.events = events

    def record(self, actor, act, target="", detail="", via=None):
        self.events.append(("ledger", act, target))
        return super().record(actor, act, target=target,
                               detail=detail, via=via)


class OrderedLines(Lines):
    """A line-store spy paired with OrderedLedger."""

    def __init__(self, events):
        super().__init__()
        self.events = events

    def add(self, mask, reason="", setter="", duration=None,
            expires=None, expires_ts=None, network=False):
        self.events.append(("store", mask))
        return super().add(mask, reason, setter, duration=duration,
                           expires=expires, expires_ts=expires_ts,
                           network=network)


class ServicesTests(unittest.IsolatedAsyncioTestCase):
    async def test_nickserv_register_identify_round_trip_applies_vhost(self):
        server = FakeServer()
        services = attach(server)
        self.assertEqual(
            set(services),
            {"nickserv", "chanserv", "hostserv", "operserv", "ircopbot"},
        )

        first = server.add_conn(FakeConn("Alice", host="first.example"))
        await dispatch_privmsg(
            server, first, "PRIVMSG NickServ :REGISTER proof-word")
        self.assertEqual(
            services["nickserv"].accounts, {"alice": "proof-word"})

        await dispatch_privmsg(
            server, first, "PRIVMSG NickServ :IDENTIFY proof-word")
        self.assertTrue(first.state["identified"])

        # The cloak is claimed on the identified connection and is
        # worn immediately; the round-trip below proves it is also
        # stored against the nick, not merely this one connection.
        await dispatch_privmsg(
            server, first, "PRIVMSG HostServ :SET cloak.example")
        self.assertEqual(first.host, "cloak.example")

        second = FakeConn("Alice", host="second.example")
        server.add_conn(second)
        await dispatch_privmsg(
            server, second, "PRIVMSG NickServ :IDENTIFY proof-word")
        self.assertTrue(second.state["identified"])
        self.assertEqual(second.host, "cloak.example")
        self.assertIn(
            "Your vhost cloak.example is now active", second.sent_text())

    async def test_ircopbot_kline_ledgers_before_store_and_drops(self):
        server = FakeServer()
        services = attach(server)
        bot = services["ircopbot"]

        events = []
        server.ledger = OrderedLedger(events)
        server.lines = OrderedLines(events)

        oper = server.add_conn(
            FakeConn("Qasparr", host="staff.example", is_oper=True))
        victim = server.add_conn(
            FakeConn("BadBot", user="bot", host="bad.example"))
        server.connections["badbot"] = victim

        await bot.handle(
            server, oper,
            parse_line("PRIVMSG IRCopBot :KLINE *@bad.example flood swarm"),
        )

        # The doctrinal ordering, witnessed by both spies: record,
        # then store. Disconnecting the matching user follows both.
        self.assertEqual(events[0], ("ledger", "KLINE", "*@bad.example"))
        self.assertEqual(events[1], ("store", "*@bad.example"))
        entries = server.ledger.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["actor"], "Qasparr")
        self.assertEqual(entries[0]["via"], "IRCopBot")
        self.assertTrue(server.lines.match("someone@bad.example"))
        self.assertNotIn("badbot", server.connections)
        self.assertIn("PRIVMSG Qasparr", oper.sent_text())
        self.assertIn("KLINE executed", oper.sent_text())
        self.assertIn("*@bad.example", oper.sent_text())

    async def test_oper_wrong_password_is_491_and_failed_attempt_ledgered(self):
        server = FakeServer()
        server.ledger = Ledger()
        server.lines = Lines()
        conn = server.add_conn(FakeConn("Qasparr", host="hopeful.example"))
        oper_handler = dict(HANDLERS)["OPER"]

        await oper_handler(
            server, conn, parse_line("OPER Qasparr wrong-password"))

        self.assertFalse(conn.is_oper)
        self.assertTrue(
            any(" 491 " in line for line in conn.sent),
            conn.sent_text(),
        )
        entries = server.ledger.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["act"], "OPER")
        self.assertEqual(entries[0]["target"], "Qasparr")
        self.assertEqual(entries[0]["detail"], "failed attempt")


class LinesTests(unittest.TestCase):
    def test_kline_store_matches_faces_and_purges_expired(self):
        lines = Lines()
        lines.add("*@bad.example", "flood", setter="Qasparr")
        self.assertTrue(lines.match("user@bad.example"))
        self.assertTrue(lines.match("Nick!user@bad.example"))
        self.assertFalse(lines.match("user@good.example"))

        # An absolute expiry in the past is dead on the next purge;
        # purging is the store's own act, not a caller's cleanup.
        lines.add("*@old.example", "temporary", setter="Qasparr",
                  expires=1)
        self.assertEqual(lines.purge_expired(), 1)
        self.assertIsNone(lines.get("*@old.example"))
        self.assertFalse(lines.match("user@old.example"))
        self.assertTrue(lines.remove("*@bad.example"))
        self.assertFalse(lines.match("user@bad.example"))


if __name__ == "__main__":
    unittest.main()


# 93 -- Live, Love, and let Love, Live.
