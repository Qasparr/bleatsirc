# 93
# ---------------------------------------------------------------------
# protocol.py -- the wire's grammar, parsed ONCE.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: RFC 1459 section 2.3.1 defines the message: an optional
# colon-led prefix, a command (a word or a three-digit numeric), and
# up to fifteen parameters, the last of which may be a "trailing"
# parameter introduced by " :" and free to contain spaces. Every line
# on the wire is parsed exactly once, here, into a Message; everything
# downstream -- the daemon's hash dispatch, the services, the client's
# event engine -- consumes the Message and never re-reads the raw line.
# DOCTRINE: one parse is the protocol form of the house rule that a
# thing be weighed once, in its own tongue, and the weighing shared.
# ---------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class Message:
    """One parsed IRC line.

    prefix:  the source (server name, or nick!user@host), or None.
    command: uppercased word ("PRIVMSG") or three digits ("001").
    params:  middle parameters, with the trailing parameter appended
             as the final element when the line carried one.
    """

    prefix: str | None
    command: str
    params: list = field(default_factory=list)

    @property
    def trailing(self) -> str:
        """The trailing parameter, or "" when the line had none."""
        return self.params[-1] if self.params else ""

    @property
    def source_nick(self) -> str | None:
        """The nick portion of the prefix, when the prefix has one."""
        if not self.prefix:
            return None
        return self.prefix.split("!", 1)[0]


def parse_line(line: str) -> Message:
    """Parse one raw line (CRLF already stripped) into a Message.

    MECHANISM: split off the prefix if the line opens with ':';
    isolate the trailing parameter at the first " :" so spaces inside
    it survive; what remains splits cleanly on single spaces.
    """
    line = line.rstrip("\r\n")
    prefix = None
    rest = line
    if rest.startswith(":"):
        prefix, _, rest = rest[1:].partition(" ")
    trailing = None
    if " :" in rest:
        rest, _, trailing = rest.partition(" :")
    parts = [p for p in rest.split(" ") if p != ""]
    command = parts[0].upper() if parts else ""
    params = parts[1:]
    if trailing is not None:
        params.append(trailing)
    return Message(prefix=prefix, command=command, params=params)


def format_msg(command: str, *params: str, prefix: str | None = None) -> str:
    """Build one raw line from a command and its parameters.

    MECHANISM: the final parameter is emitted as a trailing parameter
    (after " :") whenever it contains a space, is empty, or begins
    with ':' -- the three cases the grammar requires. Lines are
    returned without CRLF; the transport adds it.
    """
    out = []
    if prefix:
        out.append(":" + prefix)
    out.append(command)
    if params:
        middle, last = params[:-1], params[-1]
        out.extend(middle)
        if " " in last or last == "" or last.startswith(":"):
            out.append(":" + last)
        else:
            out.append(last)
    return " ".join(out)


class Registry:
    """Hash dispatch: command string -> ordered handler chain.

    MECHANISM: a plain dict of lists. Registration is data, not
    control flow -- the founder's ruled replacement for the goto table:
    O(1) lookup, handlers chain in registration order, and the same
    table shape serves the daemon and the client on every platform.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def on(self, command: str, handler) -> None:
        self._handlers.setdefault(command.upper(), []).append(handler)

    def handlers_for(self, command: str) -> list:
        return self._handlers.get(command.upper(), [])

    def knows(self, command: str) -> bool:
        return command.upper() in self._handlers


# 93 -- Live, Love, and let Love, Live.
