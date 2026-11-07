# The House IRCd — Custom Daemon Specification

**Dictated:** Saturday, November 7, 2026 (America/Detroit)
**Authorship:** Johnathan 'Qasparr' Monroe, ARR — All Rights Reserved, Without Prejudice
**Status:** Design specification, founder's dictation. The daemon's name is not yet coined — his pen.

## His dictation, verbatim

> "So when we implement the ircd which i want to make a custom ircd that is
> like bahamut and unrealircd hybrid, bahamut with channel nick and ircop
> services embedded into it. With halfops, etc.@%+v"

Desk reading, stated for his pen to strike: "channel nick and ircop services"
is read as the three service families — **nick services, channel services, and
IRC-operator services** — all embedded in the daemon.

## The design in one line

A Bahamut spine wearing UnrealIRCd's feature set, with the services living
**inside the daemon** instead of running as a separate package beside it.

## From Bahamut (the spine)

- Proven stability under mass connection counts — the DALnet lesson: the
  daemon's first virtue is not falling over.
- Disciplined server-to-server protocol: timestamped bursts, clean linking,
  nick/channel collision handling that favors the older claim.
- Operator tooling built for a working network: K-lines and their kin,
  server-side bans with reasons and expiries.
- A protocol designed from the start to cooperate with services — here the
  cooperation is internal, because the services are in the same house.
- **Multi-target commands at full strength** (founder's question,
  2026-11-07): the KICK command takes a comma list — one line,
  `KICK #chan user1,user2,user3,user4,user5 :reason`, executed in order,
  one named channel applying to every listed user (RFC 2812 list form;
  channel and user lists pair off when both are listed). Same for
  stacked MODE lines (`+oooo`, `-bbbb` in a single line). The per-line
  cap is the daemon's own setting (advertised in TARGMAX); the house cap
  is set generously, the number reserved to his pen — the war-script
  economy depends on it: one line costs one flood penalty, not five.

## From UnrealIRCd (the feature set)

- **Halfops** — named by the founder.
- The extended channel ladder above op: channel admin and channel owner
  tiers, with their own prefixes (desk reading of his "etc.": the full
  ladder is in; his pen can cut rungs).
- Rich channel modes in the Unreal manner (flood control and friends) —
  specific modes beyond halfop are desk-tier until he rules them one by one.
- Snomasks and fine-grained operator notices.

## Embedded services (in-tree, not a side package)

No Anope, no Atheme, no separate services process. One daemon, one config,
one state:

- **Nick services** — registration, identify, recovery by the member's own
  credentials. A nick is a member's name in the house; the registry is a
  house record, kept under the Constitution.
- **Channel services** — channel registration, founder/successor, access
  lists that map onto the prefix ladder below, topic retention, entry
  messages, kick/ban automation at the channel owner's word.
- **IRC-operator services** — the IRCop desk: network bans (AKILL-class),
  server management, global notices, abuse handling. IRCops are house
  officers; their powers are logged to the house record (transparency
  toward power, per THE LINE).
- **Host services (the vhost desk)** — assigns and activates the IRC vhost:
  the ghost-alias hostname. This is where the Shepherd tier's vhost good is
  delivered: on identify, the member's cloak replaces their raw host.

## The prefix ladder

| Prefix | Mode | Rank |
|--------|------|------|
| `~` | +q | Channel owner |
| `&` | +a | Channel admin |
| `@` | +o | Channel operator |
| `%` | +h | Half-operator |
| `+` | +v | Voice |

The founder's dictation names `@ % + v` and "etc."; the `~` and `&` rungs are
the Unreal side of the hybrid, included by desk reading and marked for his pen.

## Network policy — the founder's rulings (2026-11-07)

Dictated the same sitting, in his words where quoted:

1. **The Twin Synergy Telecommunications Constitution IS the network
   policy.** No second rulebook grows beside it.
2. **Incognito flag for IRCops.** An oper may run incognito if they wish —
   an oper-hidden mode (the Unreal +H class): no oper status, oper host,
   or oper line shown to the network; on the wire they are a regular user.
3. **Channel wars are ENCOURAGED.** "Our network will encourage the old
   channel wars of dalnet instead of discouraging them." The network does
   not police channel rivalry.
4. **File sharing is fully allowed:** "Full DCC and FServe and XDCC file
   sharing etc will be allowed." No CTCP filtering, no file-culture rules.
5. **The only prohibitions: DDoS and mass botting.** Desk reading, marked:
   XDCC/FServe service bots are not "mass botting" — the ban is on bot-mass
   used as a weapon (floods, join storms, takeover swarms), not on bots
   that serve.
6. **A channel bot is offered to every channel** against takeovers — a
   house guard bot, there if the channel wants it.
7. **First come, first served.** "If you don't register the channel and
   the channel empties and someone else registers it, that's a fair
   takeover, we will not help with this issue." Registration is the
   channel founder's own duty; an unregistered channel is unowned ground,
   and the house does not restore what was never claimed. Desk reading,
   marked: the guard bot defends registered channels against force
   (floods, hostile snatches); it does not resurrect lapsed channels —
   rule 7 governs those, and the house's answer there is final: no help.
8. **IRCops and server staff are IMMUNE to channel power** (founder's
   ruling, 2026-11-07): channel modes and commands — KICK, BAN, mute/quiet
   bans, deop and mode-strips — simply do not take effect on them, so
   they can do their duties without interference. Scope, by the ruling's
   own terms: the immunity runs against *channel*-level actors. It is
   not immunity from the house — server-level authority (a superior's
   KILL, the *-lines, services) and the ledger bind opers exactly as
   before. Desk design, marked: a failed attempt on an incognito oper
   fails *quietly* — a generic no-effect, never a message announcing
   that the target is staff — so the shield does not blow the incognito
   it protects.

## House law the daemon is built under

- **No logs, no telemetry** (Twin Synergy Constitution; THE LINE). The
  services keep only what registration itself requires — a nick record, a
  channel record — because the member created it. Nothing is kept to sort,
  score, or sell.
- **Transparency toward power:** IRCop actions (bans, kills, jupes) are
  written to a house record the membership can inspect. Privacy toward the
  person; the ledger faces the officers, not the members. Desk
  reconciliation with the incognito ruling — **confirmed by the founder's
  word, 2026-11-07 ("No that is correct")**: incognito governs the wire,
  not the record — an incognito oper is invisible *as an oper* to the
  network, but their official acts still enter the ledger.
- **Identity (desk proposal, his pen):** SASL EXTERNAL / certificate
  fingerprint login, so a member's nick can bind to their own keypair —
  the self-founded primitive of this house: the public key IS the identity,
  the nick a local alias over the key. Password identify remains as the
  fallback road, never the only road.
- **Tier hookup:** vhost activation is an entitlement check against the
  member's tier (Shepherd and above carry the IRC vhost good). Billboard
  and Herd members chat with raw hosts; the daemon is where the tier table
  becomes real.

## Repository and the TABVLA stats showcase (dictated 2026-11-07)

- **Repository: `bleats-ircd`** (his words: "'bleats ircd' repository") —
  the daemon's home when coding starts: source, **docs and apps**.
- **Analytics and diagnostic reporting of stability:** the project carries
  a **TABVLA showcase page** of the network's IRC statistics — user and
  channel counts, message flow, link state, uptime, restarts, lag — every
  figure pointing to its numbers, per TABVLA's own doctrine: *a figure
  that cannot point to its numbers does not ship.* Desk note, consistent
  with the ratified incognito rule: the page shows aggregates only —
  incognito opers are counted, never named.
- **The client is a separate project** — `bleatsirc` — specced in
  `BLEATSIRC-CLIENT-SPEC.md`. The daemon repo never swallows the client,
  and the client never pretends to be the daemon.

## Doctrine format (standing order, restated by him 2026-11-07)

All features and projects of this house follow the **Doctrine format** —
the thelemic + educational annotation convention on every source file —
with **ultra-verbose I/O where necessary**: diagnostics, the stats
pipeline, and oper tooling narrate what they are doing, step by step,
never silently.

## Open seams — reserved to his pen

1. The daemon's name (coinage is his alone).
2. Whether the `~` and `&` rungs stand.
3. The Unreal channel-mode list, ruled mode by mode.
4. The services database custody standard (encryption at rest, backup,
   member export/deletion on request).

---

*Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights
Reserved, Without Prejudice. Right of claim hereby reserved and coined under
the authority of the Living Man.*

93 — Live, Love, and let Love, Live.
