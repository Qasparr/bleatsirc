# 93
# ---------------------------------------------------------------------
# "The herd is known by its names, and every name is weighed in the
#  tongue that coined it."
#
# state.py -- the daemon's living memory: connections and channels.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: this module holds NO behaviour beyond the smallest
# primitives (a connection knows how to emit one line and how to
# close; a channel is a plain record). All protocol judgement lives
# in the handlers; all global bookkeeping lives in server.Server.
# DOCTRINE: state is kept plain and inspectable so that any claim
# about who is present, who holds a mode, or what a channel holds
# can be proven from the record itself -- TRVVTH over assertion.
# Per-connection state lives in a dict created fresh in every Conn
# constructor, so one user's bookkeeping can never bleed into
# another's (CODING-BRIEF invariant 2).
# ---------------------------------------------------------------------

import time

# MECHANISM: RFC 1459 section 2.2 casemapping. Because the original
# IRC implementation treated {}| as the lowercase forms of []\, and
# ~ as the lowercase form of ^, nick and channel identity folds those
# four pairs together. str.lower() alone would split identities that
# the protocol says are one; the translation table below is the rest
# of the mapping, applied after lowercasing so ASCII A-Z fold too.
_RFC1459_TABLE = str.maketrans({"{": "[", "}": "]", "|": "\\", "~": "^"})


def casefold(s: str) -> str:
    """Fold a nick or channel name to its RFC1459 identity form.

    MECHANISM: lowercase, then map '{'->'[', '}'->']', '|'->'\\',
    '~'->'^'. Every dict key in the daemon that names a user or a
    channel passes through here exactly once, at the boundary.
    DOCTRINE: identity is what the protocol says it is, not what
    the terminal happened to render.
    """
    return s.lower().translate(_RFC1459_TABLE)


class Conn:
    """One client connection and everything the daemon knows of it.

    MECHANISM: constructed by Server._client_connected with the
    asyncio reader/writer pair and the peer host. Registration
    fields (nick/user/realname) start as None and are filled by the
    handlers_core registration handshake; `registered` flips True
    only when that handshake completes, and the server's dispatch
    gate fails closed on it until then.
    DOCTRINE: equality is identity (the default object eq/hash is
    deliberately NOT overridden) -- two Conns are never "equal by
    value", because on the wire a user is a presence, not a record.
    """

    def __init__(self, server, reader, writer, host):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.host = host
        # Registration handshake state (handlers_core owns these).
        self.nick = None
        self.user = None
        self.realname = None
        self.registered = False
        # Channels this connection has joined, by lower-cased name.
        self.channels = set()
        # User modes (e.g. 'i', 'o' as a mode letter -- oper status
        # proper is the is_oper flag below, kept separate on purpose
        # so a mode display can never accidentally grant power).
        self.modes = set()
        # Staff flags. DOCTRINE: is_oper / is_staff gate the house
        # law of staff immunity (CODING-BRIEF invariant 5); handlers
        # read them, nothing else may set them but OPER and tests.
        self.is_oper = False
        self.is_staff = False
        # Per-connection scratch space (ISUPPORT/353 bookkeeping and
        # whatever a handler needs). MECHANISM: a fresh dict per
        # instance -- never a class attribute, never shared.
        self.state = {}
        # Away message, or None when the user is present.
        self.away = None

    @property
    def prefix(self) -> str:
        """The wire prefix for this user: nick!user@host."""
        return f"{self.nick}!{self.user}@{self.host}"

    def send(self, line: str) -> None:
        """Write one line (CRLF added here) to the client.

        MECHANISM: encode UTF-8 with replacement so a stray bad
        character can never raise inside a broadcast loop and take
        down delivery to everyone after this connection in line.
        A reset/broken peer is swallowed: a vanished client is a
        normal event on a network, not an error worth killing for;
        the read loop will notice the EOF and clean up.
        """
        try:
            self.writer.write((line + "\r\n").encode("utf-8", "replace"))
        except (ConnectionResetError, BrokenPipeError):
            pass

    def close(self) -> None:
        """Close the transport, tolerating an already-dead writer."""
        try:
            self.writer.close()
        except Exception:
            pass


class Channel:
    """One channel: its members, modes, topic, and bans.

    MECHANISM: `members` and `member_modes` are keyed by casefolded
    nick so lookups never depend on the case a command happened to
    type. `member_modes` values are sets holding 'o' and/or 'v'
    (PREFIX=(ov)@+ per the 005 the daemon advertises). `created` is
    epoch seconds at construction -- the first JOIN that finds no
    channel creates it, and its creator becomes `founder`.
    DOCTRINE: the channel record is the whole truth of the room;
    handlers mutate it in the open and the record, not memory of
    what a handler "meant", decides the next command.
    """

    def __init__(self, name):
        # Original case preserved for display; identity is the
        # casefolded form used as the server's dict key.
        self.name = name
        self.members = {}        # casefolded nick -> Conn
        self.member_modes = {}   # casefolded nick -> set of 'o'/'v'
        self.modes = set()       # channel modes, e.g. 'n', 't', 'm'
        self.topic = None
        self.topic_setter = None
        self.topic_time = None
        # Casefolded nick of the channel's creator, or None.
        self.founder = None
        # Ban masks, as strings exactly as set ('nick!user@host'
        # patterns); matching is the MODE handler's business.
        self.bans = set()
        self.key = None          # channel key (+k), or None
        self.limit = None        # member limit (+l), or None
        self.created = int(time.time())


# 93 -- Live, Love, and let Love, Live.
