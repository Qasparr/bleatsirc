# 93
# ---------------------------------------------------------------------
# services/__init__.py -- the embedded services, seated in the daemon.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe
# (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written Saturday, November 7, 2026, Anno V:xii e.n. (2026 e.v.),
# under the Method of Science, Aim of Religion -- Scientific
# Illuminism.
#
# MECHANISM: attach(server) is the one seating ceremony. It builds
# the service objects, publishes them on server.services under
# their lowercased nicks, reserves those nicks against member
# registration, and chains one PRIVMSG router into the server's
# Registry after the core handlers. The router is deliberately
# quiet: a PRIVMSG whose target is not a service nick falls through
# untouched, so member-to-member traffic is never the services'
# business.
# DOCTRINE: the services are pseudoclients living INSIDE the daemon
# -- no Anope, no Atheme, no second process, no second rulebook
# (CUSTOM-IRCD-SPEC). They answer at their nicks like users and hold
# server-class power, and their names are house ground: reserved,
# so no member can wear a service's face and harvest passwords
# under it. Sister desks (ChanServ, OperServ, the IRCopBot) are
# imported defensively: attach() seats whichever desks have landed
# and never lets a missing one keep the daemon -- or the desks that
# did land -- from running.
# ---------------------------------------------------------------------

from .nickserv import NickServ
from .hostserv import HostServ

# MECHANISM: the full house roster, by lowercased nick. Desks whose
# modules have not landed yet are simply absent from a given build;
# the list names the house, not a promise about tonight's files.
SERVICE_NICKS = ["nickserv", "chanserv", "hostserv", "operserv",
                 "ircopbot"]

# DOCTRINE: optional desks are seated by name when present. Each
# entry names (module, candidate class names) so a sister builder's
# reasonable naming choice still seats the desk.
_OPTIONAL_SERVICES = [
    ("chanserv", ("ChanServ",)),
    ("operserv", ("OperServ",)),
    ("ircopbot", ("IRCopBot", "IrcopBot", "IRCopbot")),
]


def _load_optional(module_name, class_names):
    """Instantiate an optional service class, or return None.

    MECHANISM: ImportError (module not landed) and a landed module
    missing the expected class both yield None -- attach() must
    work identically before and after the sister desks arrive.
    """
    try:
        module = __import__(f"{__name__}.{module_name}", fromlist=["*"])
    except ImportError:
        return None
    for class_name in class_names:
        cls = getattr(module, class_name, None)
        if cls is not None:
            try:
                return cls()
            except Exception:
                return None
    return None


def _reserve_nicks(server, nicks):
    """Reserve the service nicks against member registration.

    MECHANISM: server.reserved_nicks may be a set, a list, or not
    exist yet in a given build of the core; each shape is honoured
    in place rather than replaced, so the core's own bookkeeping is
    never silently swapped out from under it.
    """
    reserved = getattr(server, "reserved_nicks", None)
    if reserved is None:
        setattr(server, "reserved_nicks", set(nicks))
    elif isinstance(reserved, set):
        reserved.update(nicks)
    elif isinstance(reserved, list):
        for nick in nicks:
            if nick not in reserved:
                reserved.append(nick)


def attach(server):
    """Seat the embedded services on the server. Returns the dict.

    MECHANISM: server.services is keyed by lowercased service nick
    and MERGED into, never overwritten -- a desk seated by an
    earlier attach (or by the core itself) keeps its state. The
    PRIVMSG router is registered once per server, however often
    attach is called, so no service ever answers a line twice.
    """
    services = getattr(server, "services", None)
    if not isinstance(services, dict):
        services = {}
        server.services = services

    seated = [NickServ(), HostServ()]
    for module_name, class_names in _OPTIONAL_SERVICES:
        service = _load_optional(module_name, class_names)
        if service is not None:
            seated.append(service)

    for service in seated:
        nick = getattr(service, "nick", None) or type(service).__name__
        services[nick.lower()] = service
    _reserve_nicks(server, [nick.lower() for nick in
                            (getattr(s, "nick", "") for s in seated)
                            if nick])

    if not getattr(server, "_services_router_registered", False):
        registry = getattr(server, "registry", None)
        if registry is not None and hasattr(registry, "on"):

            async def route_privmsg(*args):
                """Route a PRIVMSG to a service when addressed to one.

                MECHANISM: the house handler shape is
                h(server, conn, msg); the brief's older shape is
                h(conn, msg). This router accepts both -- with two
                arguments the server is the one attach() seated it
                on -- so the router survives either dispatch the
                core settles on. A target that names no service is
                left entirely alone: the router returns without a
                word and core delivery proceeds as if it were not
                here.
                """
                if len(args) == 3:
                    srv, conn, msg = args
                elif len(args) == 2:
                    srv, conn, msg = server, args[0], args[1]
                else:
                    return
                if not getattr(msg, "params", None):
                    return
                target = msg.params[0].lower()
                service = (getattr(srv, "services", None) or {}).get(
                    target)
                if service is not None and hasattr(service, "handle"):
                    result = service.handle(srv, conn, msg)
                    if result is not None and hasattr(
                            result, "__await__"):
                        await result

            registry.on("PRIVMSG", route_privmsg)
            try:
                server._services_router_registered = True
            except Exception:
                pass

    return server.services


__all__ = ["attach", "SERVICE_NICKS", "NickServ", "HostServ"]


# 93 -- Live, Love, and let Love, Live.
