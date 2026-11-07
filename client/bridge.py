# 93
# ---------------------------------------------------------------------
# bridge.py -- the line-protocol bridge: a protocol, not an interpreter.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: the client core parses each server line ONCE into a
# structured Event (see client/core.py). This bridge is the second
# consumer of that single parse: it serialises each Event as one JSON
# object per line on its output stream, and it reads commands back,
# one per line, on its input stream. A script process therefore needs
# nothing but the ability to read a line and print a line -- Python,
# shell, Perl, Lua, JavaScript, Rust, a compiled binary, any tongue
# at all. Outbound IRC lines are built with format_msg from
# ircd/protocol.py, so client and daemon share ONE grammar for the
# house; the bridge never hand-assembles wire text of its own.
# DOCTRINE: the bridge is a protocol, not an interpreter (founder's
# dictation, BLEATSIRC-CLIENT-SPEC). No member is told their tongue
# is wrong; the bridge carries events and commands, and judges
# neither the language that speaks nor the script that is spoken.
# Scripts run as the member, with the member's permissions -- the
# bridge grants nothing its author could not type by hand.
# ---------------------------------------------------------------------

import json
import sys

# DOCTRINE: ONE grammar for the house. Every outbound line the bridge
# builds (PRIVMSG for SAY, JOIN for JOIN) goes through format_msg
# from ircd/protocol.py -- the same builder the daemon's side of the
# wire trusts -- so trailing-parameter handling can never drift
# between the client and the server.
from ircd.protocol import format_msg

# MECHANISM: the core is the single parse and the event registry.
# The bridge registers itself on it and feeds it; it never parses a
# server line itself. Event is imported as the named contract type
# handlers receive, even though this module works through attribute
# access on whatever Event the core hands it.
from client.core import ClientCore, Event


class Bridge:
    """Line-protocol bridge between ClientCore and a script process.

    MECHANISM: construction wires the bridge into the core at once --
    emit is registered as a '*' (catch-all) handler, so EVERY event
    the core produces flows to emit automatically, filtered there by
    the subscription list. The script side speaks four verbs inbound
    (SUBSCRIBE, RAW, SAY, JOIN) plus the FEED harness inlet, and
    receives two kinds of JSON lines outbound: event objects from
    emit, and {"type": "send", ...} notices from the default send
    path, which is how a host driving the bridge in-process learns
    what the script asked to put on the wire.
    """

    def __init__(self, core, instream, outstream, send_fn=None):
        # MECHANISM: the three collaborators are stored verbatim --
        # the core (event source and feed inlet), the input stream
        # the script writes to, and the output stream events are
        # written on. Nothing is opened or closed here; the bridge
        # owns no file descriptors, only the streams it was given.
        self.core = core
        self.instream = instream
        self.outstream = outstream
        # MECHANISM: send_fn is the wire-ward door. A real host
        # injects a function that writes the line to the named
        # connection's socket; when none is injected, the default
        # send reports the request as a JSON line on outstream, so
        # the bridge stays fully drivable (and testable) over stdio
        # alone, with no socket anywhere in the loop.
        self.send_fn = send_fn or self._default_send
        # MECHANISM: subscriptions starts EMPTY, and empty is a
        # meaning, not an absence: it is the default '*' behaviour
        # (see matches) -- a script that subscribes to nothing hears
        # everything until it says otherwise.
        self.subscriptions = []
        # MECHANISM: _subscribed_explicitly records whether any
        # SUBSCRIBE has ever arrived. The FIRST explicit subscription
        # REPLACES the empty default rather than appending to it;
        # later SUBSCRIBEs append. Without this flag, "empty" after a
        # first subscription could not be told from "empty" before
        # one, and the replace/append distinction would be guesswork.
        self._subscribed_explicitly = False
        # MECHANISM: registering emit as a '*' handler at
        # construction is the whole wiring. From this moment, every
        # event the core produces -- however it was fed, by a socket
        # in production or by FEED in a harness -- flows to emit
        # automatically; no caller has to remember to forward it.
        self.core.on('*', self.emit)

    # -- outbound: the default send door -----------------------------

    def _default_send(self, cid, line):
        """Report an outbound line as one JSON line on outstream.

        MECHANISM: writes {"type": "send", "connection_id": cid,
        "line": line} -- json.dumps plus a newline, then a flush, so
        a reading process sees the notice the moment it is made, not
        when some buffer happens to fill.
        """
        self.outstream.write(
            json.dumps(
                {"type": "send", "connection_id": cid, "line": line}
            )
            + "\n"
        )
        self.outstream.flush()

    def _write_event_json(self, obj):
        """Write one already-built JSON object as a single line.

        MECHANISM: json.dumps + "\n" + flush -- one object per line
        is the framing of the whole protocol; a script can frame its
        input with nothing more than a line reader, in any language.
        """
        self.outstream.write(json.dumps(obj) + "\n")
        self.outstream.flush()

    # -- subscription filtering --------------------------------------

    def matches(self, event) -> bool:
        """True when `event` passes the current subscriptions.

        MECHANISM: an empty subscription list matches everything --
        the default '*' behaviour. Otherwise ANY single pattern
        matching is enough (the list is a union, not a chain):
          '*'              matches every event;
          'numeric:<code>' matches event.numeric == int(code);
          'command:<NAME>' matches event.command == NAME.upper()
                           (the pattern's name is upper-cased, so a
                           script may write it in either case);
          'kind:<kind>'    matches event.kind.
        DOCTRINE: malformed patterns never match and never raise.
        A script's typo costs it silence on that pattern, never a
        crashed bridge -- the filter is read on every event, so an
        exception here would take down the whole stream for one bad
        word in one subscription.
        """
        if not self.subscriptions:
            return True
        for pattern in self.subscriptions:
            try:
                if pattern == '*':
                    return True
                if pattern.startswith('numeric:'):
                    # MECHANISM: int() is the only step that can
                    # raise (a non-numeric code); the try around the
                    # whole body turns that into "never matches".
                    if event.numeric == int(pattern[len('numeric:'):]):
                        return True
                elif pattern.startswith('command:'):
                    name = pattern[len('command:'):]
                    if name and event.command == name.upper():
                        return True
                elif pattern.startswith('kind:'):
                    if event.kind == pattern[len('kind:'):]:
                        return True
                # MECHANISM: any other shape -- no known prefix, an
                # empty remainder, plain garbage -- falls through
                # silently and simply does not match.
            except Exception:
                # DOCTRINE: malformed patterns never raise (see the
                # docstring). Swallow and try the next pattern.
                continue
        return False

    # -- outbound: events to the script ------------------------------

    def emit(self, event):
        """Serialise one Event as one JSON line, if subscribed.

        MECHANISM: the subscription filter runs first; a filtered-out
        event writes nothing at all. A passing event is written with
        keys exactly: connection_id, kind, command, numeric, source,
        target, text, params, raw -- the full Event, connection
        context first-class (the founder's multiserver ruling: every
        event carries which connection it belongs to, so one bridge
        can serve every network at once without ambiguity).
        """
        if not self.matches(event):
            return
        self._write_event_json(
            {
                "connection_id": event.connection_id,
                "kind": event.kind,
                "command": event.command,
                "numeric": event.numeric,
                "source": event.source,
                "target": event.target,
                "text": event.text,
                "params": event.params,
                "raw": event.raw,
            }
        )

    # -- inbound: commands from the script ---------------------------

    def handle_line(self, line):
        """Handle ONE script-side input line.

        MECHANISM: the trailing newline is stripped and empty lines
        are ignored. The first word selects the verb; the rest is
        split with bounded maxsplit so free-text tails (a SAY text, a
        RAW payload, a FEED server line) keep their internal spaces
        exactly as the script wrote them.
        DOCTRINE: unknown commands are ignored silently. A bridge
        must never crash on a script's bad line -- it is a protocol
        boundary, and the failure mode of a protocol boundary for
        garbage input is to drop the garbage, not to fall over and
        take every well-behaved script down with it. Lines too short
        for their verb are dropped the same way.
        """
        line = line.rstrip("\r\n")
        if not line.strip():
            return
        verb = line.split(None, 1)[0].upper()

        if verb == 'SUBSCRIBE':
            parts = line.split()
            if len(parts) < 2:
                return
            pattern = parts[1]
            if not self._subscribed_explicitly:
                # MECHANISM: the first explicit subscription REPLACES
                # the empty default (see __init__): the script has
                # said what it wants, so the hear-everything default
                # ends here rather than silently staying in force.
                self.subscriptions = [pattern]
                self._subscribed_explicitly = True
            else:
                # MECHANISM: later SUBSCRIBEs accumulate -- each one
                # widens the union matches() consults.
                self.subscriptions.append(pattern)
            return

        if verb == 'RAW':
            # MECHANISM: split(None, 2) yields verb, cid, and the
            # remainder untouched after the cid token -- the raw line
            # verbatim, internal spaces unstripped, because RAW means
            # the script takes responsibility for the wire text.
            parts = line.split(None, 2)
            if len(parts) < 3:
                return
            self.send_fn(parts[1], parts[2])
            return

        if verb == 'SAY':
            # MECHANISM: split(None, 3) yields verb, cid, channel,
            # and the whole text tail as one parameter. The line is
            # built by format_msg -- ONE grammar for the house -- so
            # a text with spaces is trailed exactly as the daemon
            # would build it.
            parts = line.split(None, 3)
            if len(parts) < 4:
                return
            self.send_fn(parts[1], format_msg('PRIVMSG', parts[2], parts[3]))
            return

        if verb == 'JOIN':
            parts = line.split()
            if len(parts) < 3:
                return
            self.send_fn(parts[1], format_msg('JOIN', parts[2]))
            return

        if verb == 'FEED':
            # MECHANISM: FEED is the POC harness inlet. It lets tests
            # and shell pipelines drive INBOUND server traffic through
            # the same stdin the script verbs arrive on: the raw
            # server line is handed to core.feed, the core parses it
            # once into an Event, and -- because emit was registered
            # as a '*' handler at construction -- the resulting event
            # flows back out through emit automatically. One door in,
            # one door out; the harness needs no second channel and
            # exercises exactly the production event path.
            parts = line.split(None, 2)
            if len(parts) < 3:
                return
            self.core.feed(parts[1], parts[2])
            return

        # DOCTRINE: unknown verb -- ignore silently (see docstring).
        return

    # -- the loop ------------------------------------------------------

    def run(self):
        """Consume instream line by line until EOF, then return.

        MECHANISM: a plain for-loop over the stream; handle_line does
        all the work per line and EOF simply ends the loop. There is
        no farewell handshake in the protocol -- a script closing its
        side of the pipe IS the goodbye.
        """
        for line in self.instream:
            self.handle_line(line)
        return


def main():
    """Run the bridge on stdio: `python3 -m client.bridge`.

    MECHANISM: build a bare ClientCore and a Bridge bound to
    sys.stdin / sys.stdout, then run to EOF and report success.
    Connection management belongs to the host client; this entry
    point exists so the protocol itself can be driven -- and
    smoke-tested -- from any shell pipeline.
    """
    core = ClientCore()
    bridge = Bridge(core, sys.stdin, sys.stdout)
    bridge.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 93 -- Live, Love, and let Love, Live.
