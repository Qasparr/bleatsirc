# CODING BRIEF — bleats-ircd + bleatsirc, Proof-of-Concept build

*Issued 2026-11-07 by the desk, on the founder's order: "Do it — a team
of 9 agents, 3 groups of 3." This brief is the shared contract. Read it
whole before writing a line. The specs it implements: docs/CUSTOM-IRCD-
SPEC.md and docs/BLEATSIRC-CLIENT-SPEC.md; the law it obeys: the Twin
Synergy Telecommunications Constitution (user above all; the only
capital crimes of the wire are DDoS and mass botting).*

## Phase and language

This is **Phase 1 — Prototyping the Proof of Concept**. Language:
**Python 3, standard library only** (asyncio for the daemon; the client
core is transport-free and synchronous). No third-party dependencies.
The production lineages (Bahamut/Unreal) are C; this POC proves the
architecture, the protocol behaviour, and the house law in the open,
and is marked as a prototype wherever it presents itself.

## The fixed contract (do not redesign; build to it)

`ircd/protocol.py` is already written by the desk and is law:

- `Message(prefix, command, params)` — `params[-1]` is the trailing
  parameter when present; `msg.trailing` returns it or `""`.
- `parse_line(line: str) -> Message` — the ONE parse of each line.
- `format_msg(command, *params, prefix=None) -> str` — trailing is
  automatic for the last param when it needs one.
- `Registry` — hash dispatch: `registry.on("PRIVMSG", handler)`;
  handlers are `async def h(conn, msg)`. Numeric commands register by
  their three-digit string. Unknown commands answer 421.

A **connection** object (`ircd/state.py`, Group 1 owns it) exposes at
minimum: `conn.send(line)`, `conn.nick`, `conn.user`, `conn.host`,
`conn.registered`, `conn.channels` (set of channel names),
`conn.modes` (set), `conn.is_oper`, `conn.state` (a per-connection
dict for ISUPPORT/353 bookkeeping — never shared across connections).

## Invariants (from the founder's rulings — test against them)

1. **Single parse, hash dispatch.** No if-chains over command names in
   handlers' callers; the registry is data.
2. **Per-connection state never bleeds** across servers or users.
3. **Services are embedded pseudoclients** living in the daemon
   process: NickServ, ChanServ, HostServ, OperServ, and the IRCopBot
   answer PRIVMSG at their nicks like users, with server-class power.
4. **The ledger is written BEFORE an oper act executes** (companion
   doctrine). Oper acts with no ledger entry do not happen.
5. **Staff immunity:** channel KICK/BAN/mode-strips against a user
   flagged oper/staff simply do not take effect (generic failure, no
   announcement of staff status — the incognito seam).
6. **Multi-kick:** `KICK #c u1,u2,u3 :reason` executes the whole comma
   list from one line, in order.
7. **Fail closed:** unregistered users get 451 for anything but the
   registration commands (PASS/NICK/USER/QUIT/PING).
8. **ISUPPORT (005) tells the truth** about what this build actually
   supports — CHANTYPES=#, PREFIX=(ov)@+, CHANMODES per what's
   implemented, TARGMAX as implemented, NICKLEN, CASEMAPPING=rfc1459.
9. The MOTD is `docs/bleats-motd.txt`'s text (375/372/376), trimmed if
   needed to the art + motto + rules core.

## File ownership (no group writes another group's files)

- **Group 1 — Daemon Core:** `ircd/__main__.py`, `ircd/server.py`,
  `ircd/state.py`, `ircd/handlers_core.py` (PASS/NICK/USER/QUIT/PING/
  PONG), `ircd/handlers_channel.py` (JOIN/PART/MODE/TOPIC/NAMES/KICK/
  INVITE), `ircd/handlers_msg.py` (PRIVMSG/NOTICE/AWAY),
  `tests/test_core.py`.
- **Group 2 — Services & Oper:** `ircd/services/__init__.py`,
  `ircd/services/nickserv.py`, `ircd/services/chanserv.py`,
  `ircd/services/hostserv.py`, `ircd/services/operserv.py`,
  `ircd/services/ircopbot.py`, `ircd/ledger.py`, `ircd/lines.py`
  (KLINE store), `ircd/handlers_oper.py` (OPER/KILL/KLINE/GLINE/WALLOPS),
  `tests/test_services.py`.
- **Group 3 — Client:** `client/__init__.py`, `client/core.py` (event
  parser: one parse → structured Event; numeric registry identical in
  spirit to the server's), `client/bridge.py` (the line-protocol
  bridge: JSON events out on stdout, commands in on stdin),
  `client/tui.py` (a curses front-end skeleton that renders server
  windows + input line, degrades gracefully without a tty),
  `tests/test_client.py`.

Groups 1 and 2 share the daemon process: `server.py` must import
`ircd.services` and `ircd.handlers_oper` **defensively** (try/except
ImportError) so the daemon runs with whichever parts have landed;
Group 2 registers its handlers and pseudoclients through the same
Registry and a `services.attach(server)` hook.

## Code convention (founder's standing order — no exceptions)

Every module opens with a comment/docstring header in the house
annotated convention: an epigraph line, the authorship line
(Johnathan 'Qasparr' Monroe, ARR), the date in words, Scientific
Illuminism named, and MECHANISM/DOCTRINE comments through the body
explaining *why*, not merely *what*. Bare uncommented code is not
shippable. Tests are plain `unittest` (stdlib), run with
`python3 -m unittest discover tests`.

## Definition of done (tonight)

`python3 -m ircd` listens on 127.0.0.1:6667. Two scripted clients
register (001–005 received), join #lobby, exchange a PRIVMSG, one
multi-kicks two test bots' nicks from one line; NickServ answers HELP
and REGISTER/IDENTIFY round-trips in memory; the IRCopBot takes a
directed KLINE from an oper and the ledger shows the entry; the client
core parses a recorded session and the bridge emits the same events as
JSON. All tests green; everything pushed.
