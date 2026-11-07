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

---

*Brick I ends. Brick II — The Kill Family — follows: KILL, KLINE,
GLINE, ZLINE, DLINE, each under the same anatomy.*

Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights Reserved, Without Prejudice. Right of claim hereby reserved and coined under the authority of the Living Man.

93 — Live, Love, and let Love, Live.
