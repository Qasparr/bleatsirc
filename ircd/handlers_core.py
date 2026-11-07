# 93
# ---------------------------------------------------------------------
# handlers_core.py -- registration and the core commands.
#
# "Say It. Spray It. Own It." -- the Bleats motto, the network's
# first law in miniature: a voice is claimed, then it speaks.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: this module owns PASS, NICK, USER, PING, PONG, QUIT and
# CAP. Handlers are `async def h(server, conn, msg)`; the module
# exposes HANDLERS = [(command_str, fn), ...] and server.py loads it
# defensively into the Registry. Registration is the two-key lock of
# RFC 1459: a connection is not a user until it holds BOTH a valid,
# unclaimed nick (NICK) and a username (USER), in either order; the
# moment both keys turn, maybe_register() fires the 001-005 welcome
# burst and the MOTD exactly once.
# DOCTRINE: the nick is the member's claimed name on the wire. It is
# granted by grammar and by non-collision, never by favour -- except
# that services hold their names absolutely (436, not 433), because a
# counterfeit NickServ is a counterfeit of the house itself. The user
# is above all, but even the user enters by the door, not the wall:
# fail closed, validate first, register once, reregister never (462).
# ---------------------------------------------------------------------

from pathlib import Path

from .protocol import format_msg

# MECHANISM: casefold is the RFC 1459 casemapping owned by
# ircd/state.py (Builder A's module, written in parallel). The import
# is defensive so this module still imports for inspection if state.py
# has not landed yet; the fallback below is the identical mapping --
# lower-case plus {}|~ -> []\^ -- never a different weighing.
# DOCTRINE: two implementations of one mapping must agree exactly, or
# nick identity itself forks; the fallback is a mirror, not a rival.
try:
    from .state import casefold
except ImportError:  # pragma: no cover - only while state.py is absent
    def casefold(s: str) -> str:
        return (
            s.lower()
            .replace("{", "[")
            .replace("}", "]")
            .replace("|", "\\")
            .replace("~", "^")
        )


# ---------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------

def _numeric(conn, server, code, *rest, target=None):
    """Send one numeric reply to conn.

    MECHANISM: every numeric here is
    :<server_name> <code> <target> <rest...> -- target defaults to
    conn.nick, or '*' when no nick is set yet (the RFC placeholder for
    a connection that has not claimed a name). format_msg() makes the
    final parameter trailing whenever it carries spaces, so plain
    English reply texts need no manual colon.
    DOCTRINE: one helper, one shape -- a numeric that looks different
    from its siblings is a lie about the server's discipline.
    """
    if target is None:
        target = conn.nick or "*"
    server_name = server.config["server_name"]
    conn.send(format_msg(code, target, *rest, prefix=server_name))


def _is_letter(ch: str) -> bool:
    # MECHANISM: RFC letters are ASCII A-Z / a-z; str.isalpha() would
    # also admit non-ASCII letters the wire grammar does not.
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


# MECHANISM: the "special" class of RFC 1459 section 2.3.1 as fixed
# by the task contract: []\`_^{|} -- nine characters.
_NICK_SPECIALS = frozenset("[]\\`_^{|}")


def _valid_nick(nick: str) -> bool:
    """True when `nick` obeys the RFC 1459 section 2.3.1 grammar.

    MECHANISM: length 1..16 (16 is the NICKLEN this server advertises
    in 005); first char a letter or a special; every later char a
    letter, a digit, '-', or a special. A leading digit or '-' is the
    classic erroneous nick, hence 432, not a quiet truncation.
    DOCTRINE: the grammar is the whole gate. No nick is refused for
    taste, and none is admitted against the grammar.
    """
    if not (1 <= len(nick) <= 16):
        return False
    first = nick[0]
    if not (_is_letter(first) or first in _NICK_SPECIALS):
        return False
    for ch in nick[1:]:
        if _is_letter(ch) or ("0" <= ch <= "9") or ch == "-" or ch in _NICK_SPECIALS:
            continue
        return False
    return True


def _channel_peers(server, conn, include_self=False):
    """Distinct Conns sharing any channel with conn.

    MECHANISM: conn.channels holds casefolded channel names; each
    server.channels[name].members is walked once and the result
    de-duplicated by identity, so a peer met in three channels still
    receives exactly one copy of a NICK/QUIT line. Members are Conns
    in the built daemon; the string branch (members as nicks, resolved
    through server.connections) and dict branch keep the walk honest
    against either container shape without re-parsing anything.
    DOCTRINE: a witness hears the news once. Duplicated quit/nick
    lines are noise wearing the mask of emphasis.
    """
    peers = []
    seen = set()
    if include_self:
        seen.add(id(conn))
        peers.append(conn)
    for chan_name in list(conn.channels):
        channel = server.channels.get(chan_name)
        if channel is None:
            continue
        members = getattr(channel, "members", None)
        if members is None:
            continue
        if isinstance(members, dict):
            candidates = list(members.values())
        else:
            candidates = list(members)
        for member in candidates:
            peer = None
            if isinstance(member, str):
                peer = server.connections.get(casefold(member))
            else:
                peer = member
            if peer is None or id(peer) in seen:
                continue
            seen.add(id(peer))
            peers.append(peer)
    return peers


def _send_motd(conn, server):
    """Send the 375/372/376 MOTD sequence.

    MECHANISM: the text is docs/bleats-motd.txt at the repo root --
    Path(__file__).parent is ircd/, so parent.parent is the root.
    Every file line (newline stripped, nothing skipped) becomes one
    372 prefixed '- '. A missing file degrades to a single 372
    carrying the motto, never to silence: 375 and 376 still frame it.
    DOCTRINE: the MOTD is the house rules posted at the door. If the
    printed sheet is lost, the motto is spoken instead -- the door is
    never left unmarked.
    """
    nick = conn.nick
    server_name = server.config["server_name"]
    _numeric(conn, server, "375", f"- {server_name} Message of the day -")
    motd_path = Path(__file__).resolve().parent.parent / "docs" / "bleats-motd.txt"
    if motd_path.exists():
        text = motd_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            _numeric(conn, server, "372", "- " + line)
    else:
        _numeric(
            conn, server, "372",
            "- Welcome to Bleats. Say It. Spray It. Own It.",
        )
    _numeric(conn, server, "376", "End of /MOTD command.")


def maybe_register(server, conn):
    """Complete registration the moment both NICK and USER are held.

    MECHANISM: fires only when conn.nick and conn.user are set and
    conn.registered is still False; the flag is set BEFORE the burst
    so a re-entrant call can never double-welcome. The burst is the
    contract's exact sequence: 001 welcome naming the full
    nick!user@host prefix, 002 host/version from config, 003 creation
    string from config, 004 server/version/user-modes/channel-modes,
    005 ISUPPORT telling the truth about this build (CHANTYPES=#,
    PREFIX=(ov)@+, CHANMODES=b,k,l,imnst, CASEMAPPING=rfc1459,
    NICKLEN=16, TARGMAX=KICK:4, NETWORK from config), then the MOTD.
    DOCTRINE: ISUPPORT is a sworn statement, not advertising -- every
    token in 005 names a thing this daemon actually does.
    """
    if not conn.nick or not conn.user or conn.registered:
        return
    conn.registered = True
    nick = conn.nick
    server_name = server.config["server_name"]
    version = server.config["version"]
    network = server.config.get("network", "Bleats")
    _numeric(conn, server, "001", "Welcome to the Bleats network " + conn.prefix)
    _numeric(
        conn, server, "002",
        f"Your host is {server_name}, running version {version}",
    )
    _numeric(
        conn, server, "003",
        "This server was created " + server.config["created"],
    )
    _numeric(conn, server, "004", server_name, version, "io", "bklmnst")
    _numeric(
        conn, server, "005",
        "CHANTYPES=#",
        "PREFIX=(ov)@+",
        "CHANMODES=b,k,l,imnst",
        "CASEMAPPING=rfc1459",
        "NICKLEN=16",
        "TARGMAX=KICK:4",
        f"NETWORK={network}",
        "are supported by this server",
    )
    _send_motd(conn, server)


# ---------------------------------------------------------------------
# PASS -- the password is filed, never echoed
# ---------------------------------------------------------------------

async def h_pass(server, conn, msg):
    """PASS: store the offered password in per-connection state.

    MECHANISM: a registered connection may not reregister (462); a
    PASS with no parameter is 461. Otherwise params[0] is kept at
    conn.state['password'] for whatever later check wants it. There
    is deliberately no success reply -- RFC PASS is silent.
    DOCTRINE: a password is a thing whispered once and never read
    back over the wire; silence is the correct receipt.
    """
    if conn.registered:
        _numeric(conn, server, "462", "You may not reregister")
        return
    if not msg.params:
        _numeric(conn, server, "461", "PASS", "Not enough parameters")
        return
    conn.state["password"] = msg.params[0]


# ---------------------------------------------------------------------
# NICK -- claim a name, or change it in public
# ---------------------------------------------------------------------

async def h_nick(server, conn, msg):
    """NICK: validate, check collision, index, announce changes.

    MECHANISM: no parameter is 431; a grammar failure is 432 (both
    addressed to '*' per the contract -- the claimant has no standing
    name for this purpose yet). Collision is looked up under
    casefold(new): a different holder who is a service pseudoclient
    (state['service']) takes 436, any other different holder 433;
    holding your own nick (even recased) is no collision at all.
    On a registered nick CHANGE the old prefix is captured BEFORE the
    nick moves, the index is dropped and rebuilt around the change,
    and one NICK line from the old prefix is broadcast to the user
    and every distinct channel peer. Pre-registration, the nick is
    simply set, indexed, and maybe_register() is consulted.
    DOCTRINE: first come, first served -- and services are served
    absolutely, because their names are load-bearing trust.
    """
    if not msg.params:
        _numeric(conn, server, "431", "No nickname given", target="*")
        return
    new = msg.params[0]
    if not _valid_nick(new):
        _numeric(conn, server, "432", new, "Erroneous nickname", target="*")
        return
    holder = server.connections.get(casefold(new))
    if holder is not None and holder is not conn:
        if holder.state.get("service"):
            _numeric(conn, server, "436", new, "Nickname collision KILL")
        else:
            _numeric(conn, server, "433", new, "Nickname is already in use")
        return
    if conn.registered:
        # MECHANISM: the old prefix must be built before conn.nick
        # changes, or the announcement would claim the new name
        # introduced itself -- a small forgery against the witnesses.
        old_prefix = conn.prefix
        server.drop_nick(conn)
        conn.nick = new
        server.index_nick(conn)
        line = format_msg("NICK", new, prefix=old_prefix)
        for peer in _channel_peers(server, conn, include_self=True):
            peer.send(line)
    else:
        conn.nick = new
        server.index_nick(conn)
        maybe_register(server, conn)


# ---------------------------------------------------------------------
# USER -- the second key of the registration lock
# ---------------------------------------------------------------------

async def h_user(server, conn, msg):
    """USER: record username and realname, then consult the lock.

    MECHANISM: registered connections get 462; fewer than four
    parameters is 461. conn.user is params[0] exactly as given (a
    leading '~' is the client's ident story, not ours to edit), and
    conn.realname is the trailing parameter (params[3]) -- free text
    that arrived as trailing precisely so it may contain spaces.
    DOCTRINE: the username is filed as offered. The house records
    what a member says they are; it does not correct identity at the
    door.
    """
    if conn.registered:
        _numeric(conn, server, "462", "You may not reregister")
        return
    if len(msg.params) < 4:
        _numeric(conn, server, "461", "USER", "Not enough parameters")
        return
    conn.user = msg.params[0]
    conn.realname = msg.trailing
    maybe_register(server, conn)


# ---------------------------------------------------------------------
# PING / PONG -- the wire's heartbeat
# ---------------------------------------------------------------------

async def h_ping(server, conn, msg):
    """PING: answer with PONG, echoing the token verbatim.

    MECHANISM: the token is the trailing parameter when present,
    else the first parameter, else empty. The reply is
    :<server_name> PONG <server_name> <token> -- the server names
    itself as both source and first parameter, per RFC habit.
    DOCTRINE: a ping is a question about liveness only; the answer
    carries the asker's own token back, unchanged, as proof.
    """
    token = msg.trailing or (msg.params[0] if msg.params else "")
    server_name = server.config["server_name"]
    conn.send(format_msg("PONG", server_name, token, prefix=server_name))


async def h_pong(server, conn, msg):
    """PONG: no-op.

    MECHANISM: a client's answer to our ping needs no answer in
    return; any liveness bookkeeping belongs to the transport layer,
    not the command layer.
    DOCTRINE: not every utterance deserves a reply. Silence here is
    the protocol working as designed.
    """
    return None


# ---------------------------------------------------------------------
# QUIT -- leave, and let the witnesses hear it once
# ---------------------------------------------------------------------

async def h_quit(server, conn, msg):
    """QUIT: announce departure to channel peers, then clean up.

    MECHANISM: the reason is the trailing parameter, defaulting to
    'Quit'. One QUIT line from conn's own prefix goes to every
    distinct Conn sharing a channel with conn -- never to conn
    itself, whose socket is closing. Only after the announcement
    does server.remove_connection() do the full cleanup (channels
    plus the nick index) and conn.close() shut the transport.
    DOCTRINE: departure is announced before it is effected, like the
    ledger rule for oper acts: the record of a leaving precedes the
    leaving, so no channel is left wondering at a ghost.
    """
    reason = msg.trailing or "Quit"
    line = format_msg("QUIT", reason, prefix=conn.prefix)
    for peer in _channel_peers(server, conn, include_self=False):
        peer.send(line)
    server.remove_connection(conn)
    conn.close()


# ---------------------------------------------------------------------
# CAP -- capability negotiation, empty list for the POC
# ---------------------------------------------------------------------

async def h_cap(server, conn, msg):
    """CAP: the minimal honest negotiation.

    MECHANISM: LS is answered with an empty capability list
    (CAP * LS :), REQ with an ACK of that same empty list -- this
    build supports no capabilities and says so, which per the CAP
    spec is a complete and legal negotiation. END/ACK/NAK need no
    reply; unknown subcommands are ignored, not errored.
    DOCTRINE: an empty list honestly offered beats a rich list
    falsely claimed -- the ISUPPORT doctrine applied to CAP.
    """
    sub = msg.params[0].upper() if msg.params else ""
    server_name = server.config["server_name"]
    if sub == "LS":
        conn.send(format_msg("CAP", "*", "LS", "", prefix=server_name))
    elif sub == "REQ":
        conn.send(format_msg("CAP", "*", "ACK", "", prefix=server_name))
    elif sub in ("END", "ACK", "NAK"):
        return None
    else:
        return None


# ---------------------------------------------------------------------
# The dispatch table -- registration is data, not control flow.
# MECHANISM: server.py walks this list into the Registry; adding a
# command is adding a row, never editing a caller.
# ---------------------------------------------------------------------

HANDLERS = [
    ("PASS", h_pass),
    ("NICK", h_nick),
    ("USER", h_user),
    ("PING", h_ping),
    ("PONG", h_pong),
    ("QUIT", h_quit),
    ("CAP", h_cap),
]

# 93 -- Live, Love, and let Love, Live.
