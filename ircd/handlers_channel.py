# 93
# ---------------------------------------------------------------------
# handlers_channel.py -- channels: JOIN, PART, MODE, TOPIC, NAMES,
# INVITE, KICK.
#
# "Say It. Spray It. Own It." -- VOX CAPRI, VOX POPVLI.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: handlers are `async def h(server, conn, msg)`; this
# module exposes HANDLERS = [(command, fn), ...] and server.py loads
# it defensively. Channel keys everywhere are casefold(name) under
# the RFC1459 casemap; the Channel object keeps the original case
# for display. Numerics go out as
# format_msg(code, conn.nick, ..., prefix=server_name).
# DOCTRINE: a channel is a room the users own. The daemon keeps the
# gates the room itself set (+i/+k/+l/bans) and no others; staff
# power does not announce itself inside a room (see KICK).
# ---------------------------------------------------------------------

import fnmatch
import time

from .protocol import format_msg
from .state import Channel, casefold


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _numeric(server, conn, code, *params):
    """MECHANISM: one server-prefixed numeric reply to conn."""
    conn.send(format_msg(code, conn.nick, *params,
                         prefix=server.config['server_name']))


def _need_params(server, conn, command):
    """MECHANISM: 461 -- the command arrived without its arguments."""
    _numeric(server, conn, '461', command, 'Not enough parameters')


def _is_op(channel, conn):
    """MECHANISM: op iff 'o' sits in member_modes for conn's nick."""
    return 'o' in channel.member_modes.get(casefold(conn.nick), set())


def _broadcast(channel, line):
    """MECHANISM: send one line to every member, joiner/parter incl.

    DOCTRINE: membership events are witnessed by the whole room,
    including the one who caused them -- no silent state changes.
    """
    for member in list(channel.members.values()):
        member.send(line)


def _names_payload(channel):
    """MECHANISM: 353 payload in member insertion order.

    Each name is prefixed '@' if op, '+' elif voice, else bare --
    the PREFIX=(ov)@+ truth ISUPPORT advertises.
    """
    names = []
    for ck, member in channel.members.items():
        modes = channel.member_modes.get(ck, set())
        if 'o' in modes:
            names.append('@' + member.nick)
        elif 'v' in modes:
            names.append('+' + member.nick)
        else:
            names.append(member.nick)
    return ' '.join(names)


def _send_names(conn, server, channel):
    """MECHANISM: 353 (symbol '=' -- all channels here are public in
    the NAMES sense; secret rooms are filtered by the caller) then
    366 to close the list."""
    _numeric(server, conn, '353', '=', channel.name,
             _names_payload(channel))
    _numeric(server, conn, '366', channel.name, 'End of /NAMES list.')


# ---------------------------------------------------------------------
# JOIN
# ---------------------------------------------------------------------

async def _join(server, conn, msg):
    if not msg.params:
        _need_params(server, conn, 'JOIN')
        return
    names = msg.params[0].split(',')
    keys = msg.params[1].split(',') if len(msg.params) > 1 else []
    for idx, name in enumerate(names):
        if not name:
            continue
        if not name.startswith('#'):
            _numeric(server, conn, '403', name, 'No such channel')
            continue
        key = keys[idx] if idx < len(keys) else None
        if key == '':
            key = None
        ck = casefold(name)
        channel = server.channels.get(ck)
        creating = channel is None
        if creating:
            # MECHANISM: first joiner founds the room and is its op.
            channel = Channel(name)
            channel.founder = casefold(conn.nick)
            channel.created = int(time.time())
            server.channels[ck] = channel
        conn_ck = casefold(conn.nick)
        if conn_ck in channel.members:
            # Already inside: JOIN is idempotent, answered silently.
            continue
        # --- Gates (existing room, conn not yet a member) ----------
        # DOCTRINE: gates are the room's own law (+i/+k/+l/bans),
        # checked in invite, key, limit, ban order. Services
        # pseudoclients bypass gates entirely: they are the house,
        # not guests, and a locked room must never lock out ChanServ.
        if not conn.state.get('service'):
            invites = conn.state.setdefault('invites', set())
            if 'i' in channel.modes and ck not in invites:
                _numeric(server, conn, '473', name,
                         'Cannot join channel (+i)')
                continue
            if channel.key and key != channel.key:
                _numeric(server, conn, '475', name,
                         'Cannot join channel (+k)')
                continue
            if channel.limit and len(channel.members) >= channel.limit:
                _numeric(server, conn, '471', name,
                         'Cannot join channel (+l)')
                continue
            banned = False
            for mask in channel.bans:
                if fnmatch.fnmatchcase(conn.prefix.lower(),
                                       mask.lower()):
                    banned = True
                    break
            if banned:
                _numeric(server, conn, '474', name,
                         'Cannot join channel (+b)')
                continue
        # --- Admit ---------------------------------------------------
        channel.member_modes[conn_ck] = {'o'} if creating else set()
        channel.members[conn_ck] = conn
        conn.channels.add(ck)
        conn.state.setdefault('invites', set()).discard(ck)
        _broadcast(channel, format_msg('JOIN', channel.name,
                                       prefix=conn.prefix))
        if channel.topic:
            _numeric(server, conn, '332', channel.name, channel.topic)
            if channel.topic_time:
                _numeric(server, conn, '333', channel.name,
                         channel.topic_setter, str(channel.topic_time))
        _send_names(conn, server, channel)


# ---------------------------------------------------------------------
# PART
# ---------------------------------------------------------------------

async def _part(server, conn, msg):
    if not msg.params:
        _need_params(server, conn, 'PART')
        return
    # MECHANISM: reason is the trailing param only when one was
    # actually supplied (params beyond the channel list); msg.trailing
    # alone would echo the channel name back as its own reason.
    reason = msg.trailing if len(msg.params) >= 2 else conn.nick
    if not reason:
        reason = conn.nick
    for name in msg.params[0].split(','):
        if not name:
            continue
        ck = casefold(name)
        channel = server.channels.get(ck)
        if channel is None:
            _numeric(server, conn, '403', name, 'No such channel')
            continue
        conn_ck = casefold(conn.nick)
        if conn_ck not in channel.members:
            _numeric(server, conn, '442', name,
                     "You're not on that channel")
            continue
        # Broadcast BEFORE removal so the parter hears their own PART.
        _broadcast(channel, format_msg('PART', channel.name, reason,
                                       prefix=conn.prefix))
        del channel.members[conn_ck]
        channel.member_modes.pop(conn_ck, None)
        conn.channels.discard(ck)
        if not channel.members:
            # An empty room ceases to exist; its modes die with it.
            del server.channels[ck]


# ---------------------------------------------------------------------
# MODE
# ---------------------------------------------------------------------

_CHANNEL_MODE_LETTERS = set('ovbklimnst')


async def _mode_channel(server, conn, msg, channel):
    if len(msg.params) == 1:
        # Query: 324 modestring + key/limit params, 329 creation time.
        flags = ''.join(sorted(
            channel.modes
            | ({'k'} if channel.key else set())
            | ({'l'} if channel.limit else set())))
        extra = []
        if channel.key:
            extra.append(channel.key)
        if channel.limit:
            extra.append(str(channel.limit))
        _numeric(server, conn, '324', channel.name, '+' + flags, *extra)
        _numeric(server, conn, '329', channel.name, str(channel.created))
        return
    conn_ck = casefold(conn.nick)
    if conn_ck not in channel.members:
        _numeric(server, conn, '442', channel.name,
                 "You're not on that channel")
        return
    if not _is_op(channel, conn):
        _numeric(server, conn, '482', channel.name,
                 "You're not channel operator")
        return
    modestring = msg.params[1]
    args = msg.params[2:]
    cursor = 0
    consumed = []
    direction = '+'
    attempted = False  # a real set attempt happened -> broadcast below
    for char in modestring:
        if char == '+':
            direction = '+'
            continue
        if char == '-':
            direction = '-'
            continue
        if char not in _CHANNEL_MODE_LETTERS:
            _numeric(server, conn, '472', char,
                     'is unknown mode char to me')
            continue
        if char in ('o', 'v'):
            if cursor >= len(args):
                continue
            arg = args[cursor]
            cursor += 1
            consumed.append(arg)
            attempted = True
            target = channel.members.get(casefold(arg))
            if target is None:
                _numeric(server, conn, '441', arg, channel.name,
                         "They aren't on that channel")
                continue
            modes = channel.member_modes.setdefault(casefold(arg), set())
            if direction == '+':
                modes.add(char)
            else:
                modes.discard(char)
        elif char == 'b':
            if cursor >= len(args):
                # MECHANISM: +b with no mask is the ban LIST query
                # (367 per mask, 368 to close), not a change -- so it
                # is answered to the asker only and never broadcast.
                for mask in channel.bans:
                    _numeric(server, conn, '367', channel.name, mask)
                _numeric(server, conn, '368', channel.name,
                         'End of channel ban list')
                continue
            arg = args[cursor]
            cursor += 1
            consumed.append(arg)
            attempted = True
            if direction == '+':
                channel.bans.add(arg)
            else:
                channel.bans.discard(arg)
        elif char == 'k':
            attempted = True
            if direction == '+':
                if cursor >= len(args):
                    continue
                arg = args[cursor]
                cursor += 1
                consumed.append(arg)
                channel.key = arg
            else:
                # DOCTRINE: 'k' is never stored in channel.modes;
                # the key's presence IS the flag (see 324 builder).
                channel.key = None
        elif char == 'l':
            attempted = True
            if direction == '+':
                if cursor >= len(args):
                    continue
                arg = args[cursor]
                cursor += 1
                consumed.append(arg)
                try:
                    channel.limit = int(arg)
                except (TypeError, ValueError):
                    # Invalid limit is ignored, never fatal.
                    pass
            else:
                channel.limit = None
        else:  # i, m, n, t, s -- plain flag modes, no argument
            attempted = True
            if direction == '+':
                channel.modes.add(char)
            else:
                channel.modes.discard(char)
    if attempted:
        _broadcast(channel, format_msg('MODE', channel.name, modestring,
                                       *consumed, prefix=conn.prefix))


async def _mode(server, conn, msg):
    if not msg.params:
        _need_params(server, conn, 'MODE')
        return
    target = msg.params[0]
    if target.startswith('#'):
        channel = server.channels.get(casefold(target))
        if channel is None:
            _numeric(server, conn, '403', target, 'No such channel')
            return
        await _mode_channel(server, conn, msg, channel)
        return
    # --- User modes: a user may only ever mode themselves. ----------
    if casefold(target) != casefold(conn.nick):
        _numeric(server, conn, '502',
                 "Can't change mode for other users")
        return
    if len(msg.params) == 1:
        conn.send(format_msg('MODE', conn.nick,
                             '+' + ''.join(sorted(conn.modes)),
                             prefix=conn.prefix))
        return
    modestring = msg.params[1]
    direction = '+'
    for char in modestring:
        if char == '+':
            direction = '+'
            continue
        if char == '-':
            direction = '-'
            continue
        if char == 'i':
            if direction == '+':
                conn.modes.add('i')
            else:
                conn.modes.discard('i')
        elif char == 'o':
            # DOCTRINE: oper status is GRANTED only by OPER (Group 2);
            # MODE +o from the user is ignored outright. MODE -o is
            # the one honest direction: a user may always lay power
            # down, and laying it down clears is_oper with the flag.
            if direction == '-':
                conn.modes.discard('o')
                conn.is_oper = False
        else:
            _numeric(server, conn, '501', 'Unknown MODE flag')
    conn.send(format_msg('MODE', conn.nick, modestring,
                         prefix=conn.prefix))


# ---------------------------------------------------------------------
# TOPIC
# ---------------------------------------------------------------------

async def _topic(server, conn, msg):
    if not msg.params:
        _need_params(server, conn, 'TOPIC')
        return
    name = msg.params[0]
    channel = server.channels.get(casefold(name))
    if channel is None:
        _numeric(server, conn, '403', name, 'No such channel')
        return
    if casefold(conn.nick) not in channel.members:
        _numeric(server, conn, '442', name,
                 "You're not on that channel")
        return
    if len(msg.params) == 1:
        if not channel.topic:
            _numeric(server, conn, '331', name, 'No topic is set')
        else:
            _numeric(server, conn, '332', channel.name, channel.topic)
            if channel.topic_time:
                _numeric(server, conn, '333', channel.name,
                         channel.topic_setter, str(channel.topic_time))
        return
    # Setting: +t reserves the topic to ops; without +t any member may.
    if 't' in channel.modes and not _is_op(channel, conn):
        _numeric(server, conn, '482', channel.name,
                 "You're not channel operator")
        return
    channel.topic = msg.trailing
    channel.topic_setter = conn.nick
    channel.topic_time = int(time.time())
    _broadcast(channel, format_msg('TOPIC', channel.name, channel.topic,
                                   prefix=conn.prefix))


# ---------------------------------------------------------------------
# NAMES
# ---------------------------------------------------------------------

async def _names(server, conn, msg):
    if not msg.params:
        for channel in list(server.channels.values()):
            _send_names(conn, server, channel)
        return
    for name in msg.params[0].split(','):
        if not name:
            continue
        channel = server.channels.get(casefold(name))
        if channel is None:
            _numeric(server, conn, '366', name, 'End of /NAMES list.')
            continue
        # DOCTRINE: a secret (+s) room does not publish its roster to
        # outsiders; the outsider gets the same empty 366 anyone
        # would get for a room that is not there to them.
        if 's' in channel.modes and \
                casefold(conn.nick) not in channel.members:
            _numeric(server, conn, '366', name, 'End of /NAMES list.')
            continue
        _send_names(conn, server, channel)


# ---------------------------------------------------------------------
# INVITE
# ---------------------------------------------------------------------

async def _invite(server, conn, msg):
    if len(msg.params) < 2:
        _need_params(server, conn, 'INVITE')
        return
    target = server.connections.get(casefold(msg.params[0]))
    if target is None:
        _numeric(server, conn, '401', msg.params[0], 'No such nick')
        return
    name = msg.params[1]
    channel = server.channels.get(casefold(name))
    if channel is None:
        _numeric(server, conn, '403', name, 'No such channel')
        return
    if casefold(conn.nick) not in channel.members:
        _numeric(server, conn, '442', name,
                 "You're not on that channel")
        return
    if casefold(target.nick) in channel.members:
        _numeric(server, conn, '443', target.nick, channel.name,
                 'is already on channel')
        return
    if 'i' in channel.modes and not _is_op(channel, conn):
        _numeric(server, conn, '482', channel.name,
                 "You're not channel operator")
        return
    # MECHANISM: the invite is recorded on the TARGET's per-connection
    # state, keyed by the casefolded channel name; JOIN consults and
    # discards it. Per-connection state never bleeds (Brief inv. 2).
    target.state.setdefault('invites', set()).add(casefold(channel.name))
    _numeric(server, conn, '341', target.nick, channel.name)
    target.send(format_msg('INVITE', target.nick, channel.name,
                           prefix=conn.prefix))


# ---------------------------------------------------------------------
# KICK
# ---------------------------------------------------------------------

async def _kick(server, conn, msg):
    if len(msg.params) < 2:
        _need_params(server, conn, 'KICK')
        return
    name = msg.params[0]
    ck = casefold(name)
    channel = server.channels.get(ck)
    if channel is None:
        _numeric(server, conn, '403', name, 'No such channel')
        return
    if casefold(conn.nick) not in channel.members:
        _numeric(server, conn, '442', name,
                 "You're not on that channel")
        return
    if not _is_op(channel, conn):
        _numeric(server, conn, '482', channel.name,
                 "You're not channel operator")
        return
    reason = msg.trailing if len(msg.params) >= 3 else conn.nick
    if not reason:
        reason = conn.nick
    # DOCTRINE -- MULTI-KICK: one KICK line carries a comma list and
    # the whole list executes from that one line, in order
    # (TARGMAX=KICK:4; names past the fourth are silently ignored,
    # exactly as ISUPPORT's TARGMAX tells the truth about). Each
    # victim is judged on their own facts: an unknown nick earns its
    # 401, a non-member its 441, and the line moves on -- one bad
    # name never vetoes the rest of the list.
    for target_name in msg.params[1].split(',')[:4]:
        if not target_name:
            continue
        tconn = server.connections.get(casefold(target_name))
        if tconn is None:
            _numeric(server, conn, '401', target_name, 'No such nick')
            continue
        target_ck = casefold(tconn.nick)
        if target_ck not in channel.members:
            _numeric(server, conn, '441', target_name, channel.name,
                     "They aren't on that channel")
            continue
        # DOCTRINE -- STAFF IMMUNITY (the founder's ruling, Brief
        # inv. 5): a KICK aimed at an oper or staff member simply
        # does not take effect. SILENTLY: no removal, no KICK line,
        # no error numeric, no hint that staff status was the reason
        # -- the incognito seam. The kicker sees the same nothing
        # they would see for any quietly failed act, and the wire
        # never outs who carries the house's trust.
        if tconn.is_oper or tconn.is_staff:
            continue
        # Broadcast BEFORE removal so the target hears their own KICK.
        _broadcast(channel, format_msg('KICK', channel.name, tconn.nick,
                                       reason, prefix=conn.prefix))
        del channel.members[target_ck]
        channel.member_modes.pop(target_ck, None)
        tconn.channels.discard(ck)
    if not channel.members:
        server.channels.pop(ck, None)


HANDLERS = [
    ('JOIN', _join),
    ('PART', _part),
    ('MODE', _mode),
    ('TOPIC', _topic),
    ('NAMES', _names),
    ('INVITE', _invite),
    ('KICK', _kick),
]

# 93 -- Live, Love, and let Love, Live.
