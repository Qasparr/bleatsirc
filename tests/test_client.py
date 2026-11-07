# 93
# ---------------------------------------------------------------------
# test_client.py -- the client weighed: core, bridge, isolation.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: stdlib unittest. A canned session is fed line by line to
# ClientCore; every Event is checked field by field against the wire
# line that bore it. The bridge is weighed with a StringIO outstream:
# what a script would read is exactly what is asserted.
# DOCTRINE: per-connection state never bleeds (the multiserver law),
# a malformed line degrades to 'raw' and never raises (the fallback
# floor), and subscription filtering is the script's own border --
# what it did not ask for, it does not receive.
# ---------------------------------------------------------------------

import io
import json
import unittest

from client.core import ClientCore
from client.bridge import Bridge


WELCOME = ":srv.example 001 me :Welcome to the house"
ISUPPORT = ":srv.example 005 me CHANTYPES=# PREFIX=(ov)@+ NICKLEN=30 :are supported"
JOIN_ME = ":me!u@h JOIN :#lobby"
NAMES = ":srv.example 353 me = #lobby :me @alice +bob"
PRIVMSG = ":alice!u@h PRIVMSG #lobby :hello herd"
MULTIKICK = ":carol!u@h KICK #lobby alice,bob :out you go"


class TestCoreSession(unittest.TestCase):
    def setUp(self):
        self.core = ClientCore()
        self.core.add_connection("net1")

    def test_welcome_001_fields_and_nick_state(self):
        ev = self.core.feed("net1", WELCOME)
        self.assertEqual(ev.connection_id, "net1")
        self.assertEqual(ev.kind, "numeric")
        self.assertEqual(ev.command, "001")
        self.assertEqual(ev.numeric, 1)
        self.assertEqual(ev.source, "srv.example")
        self.assertEqual(ev.target, "me")
        self.assertEqual(ev.text, "Welcome to the house")
        self.assertEqual(ev.raw, WELCOME)
        self.assertEqual(self.core.state("net1")["nick"], "me")

    def test_isupport_005_recorded_per_connection(self):
        self.core.feed("net1", WELCOME)
        ev = self.core.feed("net1", ISUPPORT)
        self.assertEqual(ev.numeric, 5)
        sup = self.core.state("net1")["isupport"]
        self.assertEqual(sup["CHANTYPES"], "#")
        self.assertEqual(sup["PREFIX"], "(ov)@+")
        self.assertEqual(sup["NICKLEN"], "30")

    def test_names_353_handler_fires_and_members_land(self):
        fired = []
        self.core.on_numeric(353, lambda ev: fired.append(ev))
        self.core.feed("net1", WELCOME)
        self.core.feed("net1", JOIN_ME)
        ev = self.core.feed("net1", NAMES)
        self.assertEqual(ev.numeric, 353)
        self.assertEqual(ev.target, "#lobby")
        self.assertEqual(len(fired), 1)
        self.assertIs(fired[0], ev)
        members = self.core.state("net1")["channels"]["#lobby"]
        # Prefixes (@, +) are ranks, not parts of nicks.
        self.assertEqual(members, {"me", "alice", "bob"})

    def test_privmsg_fields(self):
        self.core.feed("net1", WELCOME)
        ev = self.core.feed("net1", PRIVMSG)
        self.assertEqual(ev.kind, "command")
        self.assertEqual(ev.command, "PRIVMSG")
        self.assertIsNone(ev.numeric)
        self.assertEqual(ev.source, "alice")
        self.assertEqual(ev.target, "#lobby")
        self.assertEqual(ev.text, "hello herd")

    def test_multikick_one_line_removes_the_whole_list(self):
        self.core.feed("net1", WELCOME)
        self.core.feed("net1", JOIN_ME)
        self.core.feed("net1", NAMES)
        ev = self.core.feed("net1", MULTIKICK)
        self.assertEqual(ev.command, "KICK")
        self.assertEqual(ev.target, "#lobby")
        self.assertEqual(ev.params[1], "alice,bob")
        members = self.core.state("net1")["channels"]["#lobby"]
        self.assertEqual(members, {"me"})


class TestPerConnectionIsolation(unittest.TestCase):
    def test_same_nick_two_networks_no_bleed(self):
        core = ClientCore()
        core.add_connection("a")
        core.add_connection("b")
        core.feed("a", WELCOME)
        core.feed("b", WELCOME)
        core.feed("a", ":me!u@h JOIN :#one")
        core.feed("b", ":me!u@h JOIN :#two")
        chans_a = set(core.state("a")["channels"])
        chans_b = set(core.state("b")["channels"])
        self.assertEqual(chans_a, {"#one"})
        self.assertEqual(chans_b, {"#two"})
        # A names reply on B must not touch A's member lists.
        core.feed("b", ":srv.example 353 me = #two :me zed")
        self.assertEqual(core.state("b")["channels"]["#two"], {"me", "zed"})
        self.assertNotIn("#two", core.state("a")["channels"])


class TestMalformedLines(unittest.TestCase):
    def test_garbage_degrades_to_raw_without_raising(self):
        core = ClientCore()
        core.add_connection("net1")
        for junk in ("", "   ", ":", "::::", "\x00\x01"):
            ev = core.feed("net1", junk)
            self.assertEqual(ev.kind, "raw")
            self.assertEqual(ev.command, "")
            self.assertIsNone(ev.numeric)


class TestBridge(unittest.TestCase):
    def _make(self):
        core = ClientCore()
        core.add_connection("net1")
        out = io.StringIO()
        bridge = Bridge(core, io.StringIO(), out)
        return core, bridge, out

    def test_numeric_subscription_filters_out_privmsg(self):
        core, bridge, out = self._make()
        bridge.handle_line("SUBSCRIBE numeric:353")
        core.feed("net1", PRIVMSG)
        core.feed("net1", NAMES)
        lines = [ln for ln in out.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(obj["numeric"], 353)
        self.assertEqual(obj["command"], "353")
        self.assertEqual(obj["target"], "#lobby")
        self.assertEqual(obj["connection_id"], "net1")

    def test_default_subscription_passes_everything(self):
        core, bridge, out = self._make()
        core.feed("net1", PRIVMSG)
        core.feed("net1", WELCOME)
        lines = [ln for ln in out.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)

    def test_say_and_join_go_through_send_fn(self):
        sent = []
        core = ClientCore()
        core.add_connection("net1")
        bridge = Bridge(core, io.StringIO(), io.StringIO(),
                        send_fn=lambda cid, line: sent.append((cid, line)))
        bridge.handle_line("SAY net1 #lobby hello herd")
        bridge.handle_line("JOIN net1 #bleats")
        bridge.handle_line("RAW net1 MODE #lobby +o me")
        self.assertEqual(sent[0], ("net1", "PRIVMSG #lobby :hello herd"))
        self.assertEqual(sent[1], ("net1", "JOIN #bleats"))
        self.assertEqual(sent[2], ("net1", "MODE #lobby +o me"))


if __name__ == "__main__":
    unittest.main()

# 93 -- Live, Love, and let Love, Live.
