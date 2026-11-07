# bleatsirc — The House Client Specification

**Dictated:** Saturday, November 7, 2026 (America/Detroit)
**Authorship:** Johnathan 'Qasparr' Monroe, ARR — All Rights Reserved, Without Prejudice
**Status:** Design specification, founder's dictation.
**Lineage:** This continues the BleatIRC line he founded in October 2026
(mIRC-like client; plugins; event triggers; DCC; a multilingual,
adapter-based scripting engine — his order of 2026-10-01). Today's
dictation rules the access model and sharpens the scripting demand. The
old repo `Qasparr/BleatIRC.` stands as it stands; the project name as he
now gives it is **bleatsirc**.

## What it is

**bleatsirc is the client, not the ircd.** The daemon is `bleats-ircd`
(see `CUSTOM-IRCD-SPEC.md`); bleatsirc is what a member holds in their
hand to reach it — and to reach every other network, too.

## Access: CLI, SSH, telnet — the Termux road

His dictation: "make it accessible from cli and ssh telnet so we can log
in right from our termux screen and it'll connect and configure the ui
in termux for the irc session."

- The client runs on the member's shell (and on their own machine), and
  is reached three ways: **direct CLI**, **SSH attach**, and **telnet
  attach** (telnet at his word; SSH is the recommended road — telnet is
  plaintext and the client says so on that door, once, without nagging).
- On attach it **configures the terminal UI in the Termux screen** — a
  full terminal interface drawn to the size of the phone's terminal:
  channel window, nick list, input line, status bars. No browser, no app
  store, no separate download: a terminal is enough.
- Desk design, marked: because the client lives on the shell, sessions
  **persist across detach** — close Termux, come back, re-attach, and the
  session is where you left it (the tmux pattern, native to the client).

## Multiserver — the mIRC pattern

His dictation: "we will want multiserver capability like mirc did it."

- Simultaneous connections to **many networks at once** — the house
  network and any other — each with its own server window, its own nick,
  its own channels, all live at the same time.
- Switching is a keystroke; a status overview shows every connection,
  its lag, and its unread highlights across all networks at once.

## Scripting: every language (his hard requirement)

His dictation: "we want it to allow all forms of language as its
scripting language so im sure that's probably a difficult task."

It is — and the desk's architecture for it, marked as desk design:

- **The bridge is a protocol, not an interpreter.** The client speaks a
  documented line protocol to script processes: events flow out
  (messages, joins, modes, highlights), commands flow back in (say, act,
  join, raw). **Any language that can read a line and print a line can
  script bleatsirc** — Python, shell, Perl, Lua, JavaScript, Rust, a
  compiled binary, anything. No member is told their tongue is wrong.
- Embedded quick-scripting inside the client (aliases, triggers,
  one-liners in the mIRC tradition) for light work that shouldn't need a
  process at all.
- mIRC-style **event triggers** (on join, on text, on notice, on mode)
  are first-class citizens of the protocol — the 2026 founding order's
  demand, kept.
- Scripts run as the member, in the member's own account, with the
  member's permissions — a script can do nothing its author couldn't type.

## Event-style parsing — the founder's vision, confirmed (2026-11-07)

His words: "If we can develop the same type of event style parsing for
the scripting that would be perfect… that was my vision."

**The desk's feasibility ruling: it can be developed — the event model
is the center of the design, not an add-on.** Mechanism: IRC is already
an event stream — every protocol line (PRIVMSG, JOIN, PART, MODE,
NOTICE, the numerics) *is* an event. The client core parses each line
**once** into a structured event (type, source, target, text, mode
changes), and that single parse feeds both consumers:

- the internal trigger engine (mIRC-style: on TEXT / on JOIN / on MODE
  with wildcard matchtext, scope, and user levels), and
- the bridge: the same parsed events are serialized to external script
  processes, which subscribe by event type and pattern — so a script in
  any language writes what reads as native event handlers in its own
  tongue, because its main loop is simply the event stream.

- **Raw numerics are first-class events** (founder's addition, same
  sitting). Every numeric — 001 welcome, 353 names, 433 nick-in-use,
  the whole table — parses into an event carrying its code and fields,
  bindable in internal triggers the way mIRC bound `raw`, and
  subscribable on the bridge as `numeric:<code>`. Nothing the server
  says is beneath the scripting layer's notice.

### Numeric dispatch — the founder's ruling (2026-11-07)

He asked whether numerics should live in a filter file with `goto
"numeric":` dispatch, or whether goto is bad design now. The desk's
answer (registry over goto: labels are global and single-owner, a jump
chain is a search where a table is a lookup, handlers need priority and
stop-semantics goto can't give) went to his pen, and he ruled: **"do it
the most efficient and cross-platform and multiserver way."** Filed as
the binding design:

- **Efficient:** each line is parsed **once** into one event object;
  numerics dispatch through a hash table (code → handler chain), never
  a scan. Subscription patterns compile once at registration. One parse
  serves the trigger engine, every bridge script, and the UI — nothing
  re-parses per consumer.
- **Cross-platform:** the numeric registry is **data, not code** — one
  declarative table file (code → default handler, priority, stop flag)
  that loads identically on Linux, Android/Termux, Windows, and macOS;
  the bridge stays line-based text over stdio/sockets, no platform
  paths, no binary formats.
- **Multiserver:** every event carries its **connection context**
  (network/server id) as a first-class field. The registry is shared —
  numerics are protocol-global — but dispatch is per-connection, state
  built from numerics (names lists, ISUPPORT) is kept per-connection
  and never bleeds across servers, and any handler may scope itself to
  one network or ride all of them.
- Goto remains what it is in modern practice: an engine-room technique
  (cleanup paths, generated dispatch) the implementer may use under the
  floorboards. It never surfaces in the scripting layer — members see
  a registry and events.

The pattern is battle-tested elsewhere (WeeChat's signals, Eggdrop's
binds, irssi's signals); the house's own contribution is making the
bridge language-neutral. **Fallback floor, if full parity ever hits a
wall:** external scripts always receive raw lines plus client-side
subscription filtering, so every language keeps working even for events
the core doesn't deep-parse — parsed events where available, raw
passthrough underneath, never nothing.

## DCC and the file culture

The daemon allows DCC, FServe, and XDCC (network policy, founder's
ruling); the client **supports them natively** — DCC chat and send/get,
FServe browsing, XDCC pack requests and queues — from the terminal UI.

## Doctrine format and ultra-verbose I/O

Standing order (restated by him 2026-11-07): all features and projects
follow the **Doctrine format** — thelemic + educational annotation on
every source file — with **ultra-verbose I/O where necessary**. In a
client that means, concretely: a raw-protocol view (the classic raw
window) one keystroke away, a scripting trace that narrates what a
script saw and did, and connection diagnostics that explain themselves
instead of printing a bare error.

## Open seams — reserved to his pen

1. The default network list (the house network first — desk assumption,
   marked).
2. The script protocol's name, if he wants it coined as house property.
3. Session persistence defaults (how long a detached session is held).
4. Whether telnet attach ships at all in the first build, or waits.

---

*Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights
Reserved, Without Prejudice. Right of claim hereby reserved and coined under
the authority of the Living Man.*

93 — Live, Love, and let Love, Live.
