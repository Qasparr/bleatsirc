# 93
# ---------------------------------------------------------------------
# test_core.py -- the daemon proven against REAL sockets.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: no mocks of the wire. Each test class run starts the
# real Server in a background thread on its own asyncio loop,
# bound to a fixed uncommon localhost port, and the tests speak
# raw IRC over real TCP sockets -- registration burst, the 451
# fail-closed gate, JOIN + PRIVMSG relay, the multi-kick comma
# list, and staff immunity are all observed as lines on the wire,
# exactly as a user's client would observe them.
# DOCTRINE: a claim about the protocol is only as good as the
# socket it was proven on. Positive expects get generous timeouts
# (5s); negative expects (a line that must NOT arrive) use short
# windows (0.5-0.8s), so the suite stays fast without going flaky.
# ---------------------------------------------------------------------

import asyncio
import itertools
import select
import socket
import threading
import time
import unittest
from collections import deque

from ircd.server import Server
from ircd.state import casefold

HOST = "127.0.0.1"
PORT = 17667


class WireClient:
    """A minimal blocking IRC client over a real socket.

    MECHANISM: received bytes accumulate in a buffer and are split
    into CRLF-stripped lines in a queue, so read_until() first scans
    lines already received before waiting for more -- a fast burst
    from the server can never be "missed" between two expects.
    """

    def __init__(self, host=HOST, port=PORT):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.setblocking(False)
        self._buffer = b""
        self._lines = deque()
        self.nick = None
        self.registration_lines = []
        self.seen = []  # every line consumed by expects, for debugging

    # -- transport --------------------------------------------------

    def send_line(self, line):
        self.sock.sendall((line + "\r\n").encode("utf-8", "replace"))

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    # -- reading ------------------------------------------------------

    def _pump(self, timeout):
        """Wait up to `timeout` for bytes; split any into lines."""
        if timeout <= 0:
            return
        ready, _, _ = select.select([self.sock], [], [], timeout)
        if not ready:
            return
        try:
            chunk = self.sock.recv(65536)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            chunk = b""
        if chunk:
            self._buffer += chunk
            while b"\n" in self._buffer:
                raw, self._buffer = self._buffer.split(b"\n", 1)
                self._lines.append(raw.rstrip(b"\r").decode("utf-8", "replace"))

    def read_until(self, predicate, timeout=5.0):
        """Return the first line matching predicate, or None.

        Lines scanned and not matched are consumed (they are kept
        in self.seen for debugging a failed expect).
        """
        deadline = time.monotonic() + timeout
        while True:
            while self._lines:
                line = self._lines.popleft()
                self.seen.append(line)
                if predicate(line):
                    return line
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self._pump(min(remaining, 0.25))

    def collect_for(self, duration):
        """Collect every line that arrives within `duration` seconds."""
        deadline = time.monotonic() + duration
        collected = []
        while True:
            while self._lines:
                line = self._lines.popleft()
                self.seen.append(line)
                collected.append(line)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return collected
            self._pump(min(remaining, 0.1))

    def drain(self, duration=0.4):
        """Discard a burst (e.g. NAMES after JOIN) so the next
        expect starts from a clean wire."""
        self.collect_for(duration)


class CoreServerTests(unittest.TestCase):
    """End-to-end tests against one Server shared by the class.

    MECHANISM: the Server runs its own asyncio loop in a daemon
    thread (setUpClass); tests run on the main thread over sockets.
    Channels empty out when their last member disconnects, and
    every test uses fresh unique nicks, so tests stay independent
    on the shared daemon.
    """

    _nick_counter = itertools.count(1)

    # -- server lifecycle --------------------------------------------

    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        cls.server = Server()
        cls.thread = threading.Thread(
            target=cls.loop.run_forever, name="bleats-test-loop", daemon=True
        )
        cls.thread.start()
        cls.start_future = asyncio.run_coroutine_threadsafe(
            cls.server.start(HOST, PORT), cls.loop
        )
        # Wait until the port actually accepts (bounded, generous).
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                probe = socket.create_connection((HOST, PORT), timeout=0.5)
            except OSError:
                time.sleep(0.05)
                continue
            probe.close()
            break
        else:  # pragma: no cover - environment failure, not a test
            raise RuntimeError("bleats-ircd test server did not start")
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        try:
            fut = asyncio.run_coroutine_threadsafe(cls.server.close(), cls.loop)
            fut.result(timeout=2)
        except Exception:
            pass
        cls.start_future.cancel()
        cls.loop.call_soon_threadsafe(cls.loop.stop)
        cls.thread.join(timeout=2)

    # -- per-test client bookkeeping -----------------------------------

    def setUp(self):
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.clients = []
        # Give the daemon a beat to reap the disconnected conns so
        # channels empty and nicks free before the next test.
        time.sleep(0.2)

    # -- helpers --------------------------------------------------------

    def _unique_nick(self, base):
        return f"{base}{next(self._nick_counter)}"

    def connect(self):
        client = WireClient()
        self.clients.append(client)
        return client

    def register_client(self, base):
        """Connect and complete NICK/USER, waiting for 376.

        Returns the client; every line of the registration burst is
        kept on client.registration_lines for burst assertions.
        """
        nick = self._unique_nick(base)
        client = self.connect()
        client.nick = nick
        client.send_line(f"NICK {nick}")
        client.send_line(f"USER {nick} 0 * :{nick} Realname")
        end = client.read_until(lambda l: " 376 " in l, timeout=5.0)
        self.assertIsNotNone(end, f"no 376 end-of-MOTD for {nick}: {client.seen}")
        client.registration_lines = list(client.seen)
        client.seen = []
        return client

    def join_channel(self, client, channel="#lobby"):
        """JOIN and wait for the client's own JOIN echo, then drain
        the trailing burst (topic / NAMES / 366) if one is sent."""
        client.send_line(f"JOIN {channel}")
        echo = client.read_until(
            lambda l: " JOIN " in l and channel in l, timeout=5.0
        )
        self.assertIsNotNone(
            echo, f"{client.nick} got no JOIN echo for {channel}: {client.seen}"
        )
        client.drain(0.3)
        return echo

    # -- the tests -------------------------------------------------------

    def test_registration_burst(self):
        """001 and a truthful 005 (CHANTYPES, TARGMAX) are delivered."""
        client = self.register_client("Reg")
        lines = client.registration_lines
        self.assertTrue(
            any(" 001 " in l for l in lines), f"no 001 in burst: {lines}"
        )
        isupport = " ".join(l for l in lines if " 005 " in l)
        self.assertTrue(isupport, f"no 005 in burst: {lines}")
        self.assertIn("CHANTYPES=#", isupport)
        self.assertIn("TARGMAX=KICK:4", isupport)

    def test_451_before_registration(self):
        """An unregistered JOIN is refused 451 -- fail closed."""
        client = self.connect()
        client.send_line("JOIN #lobby")
        line = client.read_until(lambda l: " 451 " in l, timeout=5.0)
        self.assertIsNotNone(line, f"no 451 for pre-registration JOIN: {client.seen}")

    def test_join_and_privmsg(self):
        """A's PRIVMSG to #lobby reaches B, bearing A's prefix."""
        a = self.register_client("Alice")
        b = self.register_client("Bob")
        self.join_channel(a)
        self.join_channel(b)
        a.drain(0.3)  # B's JOIN echo as seen by A, plus any burst

        a.send_line("PRIVMSG #lobby :hello herd")
        line = b.read_until(
            lambda l: "PRIVMSG #lobby" in l and "hello herd" in l, timeout=5.0
        )
        self.assertIsNotNone(line, f"B never received A's message: {b.seen}")
        self.assertTrue(
            line.startswith(f":{a.nick}!"),
            f"message lacks A's nick!user@host prefix: {line}",
        )

    def test_multi_kick(self):
        """One KICK line with a comma list removes C and D."""
        a = self.register_client("OpA")
        b = self.register_client("Bee")
        c = self.register_client("Cee")
        d = self.register_client("Dee")
        self.join_channel(a)  # A creates #lobby: founder/op
        self.join_channel(b)
        self.join_channel(c)
        self.join_channel(d)
        a.drain(0.3)

        a.send_line(f"KICK #lobby {c.nick},{d.nick} :wave")
        c_kick = c.read_until(
            lambda l: "KICK" in l and "#lobby" in l and c.nick in l, timeout=5.0
        )
        d_kick = d.read_until(
            lambda l: "KICK" in l and "#lobby" in l and d.nick in l, timeout=5.0
        )
        self.assertIsNotNone(c_kick, f"C got no KICK line: {c.seen}")
        self.assertIsNotNone(d_kick, f"D got no KICK line: {d.seen}")

        # Sanity: a kick is a removal, not a ban -- C can rejoin.
        self.join_channel(c)

    def test_staff_immunity(self):
        """KICK against an oper-flagged user does not take effect."""
        a = self.register_client("OpB")
        b = self.register_client("Staff")
        self.join_channel(a)
        self.join_channel(b)
        a.drain(0.3)

        # Flip the flag server-side, on the live Conn object. (The
        # GIL makes this direct attribute set safe enough for a
        # smoke test; production would flip it via OPER.)
        conn_b = self.server.connections[casefold(b.nick)]
        conn_b.is_oper = True

        a.send_line(f"KICK #lobby {b.nick} :try")
        heard = b.collect_for(0.6)
        self.assertFalse(
            any("KICK" in l and b.nick in l for l in heard),
            f"staff user received a KICK despite immunity: {heard}",
        )

        # Proof B is still in the channel: its PRIVMSG reaches A.
        b.send_line("PRIVMSG #lobby :still here")
        line = a.read_until(
            lambda l: "PRIVMSG #lobby" in l and "still here" in l, timeout=5.0
        )
        self.assertIsNotNone(line, f"A never received staff user's message: {a.seen}")


if __name__ == "__main__":
    unittest.main()


# 93 -- Live, Love, and let Love, Live.
