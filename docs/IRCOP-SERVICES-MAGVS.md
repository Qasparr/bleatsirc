# THE IRCOP SERVICES — A TEACHER'S REVISION (MAGVS) COMPANION

## The Operator's Craft, Deep-Dived: K-Lines, Kills, Jupes, and the Services That Held the Net

*A Scientific Illuminist treatment of power on the Internet Relay Chat protocol.*

**Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice)**
VII day of November, Dies Saturni, Sol in Scorpio, Anno V:xii e.n. (2026 e.v.)

**Classification:** Enterprise • Educational • Research & Development
**Method of Science, Aim of Religion**

Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights Reserved, Without Prejudice. Right of claim hereby reserved and coined under the authority of the Living Man.

---

## §I — What this companion is

The RFC 1459 Teacher's Revision (its parent volume, in the same docs
area) deep-dives the protocol as written. This companion deep-dives the
protocol **as wielded**: the operator's toolkit — the OPER command and
the O-line that feeds it, the kill family, the *-lines (K, G, Z, D), the
services-side enforcements the DALnet generation called OperServ, the
server powers (SQUIT, CONNECT, JUPE, REHASH), and the voices of power
(WALLOPS and its kin).

Much of this craft **is not in RFC 1459 at all.** The K-line grew out of
ircd configuration practice; the AKILL is a DALnet services invention;
the GLINE is EFnet lineage. A student who reads only the RFC will never
learn the tools that actually governed the networks. So this book keeps
the parent volume's anatomy — the text or the practice, the wire trace
in ultra-verbose I/O, the **full six inquiries** (Who, What, Where,
When, Why, How), the teaching essay, the four elements — and widens the
strata:

- **[1459]** — written in the RFC itself.
- **[DAEMON]** — the practice of the great daemon lineages: Bahamut,
  Hybrid, UnrealIRCd.
- **[SERVICES]** — the services packages (DALnet's, Anope, Atheme) where
  the tool actually lived.
- **[HOUSE]** — how this house's embedded services run the tool under
  the founder's ratified rulings: incognito on the wire, every official
  act in the house ledger, and only two capital crimes on the network —
  DDoS and mass botting.

## §II — The brick plan

- **Brick I — The Oper Himself** *(this brick)*: OPER, the O-line, oper
  modes, the incognito flag.
- **Brick II — The Kill Family**: KILL, KLINE/UNKLINE, GLINE, ZLINE,
  DLINE — local blades and network-wide ones.
- **Brick III — Services-Side Enforcement**: AKILL and its expiry,
  SHUN, session limits, exception lists — OperServ's desk.
- **Brick IV — Server Power**: SQUIT, CONNECT, JUPE, REHASH, DIE,
  RESTART — the dangerous drawer, and why it is locked.
- **Brick V — The Voice of Power**: WALLOPS, GLOBOPS, CHATOPS, LOCOPS,
  the services GLOBAL — who may speak to everyone at once.
- **Brick VI — Judgment & the Record**: the abuse cases of the DALnet
  era, what power did when nobody logged it, and the house's answer —
  the ledger, transparency toward power, privacy toward the person.

---

# BRICK I — THE OPER HIMSELF

## Event: OPER — the taking up of power [1459 §4.5]

**The text:** `Command: OPER · Parameters: <user> <password>` — and its
two verdicts in the parent volume's tables: 381 RPL_YOUREOPER,
`":You are now an IRC Operator"`, and 491 ERR_NOOPERHOST,
`":No O-lines for your host"`.

**On the wire:**
```
C→S  OPER qasparr <password>
S→C  :irc.house 381 Qasparr :You are now an IRC Operator
S→C  :Qasparr MODE Qasparr :+oHs        ← the crown, and its shadow:
                                           o = operator, H = hidden,
                                           s = seeing the snomask feed
```

**The six inquiries.** **Who:** a user whose host matches an O-line and
who holds its password — power on IRC was never granted by the network
at large, only *configured into a server* by the human who runs it.
**What:** a state change, not a message: the user acquires the oper
flag (+o) and with it every blade in Bricks II–V. **Where:** any time
after registration; the flag rides the user record until they disconnect
or an oper removes it. **When:** at the moment of authentication — and
note what authenticates: not the nick, but the **host plus password**;
491 exists because the protocol asks "are you connecting from a place
we trust, holding a word we chose?" **Why:** a federated anarchy still
needs sheriffs; OPER is how a server deputizes without a central
authority — each server its own O-lines, each network a patchwork of
trust. **How:** the server matches the connection's host against its
O-line list, checks the password (in the old world, DES-encrypted in
the config; in the living world, hashed or certificate-bound), sets the
flag, announces 381, and — on any competently run net — tells the other
opers, through the snomask feed, that power has been taken up, by whom,
from where.

**The teaching.** OPER is the most honest command in the protocol: it
pretends to nothing. It does not say the oper is wise, or elected, or
good. It says: *this server's owner wrote a line in a file, and this
person matched it.* Every legitimacy IRC power ever had was built on
top of that line by culture — by opers who answered abuse reports, who
showed up, who were known. And every abuse grew in the same soil: the
O-line answers to no one but its author. The student should hold both
truths at once, because the whole of Brick VI is their war.

**Four elements.** *Inputs:* an O-line name and password, from a host.
*Process:* host match, credential check, flag set, peer announcement.
*Outputs:* 381 and the flag — or 491, or 464 ERR_PASSWDMISMATCH for the
wrong word. *Tolerances:* must refuse silently-logged failure as a
design goal — a failed OPER attempt is exactly the event a snomask feed
exists to report; a server that hides failed deputizations from its own
opers is hiding the sound of someone trying the door.

## The O-line — a constitution in one line of config [DAEMON]

**What it is:** a line in the server's configuration file —
operator name, password (encrypted), the hostmask allowed to use it,
and the privilege flags this particular oper carries (local kill only,
global kill, K-line authority, server powers…). Bahamut, Hybrid, and
Unreal all kept the pattern; Unreal grew it into the richest dialect,
with per-oper flag sets that read like a table of ranks.

**The six inquiries, compressed as the object deserves.** **Who** writes
it: the server's owner, alone — the one unlogged act of power in the
whole system, and the root of all the others. **What:** a standing
pre-authorization: power defined *before* it is exercised. **Where:** on
disk, in the config, reloaded by REHASH (Brick IV). **When:** at
configuration time, not at crisis time — which is the entire discipline:
the network decides in calm who may act in storm. **Why:** because
mid-incident credentialing is how coups happen. **How:** hostmask +
secret + flags; the OPER command is merely the line, knocking.

**The teaching.** The O-line is the protocol's quiet answer to the
question every community eventually faces — *who watches, and who chose
them?* Its answer is feudal, and it worked for thirty years at scales
no startup survives. The house keeps the pattern and changes the
lighting: in the embedded services, the O-line's equivalent is a house
record, and its *exercise* — though never its holder's wire presence —
is ledgered (Brick VI).

## Oper modes and the snomask feed [DAEMON]

**The crown's wardrobe.** Taking up +o is only the first letter. The
daemon lineages grew an alphabet around it: **+H** — hidden oper, the
incognito flag (Unreal's form of it; other lineages spell the trick with
+C or server-specific cloaks): the oper's status, oper-host, and
oper-only WHOIS lines are suppressed for non-opers. **+s** — the
snomask subscription: instead of one firehose of server notices, the
oper subscribes to *classes* — connects and quits, kills, OPER attempts
failed and successful, flood reports, each class a letter. Power that
cannot see is decoration; the snomask feed is how an oper actually
perceives the network — ten thousand small events an hour, filtered to
the classes their duty needs.

**The six inquiries (for +s, the feed).** **Who:** the server speaks;
opers who subscribed, listen. **What:** structured notices, classed by
letter. **Where:** outside channels entirely — a private wire from the
daemon to its officers. **When:** continuously. **Why:** because the
alternative is opers flying blind or drowning; classes are the
compromise perception allows. **How:** the daemon formats, classes, and
routes; the client (Brick: the parent volume's event model) renders —
in bleatsirc, snomask classes are bridge events like any other, and an
oper's scripts may watch the feed in any language.

## The incognito flag — the founder's ruling [HOUSE]

The founder has ruled for this house (2026-11-07, ratified the same
sitting): **IRCops may run incognito if they wish** — +H or its house
equivalent, offered to every oper as a right of the office, not a favor.
And its reconciliation, confirmed by his word: **incognito governs the
wire, not the record.** On the wire, an incognito oper is a regular
user — no crown shown, no oper-host, no target painted. In the house
ledger, their official acts — every kill, every line, every jupe — are
entered under their name, inspectable by the membership the
Constitution serves.

The teaching writes itself, and it is the founder's whole doctrine of
power in one flag: **privacy toward the person — even the officer;
transparency toward the power — even when the officer is private.** The
old networks chose, variously, neither. This house chooses both, on
purpose, and has written it here so the choice cannot quietly un-happen.

## The shield of the office — immunity from channel power [HOUSE]

The founder's ruling, same sitting: **IRCops and server staff are
immune to channel modes and commands — KICK, BAN, and their kin — so
they can do their duties without interference.**

The precedents are older than the ruling. Services and U-lined servers
were always immune — no one kicks ChanServ — and Unreal's line gave the
channel owner (+q) a lesser form of the same armor against kicks. The
house extends the principle to its officers in person, because the
alternative is absurd on its face: an oper who enters a channel to stop
a mass-botting swarm cannot be *ejected by the swarm's channel bot* in
the middle of the duty.

**The shape of the shield.** Channel-level power does not take effect
on staff: kicks do not remove them, bans (including quiet/mute bans) do
not silence or exclude them, deops and mode-strips aimed at them fail.
Channel wars rage exactly as encouraged — around the oper, never *on*
the oper. And the shield has a deliberate seam, stated here so no future
officer mistakes its size: **it is immunity from channels, not from the
house.** A superior's KILL still lands. The *-lines still bind. The
ledger still records. The Constitution that arms the oper against the
channel is the same one that keeps the oper answerable — the shield
faces outward, toward interference, never upward, toward judgment.

**The incognito seam (desk design, marked).** When a channel command
is attempted on an incognito oper, it fails *quietly* — a generic
no-effect, indistinguishable from any other failed mode — never with a
message announcing that the target is staff. A shield that announced
itself would be a beacon, and the incognito ruling would be a dead
letter the first time a channel tried to kick the quiet stranger who
wouldn't leave.

## The proxy hand — the IRCopBot [HOUSE]

The founder's addition, same sitting: **an IRCopBot that incognito
opers — his word for them is *incognito troopers* — can use to do their
drop duties through, like a proxy bot.**

The problem it solves is written into the two rulings before it.
Incognito keeps the oper invisible; enforcement makes them visible —
every kill has an author, every K-line a signature, and a trooper who
must sign their work in public is incognito in name only. The IRCopBot
severs the act from the actor *on the wire*: the oper directs privately;
the bot — a services pseudoclient of the U-lined class, immune as
services have always been — executes in the open under its own name.

**On the wire:**
```
oper→bot (private)   DROP SWARM #lobby  (12 clones, one /24, joining in waves)
bot→#lobby           :IRCopBot MODE #lobby +mi
bot→S                KLINE *@203.0.113.0/24 :Automation used to flood — case 114
                     ← on the wire, the hand is the bot's.
                     ← in the ledger: "KLINE …/24 — directed by <oper>,
                        case 114, reason stated, duration 24h."
```

**The six inquiries.** **Who:** authenticated opers direct; the bot
acts; the network sees the bot. **What:** the enforcement repertoire of
Bricks II–III — kills, *-lines, mode enforcement, swarm drops — issued
as private commands and executed as services actions. **Where:** the
bot sits in the embedded services, beside the IRCop desk of the daemon
spec; direction arrives by private message or the oper-only command
wire, never in public channels. **When:** on direction — the bot holds
**no initiative of its own**; it is a hand, not a will. (Whether
pre-authorized automatic responses — a flood threshold that drops first
and reports after — should ever be granted is an open seam, reserved to
the founder's pen; the default is direction only.) **Why:** because the
incognito ruling and the enforcement duty collide, and the house
refuses to sacrifice either. **How:** oper-grade authentication — in
this house, the oper's keypair (certfp) alongside the O-line credential;
the direction is **written to the ledger before the act executes**, so
no act exists whose authorship the record cannot produce; the bot
reports back to the directing oper in full, ultra-verbose — what was
done, on whom, with what effect.

**The teaching, and it is the sharpest one in this brick:** a proxy
concentrates temptation. The same severance that protects a trooper's
safety could, in a lesser house, protect an abuser's conscience —
*the bot did it* is the oldest excuse wearing new clothes. The house's
answer is architectural, not rhetorical: **the wire forgets the oper;
the ledger never does.** Attribution is not destroyed by the proxy; it
is *moved* — from the public square, where it endangers, to the house
record, where it judges. An act the ledger cannot attribute does not
execute at all. That is the whole design, and Brick VI will weigh it.

## The Duties of the IRCop — the Constitution is the whole of the law [HOUSE]

*Added at the founder's order, same sitting: the companion must explain
the duties of the IRCops, their main focus being the Twin Synergy
Telecommunications Constitution. It stands here, at the end of the first
brick, because a duty belongs with the office that carries it.*

An IRCop of this house has one law above every tool in Bricks II–V:
**the Twin Synergy Telecommunications Constitution.** The tools are
means; the Constitution is the focus. Its first law is the office's
first duty: **the user is above all** — the user is sovereign; the
company, and therefore its officers, are **fiduciary**, bound to act for
the user's benefit and no other's. From that root, the duties grow:

1. **Serve the member, never the crown.** Every act of power must name
   the member it protects. An act that protects only the oper's pride,
   the network's vanity, or the office itself has no warrant and is not
   to be done.
2. **Carry the duty multiplied with the right.** Under the Handshake
   Clause (Oz×Duty), no right exists in this house severed from its
   duty — least of all an oper's. The kill, the line, the jupe: each is
   a right that arrives *multiplied by its duty*, and exercised without
   the duty — without reason, without record, without restraint — it is
   void as house law, whatever the daemon permits.
3. **Enforce the two capital crimes, and only those.** DDoS and mass
   botting. That is the whole criminal code of the wire. Everything
   else — channel wars (encouraged by policy), file sharing by DCC,
   FServe, and XDCC (allowed in full), rivalry, mockery, offense — is
   the members' country. The oper who polices beyond the two crimes has
   left the Constitution, however good their intentions were.
4. **Practice the duty of restraint.** Where the Constitution gives no
   warrant, the oper's duty is to *not act* — and the standing case is
   the lapsed channel: unregistered, emptied, fairly taken. **We will
   not help** is not indifference; it is a constitutional duty, owed
   equally to the one who lost the channel and the one who claimed it.
   The office that intervenes there serves neither — it serves itself.
5. **Guard the wire; never read it.** No logs. No telemetry. No
   inspecting the members' traffic to sort, score, or sell — or to
   satisfy curiosity, which is the same sin in a smaller hat. What is
   not kept cannot be taken, and what the oper never saw can never be
   used against the person who sent it. Public is public; private is
   private; the line does not cross.
6. **Be a common carrier, not a censor.** The house carries the signal.
   Content, viewpoint, taste, and doctrine are not enforcement
   categories — the members' speech is theirs, including speech the
   oper despises. The two capital crimes are acts against the *wire*,
   never against *words*.
7. **Wear the incognito if you wish; enter the ledger always.** The
   oper's privacy is protected as any person's (privacy toward the
   person). The oper's *acts* belong to the record the membership may
   inspect (transparency toward power). An official act kept out of the
   ledger is unconstitutional on its face — not because it was
   necessarily wrong, but because the house cannot weigh what it cannot
   see.
8. **Fail closed.** No justification, no action — the office of this
   house (Oz×Duty + TRVVTH) applied to power: where the constitutional
   warrant for an act cannot be stated, the act does not happen, and
   the doubt resolves in the member's favor, every time.
9. **Teach with every enforcement.** This is an educational enterprise
   under the Method of Science. A kill or a line lands with its reason
   stated in plain words — what rule of the two, what evidence, what
   duration, what appeal. Power that explains itself builds the
   network's judgment; power that doesn't only builds its fear.
10. **Hold the guard bot as an offer, never a garrison.** The house
    offers every channel its guard bot against takeover by force. A
    channel that declines it has exercised the same sovereignty the
    office exists to protect. The duty is the offer, kept standing —
    not the occupation.

**The six inquiries, for the office itself.** **Who:** any member
deputized by O-line under the parent volume's rules. **What:** a trust,
not a rank. **Where:** everywhere the wire runs, and nowhere the
Constitution does not reach — which is to say the reach and the limit
are the same line. **When:** on duty, the focus does not lapse; an oper
is fiduciary in their sleep, because the ledger does not sleep.
**Why:** because a network that encourages channel wars, allows the
whole file culture, and refuses to log its people *requires* officers
whose restraint is constitutional rather than temperamental — freedom
this wide is only survivable if power this strong is this bounded.
**How:** by the ten duties above, weighed on TRVVTH, recorded in the
ledger, and answerable to the membership the Constitution serves.

---

# APPENDIX A — THE COMPLETE IRCOP COMMAND REGISTER

*Added at the founder's direct question, 2026-11-07: the full list of
IRCop commands and what they do, in one place. The bricks deep-dive each
family under the full anatomy; this register is the complete map — no
command of the office left off it. Scope tags: **L** local server ·
**N** network-wide · **S** services-side. Strata as throughout:
[1459] · [DAEMON] · [SERVICES] · [HOUSE].*

## Becoming, and seeing like an officer

- **OPER** [1459] — Authenticate against an O-line and take up the oper
  flag. The door to everything below. (Brick I.)
- **SNOTICE / +s snomasks** [DAEMON] — Subscribe to classes of server
  notices: connects, quits, kills, failed OPER attempts, flood reports.
  Perception, not power — and the precondition of every sane act.
- **LOCOPS** [DAEMON] — Message to the opers of this server only.
- **TRACE** [1459] — Trace the server path to a user or server;
  exposes the link tree to an officer tracing floods or splits.
- **STATS** [1459] — Interrogate a server's tables by letter: its
  *-lines (the q/o/l letters read the ban and oper tables), uptime,
  connection counts, command usage. The officer's census.
- **LINKS** [1459] — List the network's server links; opers see the
  unmasked map users are denied.
- **ADMIN** [1459] — A server's administrative identity and contact;
  the address to which abuse of that server is reported.

## The kill family

- **KILL** [1459] **N** — Disconnect a user, with a reason that carries
  the path of servers it crossed. The personal blade: one user, now.
- **KLINE** [DAEMON] **L** — Ban a user@host mask from *this* server,
  written to its config; Bahamut's temporary form takes a duration and
  expires itself. **UNKLINE** removes it.
- **GLINE** [DAEMON] **N** — The K-line's network-wide elder: a
  host-mask ban propagated to every server. **UNGLINE** removes.
- **ZLINE** [DAEMON] **L** — Ban an IP (or CIDR) *before registration*:
  the connection is refused at the door, no nick ever spoken. For
  botnets whose users never become users.
- **DLINE** [DAEMON] **L** — The hybrid-lineage IP deny; ZLINE's cousin
  from the ircd-hybrid/ircu side of the family.
- **AKILL** [SERVICES] **N** — Autokill: a services-held hostmask ban
  with mandatory expiry and reason, enforced by every server on
  connect. DALnet's workhorse against clones and flood bots; its
  removal twin travelled as RAKILL in the early services.
- **SHUN** [DAEMON] **N** — The silencing: the user stays connected and
  sees the network, but every command is swallowed — they can speak to
  no one, join nothing, do nothing. For abusers whose data you still
  want visible to themselves as consequence. **TEMPSHUN** is its
  join-scoped, minutes-long form, usable by lesser flags.

## Silencing, filtering, and the channel instruments

- **SPAMFILTER** [DAEMON] **N** — Unreal's regex engine over messages
  and actions: match text, then block, kill, or *-line the sender, per
  the rule. Power and hazard in equal measure (Brick III weighs it).
- **SAMODE** [DAEMON] **N** — Services-admin mode change on any channel
  or user, overriding channel rank entirely.
- **SAJOIN / SAPART** [DAEMON] **N** — Force a user into, or out of, a
  channel, by services authority.
- **SANICK** [DAEMON] **N** — Force a user's nick change (freeing a
  collided or abusive nick without killing the person holding it).
- **CHGHOST / CHGIDENT / CHGNAME** [DAEMON] **N** — Rewrite a connected
  user's host, ident, or realname, live — the discreet alternative to
  killing them for a bad vhost.
- **SETHOST / SETIDENT** [DAEMON] **L** — The oper-facing forms: set a
  (or one's own) visible host/ident.
- **OPEROVERRIDE** [DAEMON] — Not a command but a chartered privilege:
  join through +i, +b, +k, +l; the officer's master key to channels,
  exercised under Brick VI's judgment rules. In this house it is bounded
  by the immunity chapter above: staff need no override to *enter*
  force — channel power simply does not move them.
- **CLEARMODES** [SERVICES] — ChanServ/OperServ clearing of a channel's
  modes and bans in one act — the takeover fire-axe.
- **AKICK** [SERVICES] — A channel's standing auto-kick list, held by
  channel services: the mask that is kicked on sight, every sight.

## Server power — the dangerous drawer

- **SQUIT** [1459] **N** — Sever a server's link to the network, with a
  reason. Amputation as an instrument: for a compromised or desynced
  server, there is no lesser tool.
- **CONNECT** [1459] **N** — Order a server to link to another named
  server; the surgeon's counterpart to SQUIT.
- **JUPE** [SERVICES] **N** — *Jupiter* a name: place a fake, blocking
  presence on a server, nick, or channel so the real one cannot link,
  register, or be used — for holding a compromised server's name out of
  the merge until its owner returns.
- **REHASH** [1459] **L** — Reload the server's configuration — O-lines,
  *-lines, limits — without dropping a single user. How calm edits
  become live law.
- **RESTART** [1459] **L** — Restart the daemon in place; the network
  holds its breath for seconds.
- **DIE** [1459] **L** — Shut the server down entirely. In 1459 it sits
  in the text unguarded; the lineages learned to fence it with flags,
  passwords, and fear. Brick IV tells why.

## The voices of power

- **WALLOPS** [1459] **N** — A message to every oper on the network
  (and, in the old form, every +w user): the officer's public address.
- **GLOBOPS** [DAEMON] **N** — The DALnet/Unreal global oper wall:
  opers only, network-wide, faster and narrower than WALLOPS.
- **CHATOPS** [DAEMON] **N** — Bahamut/DALnet's oper chat wall — the
  informal channel of the officer corps, distinct from GLOBOPS'
  announcements.
- **GLOBAL** [SERVICES] **N** — OperServ's notice to *every user on the
  network* — maintenance warnings, emergency word. The loudest voice
  the services own; governed by Duty 9 (teach) in this house.

## The services desk (OperServ and kin)

- **SESSION / EXCEPTION** [SERVICES] — OperServ's connection governor:
  cap simultaneous sessions per host; hold the exception list for hosts
  chartered to exceed it (schools, bouncers, shells). The quiet tool
  that made clone wars expensive before they started.
- **SVSHOLD** [SERVICES] — Hold a nick in services custody, unusable by
  anyone, pending judgment.
- **OS OPER / OS ADMIN lists** [SERVICES] — The services' own officer
  roster — who may command OperServ itself — kept separate from the
  daemons' O-lines, because the services are a second seat of power and
  keep their own roll of it.
- **RAW** [SERVICES] — OperServ emitting a raw protocol line as if it
  were a server. The single most dangerous services command ever
  shipped; most networks compiled it out. It stands in this register
  for completeness and as a warning — the house does not ship it.
- **UPDATE / RELOAD / SHUTDOWN** [SERVICES] — The services process's own
  lifecycle commands, for services admins: flush databases, reload
  config, stop the services. Small commands, constitutional weight —
  whoever holds them holds NickServ's memory itself.

## The house instruments [HOUSE]

- **IRCopBot direction** — The incognito trooper's proxy hand (Brick I):
  the full enforcement repertoire above, directable in private, executed
  under the bot's name; every direction ledgered, with its directing
  oper, before the act.
- **The channel guard bot** — Offered to every channel against takeover
  by force (policy rule 6); a member instrument, not an officer's.
- **The ledger** — Not a command but the office's memory: every official
  act, its actor, its reason, inspectable by the membership. If a tool
  in this register is ever used in this house, its use is *here*.

*End of Appendix A. Where a lineage spells a command differently
(Hybrid's DLINE beside EFnet's GLINE, and their kin), the register
carries the major forms; the bricks arbitrate the spellings at their
boundary, per the Zero-Point Directive.*

---

*Brick I ends. Brick II — The Kill Family — follows: KILL, KLINE,
GLINE, ZLINE, DLINE, each under the same anatomy.*

Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights Reserved, Without Prejudice. Right of claim hereby reserved and coined under the authority of the Living Man.

93 — Live, Love, and let Love, Live.
