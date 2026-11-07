# 93
# ---------------------------------------------------------------------
# handlers_msg.py -- messaging: PRIVMSG, NOTICE, AWAY.
#
# "Say It. Spray It. Own It." -- NVLLA VOX TACEBITVR: no voice
# shall be silenced.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: handlers are `async def h(server, conn, msg)`; this
# module exposes HANDLERS = [(command, fn), ...] and server.py loads
# it defensively. PRIVMSG and NOTICE share one routing engine,
# _route(server, conn, msg, quiet): quiet=False speaks errors,
# quiet=True (NOTICE) swallows them whole, as the protocol demands
# that a NOTICE never be answered.
# DOCTRINE: The Line -- public is public, private is private. A
# channel message goes to the room and never to the sender's own
# echo; a nick message goes to that nick alone. Routing is the
# whole law here, and it is kept in one place so it cannot drift.
# ---------------------------------------------------------------------

from .protocol import format_msg
from .state import casefold


def _numeric(server, conn, code, *params):
    """MECHANISM: one server-prefixed numeric reply to conn."""
    conn.send(format_msg(code, conn.nick, *params,
                         prefix=server.config['server_name']))


async def _route(server, conn, msg, quiet):
    """Route one PRIVMSG/NOTICE to each comma-separated target.

    MECHANISM: validation first (411 no recipient, 412 no text),
    then per target: '#'-targets resolve through server.channels,
    bare targets through server.connections. Channel relay goes to
    every member EXCEPT the sender; +n rooms refuse outside voices
    with 404. Nick delivery answers 301 when the target is away
    (PRIVMSG only).
    DOCTRINE: when quiet is set (NOTICE), every error numeric and
    the away reply are suppressed entirely -- a NOTICE is fire and
    forget, and an error about a NOTICE would itself be a reply,
    which the form forbids. Delivery itself is identical either
    way: quiet changes the reporting, never the routing.
    """
    if len(msg.params) < 1:
        if not quiet:
            _numeric(server, conn, '411',
                     'No recipient given (PRIVMSG)')
        return
    if len(msg.params) < 2 or msg.trailing == '':
        if not quiet:
            _numeric(server, conn, '412', 'No text to send')
        return
    text = msg.trailing
    command = msg.command
    for target_name in msg.params[0].split(','):
        if not target_name:
            continue
        if target_name.startswith('#'):
            channel = server.channels.get(casefold(target_name))
            if channel is None:
                if not quiet:
                    _numeric(server, conn, '403', target_name,
                             'No such channel')
                continue
            if casefold(conn.nick) not in channel.members and \
                    'n' in channel.modes:
                # +n: no external messages -- outsiders may read the
                # NAMES list but may not speak into the room.
                if not quiet:
                    _numeric(server, conn, '404', channel.name,
                             'Cannot send to channel')
                continue
            line = format_msg(command, channel.name, text,
                              prefix=conn.prefix)
            for member in list(channel.members.values()):
                if member is not conn:
                    member.send(line)
        else:
            tconn = server.connections.get(casefold(target_name))
            if tconn is None:
                if not quiet:
                    _numeric(server, conn, '401', target_name,
                             'No such nick')
                continue
            tconn.send(format_msg(command, tconn.nick, text,
                                  prefix=conn.prefix))
            if tconn.away and not quiet:
                _numeric(server, conn, '301', tconn.nick, tconn.away)


async def _privmsg(server, conn, msg):
    await _route(server, conn, msg, quiet=False)


async def _notice(server, conn, msg):
    await _route(server, conn, msg, quiet=True)


async def _away(server, conn, msg):
    """MECHANISM: AWAY with a non-empty trailing marks the conn away
    (305); AWAY bare clears the mark (306). The stored text is what
    a later PRIVMSG sender hears back as the 301 reply.
    DOCTRINE: absence is stated, never inferred -- the wire marks
    a user away only when they say so, and unmarks them the same
    way. Presence is the user's own claim to make and to withdraw.
    """
    if msg.params and msg.trailing:
        conn.away = msg.trailing
        _numeric(server, conn, '305',
                 'You are now marked as being away')
    else:
        conn.away = None
        _numeric(server, conn, '306',
                 'You are no longer marked as being away')


HANDLERS = [
    ('PRIVMSG', _privmsg),
    ('NOTICE', _notice),
    ('AWAY', _away),
]

# 93 -- Live, Love, and let Love, Live.
