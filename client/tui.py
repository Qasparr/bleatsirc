# 93
# ---------------------------------------------------------------------
# tui.py -- bleatsirc's terminal face: a curses skeleton that RUNS.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: this module is a FRONT-END SKELETON, not a finished UI.
# It owns no sockets and parses no wire lines itself. The ClientCore
# (client/core.py) parses each inbound line ONCE into an Event; this
# module registers one '*' handler on the core (note_event) and routes
# every Event into a per-(connection, target) text buffer. Rendering
# is split in two: render_lines()/nicklist() are PURE functions of the
# current buffer state (so tests can assert on them without a tty),
# and a thin curses layer merely draws what they return. Outbound
# lines leave through an injected send_fn(cid, line); the POC default
# drops sends, and tests inject a recording one.
# DOCTRINE: multiserver is the point, not a feature bolted on later --
# windows span ALL connections, and Ctrl-N/Ctrl-P walk the whole
# window list across networks, because the member holds every network
# in one hand. Dumb mode (no tty) degrades honestly instead of
# crashing: it doubles as a test harness, documented below.
# ---------------------------------------------------------------------

import sys

# MECHANISM: outbound lines are built by the ONE formatter the whole
# house shares (ircd/protocol.py), so the client never hand-rolls wire
# grammar that could drift from the daemon's.
from ircd.protocol import format_msg

# DOCTRINE: the dependency contract with client/core.py is fixed by
# the desk and coded against exactly -- ClientCore parses, TuiApp
# displays; neither reaches into the other's work.
from client.core import ClientCore

# MECHANISM: commands whose target may be a channel, and therefore
# route to a channel window instead of the status window.
_CHANNEL_COMMANDS = ("PRIVMSG", "NOTICE", "JOIN", "PART", "KICK", "TOPIC")

# MECHANISM: per-buffer scrollback cap -- a POC client on a phone
# terminal must not grow without bound on a busy channel.
_BUFFER_CAP = 500

# MECHANISM: width of the nicklist column the curses layer reserves.
_NICKLIST_WIDTH = 18


class TuiApp:
    """The curses front-end skeleton: buffers, routing, rendering.

    core:    a ClientCore; this app registers note_event on it.
    send_fn: callable(cid, line) receiving outbound raw lines. When
             None, sends are dropped (POC default) -- the display side
             still runs, which is what the skeleton exists to prove.
    """

    def __init__(self, core, send_fn=None):
        # MECHANISM: state is (connection_id, target) -> list of
        # display strings. 'status' is the target of each connection's
        # server window; channel targets keep their '#'/'&' sigil.
        self.core = core
        self.send_fn = send_fn or (lambda cid, line: None)
        self.windows: dict = {}
        self.window_order: list = []
        self.active_index: int = 0
        # MECHANISM: one '*' registration receives every Event the
        # core parses -- the UI consumes the same single parse the
        # trigger engine and the bridge do; nothing re-parses here.
        self.core.on("*", self.note_event)

    # -- window bookkeeping -------------------------------------------

    def _ensure_window(self, key):
        """Create key's buffer on first use; first window is active."""
        if key not in self.windows:
            first = not self.window_order
            self.windows[key] = []
            self.window_order.append(key)
            if first:
                # DOCTRINE: the member lands looking at the first
                # window that exists, never at a void.
                self.active_index = 0
        return self.windows[key]

    def _append(self, key, line):
        """Append a display line, capping the buffer at _BUFFER_CAP."""
        buf = self._ensure_window(key)
        buf.append(line)
        # MECHANISM: drop the oldest lines past the cap, in place, so
        # holders of the list (render_lines callers) see the trim.
        while len(buf) > _BUFFER_CAP:
            del buf[0]

    def _window_key(self, event):
        """Route an Event to its (connection_id, target) window key.

        MECHANISM: channel traffic (target starting '#' or '&') goes
        to that channel's window on ITS connection; everything else --
        numerics, server notices, private messages -- goes to that
        connection's status window. Per-connection keys are what keep
        one network's state from bleeding into another's display.
        """
        cid = event.connection_id
        command = (event.command or "").upper()
        target = event.target or ""
        if command in _CHANNEL_COMMANDS and target[:1] in ("#", "&"):
            return (cid, target)
        return (cid, "status")

    @staticmethod
    def _display(event):
        """Format one Event as its display string.

        MECHANISM: the classic mIRC shapes -- <nick> for speech,
        -nick- for notice, arrows for join/part -- so a member reads
        the buffer by shape before reading words. Numerics and
        anything unrecognised show the raw line: the raw-protocol
        view is the fallback floor, never nothing (house doctrine).
        """
        command = (event.command or "").upper()
        if command == "PRIVMSG":
            return f"<{event.source}> {event.text}"
        if command == "NOTICE":
            return f"-{event.source}- {event.text}"
        if command == "JOIN":
            return f"--> {event.source} joined {event.target}"
        if command == "PART":
            return f"<-- {event.source} left {event.target}"
        if command == "KICK":
            # MECHANISM: KICK's victim is params[1] (params[0] is the
            # channel); guard a short param list instead of crashing
            # the whole UI on one malformed line.
            params = event.params or []
            victim = params[1] if len(params) > 1 else "?"
            return f"--- {victim} kicked from {event.target}: {event.text}"
        if event.numeric is not None:
            return event.raw
        return event.raw

    # -- the core's '*' handler ----------------------------------------

    def note_event(self, event):
        """Route one parsed Event into its window buffer."""
        self._append(self._window_key(event), self._display(event))

    # -- navigation ------------------------------------------------------

    def active_key(self):
        """The active window's (connection_id, target) key, or None."""
        if not self.window_order:
            return None
        return self.window_order[self.active_index]

    def cycle(self, delta):
        """Move the active window by delta, wrapping modulo the count.

        DOCTRINE: the walk spans ALL connections' windows in creation
        order (Ctrl-N = +1, Ctrl-P = -1 in the curses layer) -- that
        cross-network walk IS the multiserver point: one keystroke
        takes the member from #lobby on the house network to a status
        window on any other, with no server-switching ceremony.
        """
        if not self.window_order:
            return
        self.active_index = (self.active_index + delta) % len(self.window_order)

    # -- user input ------------------------------------------------------

    def handle_input(self, text):
        """Act on one line of user input for the ACTIVE window.

        MECHANISM: '/...' is a raw escape -- the remainder goes to the
        wire verbatim through send_fn. Plain text in a channel window
        becomes a PRIVMSG (built by format_msg) plus a local echo of
        the member's own line. Plain text in a status window has
        nowhere honest to go, so it earns a local note, not a crash
        and not a silent swallow -- POC honesty.
        """
        if not text:
            return
        key = self.active_key()
        if key is None:
            return
        cid, target = key
        if text.startswith("/"):
            raw = text[1:]
            if raw:
                self.send_fn(cid, raw)
            return
        if target[:1] in ("#", "&"):
            self.send_fn(cid, format_msg("PRIVMSG", target, text))
            # MECHANISM: echo our own line locally -- the server may
            # or may not echo it back depending on echo-message, and
            # the member must see what they said either way.
            try:
                mynick = self.core.state(cid).get("nick") or "?"
            except Exception:
                mynick = "?"
            self._append(key, f"<{mynick}> {text}")
            return
        # Status window, plain text: nowhere to send it.
        self._append(key, "--- nowhere to send: use /RAW or join a channel")

    # -- pure rendering (shared by curses and tests) ---------------------

    def nicklist(self):
        """Sorted member nicks for the active channel window.

        MECHANISM: read straight from the core's per-connection state
        (built from JOIN/NAMES numerics by the core, never by the UI).
        Status windows have no nicklist: [].
        """
        key = self.active_key()
        if key is None:
            return []
        cid, target = key
        if target[:1] not in ("#", "&"):
            return []
        try:
            channels = self.core.state(cid).get("channels", {})
        except Exception:
            return []
        return sorted(channels.get(target, ()))

    def render_lines(self, width=80):
        """Return the display lines for the active window.

        MECHANISM: a PURE function of current state -- line 0 is the
        status line naming connection, own nick, window, and position
        in the window walk; the rest are the active buffer's lines,
        ALL of them (deciding how many fit the screen is the curses
        layer's problem, not this function's). `width` is accepted
        for the curses layer's convenience; the status line's format
        is fixed by spec and not truncated here.
        """
        key = self.active_key()
        if key is None:
            return [" bleatsirc [] nick=? window=status (0/0) "]
        cid, target = key
        try:
            nick = self.core.state(cid).get("nick") or "?"
        except Exception:
            nick = "?"
        n = len(self.window_order)
        status = (
            f" bleatsirc [{cid}] nick={nick} window={target} "
            f"({self.active_index + 1}/{n}) "
        )
        return [status] + list(self.windows.get(key, []))

    # -- curses layer ------------------------------------------------------

    def run(self):
        """Run in curses when a real tty exists, else in dumb mode.

        MECHANISM: the Termux/SSH/telnet road means the client is
        often attached through pipes and scripts where curses cannot
        live; degrading to run_dumb keeps the session usable instead
        of dying on an import or a non-tty stream.
        """
        try:
            import curses
        except ImportError:
            self.run_dumb(sys.stdin, sys.stdout)
            return
        if sys.stdout.isatty() and sys.stdin.isatty():
            curses.wrapper(self._curses_main)
        else:
            self.run_dumb(sys.stdin, sys.stdout)

    def _curses_main(self, stdscr):
        """The curses draw/key loop -- compact skeleton, by design.

        MECHANISM: draw status at row 0, the tail of the active
        buffer in rows 1..h-3, the nicklist (channel windows only) in
        a right column, and the input line at row h-1; then one getch
        per iteration, refreshing after each key. Keys: Ctrl-N/Ctrl-P
        cycle windows, Enter submits, Backspace edits, Esc exits,
        printable ASCII appends to the input buffer.
        """
        import curses  # noqa: F401 -- presence proven by run()

        stdscr.keypad(True)
        input_buf = ""
        while True:
            height, width = stdscr.getmaxyx()
            if height < 3 or width < 10:
                # MECHANISM: too small to draw honestly; wait for a
                # resize instead of painting over ourselves.
                stdscr.getch()
                continue
            key = self.active_key()
            is_channel = bool(key) and key[1][:1] in ("#", "&")
            stdscr.erase()
            lines = self.render_lines(width=width)
            self._draw(stdscr, 0, 0, lines[0] if lines else "", width)
            buf = self.windows.get(key, []) if key else []
            body_rows = height - 3
            text_width = width - _NICKLIST_WIDTH - 1 if is_channel else width
            for row, line in enumerate(buf[-body_rows:] if body_rows else [], start=1):
                self._draw(stdscr, row, 0, line, max(text_width, 1))
            if is_channel:
                col = width - _NICKLIST_WIDTH
                for row, nick in enumerate(self.nicklist(), start=1):
                    if row > body_rows:
                        break
                    self._draw(stdscr, row, col, nick, _NICKLIST_WIDTH - 1)
            self._draw(stdscr, height - 1, 0, "> " + input_buf, width)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == 27:  # Esc -- leave.
                return
            if ch == 14:  # Ctrl-N -- next window (any connection).
                self.cycle(+1)
            elif ch == 16:  # Ctrl-P -- previous window.
                self.cycle(-1)
            elif ch in (10, 13):  # Enter -- submit the input line.
                self.handle_input(input_buf)
                input_buf = ""
            elif ch in (127, 263, 8):  # Backspace variants by terminal.
                input_buf = input_buf[:-1]
            elif 32 <= ch < 127:  # Printable ASCII.
                input_buf += chr(ch)
            # MECHANISM: every other key (arrows, function keys, a
            # resize sentinel) is ignored by the skeleton; the loop
            # redraws from current state regardless.

    @staticmethod
    def _draw(stdscr, row, col, text, width):
        """addnstr with the curses edge-errors swallowed.

        MECHANISM: writing the bottom-right cell or past a shrunken
        edge raises curses.error mid-draw; one bad cell must not kill
        the session, so drawing failures are contained here.
        """
        if width <= 0:
            return
        try:
            stdscr.addnstr(row, col, text, width)
        except Exception:
            pass

    # -- dumb mode ---------------------------------------------------------

    def run_dumb(self, instream, outstream):
        """Line-mode operation when there is no tty.

        MECHANISM: print a header, auto-open connection 'net1', then
        per input line: a line starting '/' is user input (routed to
        handle_input); EVERY other line is treated as an inbound
        server line for 'net1', fed to the core, and the display line
        it routed to is printed as "[cid] display".
        DOCTRINE: dumb mode doubles as a test harness -- scripted
        lines in, formatted lines out -- so the POC's client behaviour
        is checkable on any pipe. On a real shell the socket layer
        will feed the core instead; this harness stands in for it,
        honestly labelled.
        """
        print("bleatsirc (dumb mode — no tty)", file=outstream)
        # MECHANISM: the harness has exactly one canned connection;
        # add_connection is idempotent in the core's contract use.
        try:
            self.core.add_connection("net1")
        except Exception:
            pass
        for line in instream:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("/"):
                self.handle_input(line.strip())
                continue
            ev = self.core.feed("net1", line)
            buf = self.windows.get(self._window_key(ev), [])
            display = buf[-1] if buf else ev.raw
            print(f"[{ev.connection_id}] {display}", file=outstream)


def main(argv=None):
    """Entry point: --selftest proves the skeleton; else run the app."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        # MECHANISM: canned session against a recording send_fn --
        # welcome numeric to status, own JOIN opens #lobby, alice's
        # PRIVMSG lands in it formatted. Assertions are shape-tolerant
        # (source may render as nick or nick!user@host).
        sent = []
        core = ClientCore()
        app = TuiApp(core, send_fn=lambda cid, line: sent.append((cid, line)))
        core.add_connection("net1")
        core.feed("net1", ":srv 001 me :Welcome to the house")
        core.feed("net1", ":me!u@h JOIN :#lobby")
        core.feed("net1", ":alice!u@h PRIVMSG #lobby :hello herd")
        assert ("net1", "#lobby") in app.windows, "no #lobby window created"
        lobby = app.windows[("net1", "#lobby")]
        assert any(
            "alice" in line and "hello herd" in line for line in lobby
        ), f"alice line missing from #lobby buffer: {lobby!r}"
        print("selftest ok")
        return 0
    # MECHANISM: the plain road -- a core, an app, and run(), which
    # itself chooses curses or dumb mode by the tty it finds.
    core = ClientCore()
    app = TuiApp(core)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 93 -- Live, Love, and let Love, Live.
