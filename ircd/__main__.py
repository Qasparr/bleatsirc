# 93
# ---------------------------------------------------------------------
# "Say it, spray it, own it -- and first, listen."
#
# __main__.py -- `python3 -m ircd`: build the Server and serve.
#
# Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice).
# Written VII day of November, Anno V:xii e.n. (2026 e.v.), under the
# Method of Science, Aim of Religion -- Scientific Illuminism.
#
# MECHANISM: the thinnest possible entry point. All judgement lives
# in Server and the handlers; this module only announces the POC,
# runs the event loop, and treats Ctrl-C as a clean shutdown rather
# than a crash -- a daemon the founder stops with a keystroke should
# bow, not traceback.
# DOCTRINE: this is the Proof-of-Concept phase and the startup line
# says so in the open, on bleats.local, per the brief's order that
# the prototype be marked as a prototype wherever it presents
# itself.
# ---------------------------------------------------------------------

import asyncio

try:
    from .server import Server
except ImportError:  # pragma: no cover - run as a loose file
    from ircd.server import Server


def main() -> None:
    """Build the Server, announce it, and serve until interrupted."""
    server = Server()
    print(
        "bleats-ircd POC listening on 127.0.0.1:6667 "
        f"(server {server.config['server_name']}, "
        f"network {server.config['network']}, "
        f"{server.config['version']}) -- "
        "Prototyping the Proof of Concept phase.",
        flush=True,
    )
    try:
        asyncio.run(server.start("127.0.0.1", 6667))
    except KeyboardInterrupt:
        # Graceful by design: Ctrl-C is an order, not an accident.
        print("bleats-ircd: shutdown requested, closing.", flush=True)


if __name__ == "__main__":
    main()


# 93 -- Live, Love, and let Love, Live.
