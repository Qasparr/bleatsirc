# RFC 1459 — TEACHER'S REVISION (MAGVS)

## The Internet Relay Chat Protocol, Deep-Dived: Every Numeric, Every Event

*A Scientific Illuminist treatment of the protocol that carried a generation.*

**Authorship attributed exclusively to Johnathan 'Qasparr' Monroe (Greek, -ARR, All Rights Reserved, Without Prejudice)**
VII day of November, Dies Saturni, Sol in Scorpio, Anno V:xii e.n. (2026 e.v.)

**Classification:** Enterprise • Educational • Research & Development
**Method of Science, Aim of Religion**

Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights Reserved, Without Prejudice. Right of claim hereby reserved and coined under the authority of the Living Man.

---

## §I — What this book is, and why

RFC 1459 (Oikarinen & Reed, May 1993) is a spare document. It names the
protocol's messages and assigns its numbers, and then it stops — it tells
you *what* a numeric is and almost never *why it exists*, *when it fires*,
*what breaks without it*, or *what it looks like on the wire at 3 a.m. in a
netsplit*. The old hands learned those things by scars. This Teacher's
Revision exists so the next generation can learn them by reading.

Every command (here called an **event**, in the house's usage — each one is
an event in a client's life) and every numeric in the protocol receives a
full treatment: the RFC's own text, an annotated wire trace in
ultra-verbose I/O, the **full spectrum of inquiries** — Who, What, Where,
When, Why, How — and a teaching essay. Nothing in the original is struck;
where later practice (RFC 2812, and the living networks after it) extends
or corrects the 1993 text, the later stratum is **marked, never vanished**,
and labeled with its tier.

This book is also the founding document of the house's own protocol work:
the custom daemon and the bleatsirc client specced beside it are built
under the lessons recorded here, and each entry closes with its **house
hookup** — where the numeric or event lives in those designs.

## §II — Method

- **Strata.** Every entry carries one or more stratum labels:
  **[1459]** the 1993 text itself · **[2812]** the 2000 collation, which
  formalized practice 1459 left in prose · **[LIVING]** what real networks
  do now, where it differs. A disagreement between strata is reported at
  its boundary coordinates, per the Zero-Point Directive — never smoothed.
- **The six inquiries.** Each entry answers **Who** sends and receives it,
  **What** it carries, **Where** it lives in the connection's lifecycle,
  **When** it fires, **Why** the protocol needs it, and **How** it is
  produced, parsed, and handled. Where the evidence does not support an
  answer, the inquiry stands visibly open — it is never filled by invention.
- **Ultra-verbose I/O.** Each entry shows the message on the wire, raw,
  with direction and annotation: `C→S` client to server, `S→C` server to
  client, `S→S` server to server.
- **Four-element test.** Every entry states its Inputs, its Process, its
  Outputs, and its Tolerances (what the parser must accept and what it
  must refuse). An entry that cannot state all four is not finished.

## §III — The verified inventory (counted from the texts, 2026-11-07)

| Corpus | Count | Source |
|--------|-------|--------|
| Numerics tabulated in RFC 1459 §6 | **127** | extracted from the RFC text on file |
| Numerics tabulated in RFC 2812 §5 | **151** | extracted from the RFC text on file |
| Union of distinct numeric codes | **158** | collation of both tables |
| Codes present in 2812 but absent from 1459's tables | **31** | incl. 001–005, 325, 346–349, 437, 476–478, 484, 485 |
| Commands defined by RFC 1459 | **45** | its §4, by section |

**Collation finding, flagged at the front because it shapes the book:**
the famous welcome block, 001–004, **does not appear in RFC 1459's
tables at all.** The 1993 text describes registration in prose and begins
its numeric tables at the 200s. The welcome numerics lived on the wire by
convention for seven years before RFC 2812 §5.1 wrote them down. A reader
of 1459 alone would never learn the first four numbers every IRC client
on earth waits for. This is the Zero-Point of the whole collation, and it
is why a Teacher's Revision is necessary.

## §IV — The brick plan

The book is built in bricks, each brick a coherent country of the protocol:

- **Brick I — Registration & the Welcome** *(this brick)*: PASS, NICK,
  USER, QUIT · numerics 001–005, 431, 432, 433, 436, 451.
- **Brick II — The Server Confesses**: MOTD, LUSERS, VERSION, STATS,
  LINKS, TIME, ADMIN, INFO · numerics 200–219, 241–259, 261–266,
  371–376, 381–385, 391.
- **Brick III — Channel Country**: JOIN, PART, MODE, TOPIC, NAMES, LIST,
  INVITE, KICK · numerics 300–309, 311–319 (cross-filed), 321–329,
  331–333, 341–353, 361–369, 371–376, 401–476 (the channel errors).
- **Brick IV — Speech**: PRIVMSG, NOTICE, AWAY · numerics 301, 306,
  407, 411–414, 421, 431–436 (cross-filed).
- **Brick V — Knowledge of Persons**: WHO, WHOIS, WHOWAS, USERHOST, ISON
  · numerics 311–319, 330 (living), 352, 354 (living), 369, 401–406.
- **Brick VI — Power & the Wire's Edge**: OPER, KILL, PING, PONG, ERROR,
  SQUIT, CONNECT, TRACE, REHASH, DIE, RESTART, SUMMON, USERS, WALLOPS,
  SQUERY, SERVLIST, SERVER, SERVICE · numerics 381, 409, 411, 481–502,
  and the reserved/obsolete register of 1459 §6.3, collated in full.

---

# BRICK I — REGISTRATION & THE WELCOME

*The door of the network. Everything in this brick happens in the first
seconds of a connection, before the user has a name the network honors —
or it is the story of how they fail to get one.*

## Event: PASS — the password at the gate [1459 §4.1.1]

**The text:** `Command: PASS · Parameters: <password>` — and 1459's
standing rule: the PASS command **must** be sent before any NICK/USER
combination; a second PASS is error 462, ERR_ALREADYREGISTRED.

**On the wire:**
```
C→S  PASS s3cret-horse            ← before anything else; order is the law
C→S  NICK Qasparr
C→S  USER qasparr 8 * :Johnathan Monroe
```

**The six inquiries.** **Who:** the client, once, at the threshold; the
server judges silently — success has no numeric of its own, only the
welcome that follows. **What:** one password for the connection itself —
not for a nick; nick passwords belong to services, a layer 1459 does not
contain. **Where:** first position in the registration sequence; a PASS
arriving after registration is a category error, and the protocol says so.
**When:** before NICK/USER, or never. **Why:** because a network that
admits servers and clients by password needs the credential presented
before identity is claimed — first the key, then the name. **How:** the
server records the password against the connection attempt; mismatch is
usually answered not by a numeric but by ERROR and a closed socket
(464 ERR_PASSWDMISMATCH exists in the tables for servers polite enough
to send it).

**The teaching.** PASS teaches the protocol's deepest habit: **sequence
is semantics.** The same three messages in the wrong order are not a
registration; they are three errors. It also teaches the protocol's age:
the password crosses in cleartext, because in 1993 the wire was a campus
and the enemy was a classmate. Every later armor (SASL, TLS) is a patch
on this moment.

**Four elements.** *Inputs:* one password string. *Process:* position
check, then credential check. *Outputs:* silent state (password-accepted)
or ERROR/464. *Tolerances:* must accept being sent exactly once, first;
must refuse a second (462).

**House hookup.** In bleatsirc, PASS is emitted by the connection profile
before NICK/USER, visible in the raw window; in the house daemon it is
the outer gate only — member identity lives in the embedded nick
services, exactly the separation 1459 assumed.

## Event: NICK — the claiming of a name [1459 §4.1.2]

**The text:** `Command: NICK · Parameters: <nickname> [ <hopcount> ]` —
"used to give user a nickname or change the previous one. The <hopcount>
parameter is only used by servers… If supplied by a client, it must be
ignored."

**On the wire:**
```
C→S  NICK Qasparr
S→C  :irc.house 433 * Qasparr :Nickname is already in use   ← not this time
C→S  NICK Qasparr|desk
S→S  NICK Qasparr|desk 1 1717171717 +i qasparr shell.house * :Johnathan
       ← server-to-server form: hopcount, timestamp, modes, the works
```

**The six inquiries.** **Who:** every user at birth, and any user at any
later moment who wants a new name; servers relay the claim network-wide.
**What:** a nickname — 1459 allows letters, digits, and the special set
``[]\`_^{|}``- and caps it at nine characters, a limit the living networks
have stretched but never formally repealed. **Where:** second in the
registration sequence; afterwards, anywhere in the session, where it
becomes an event every shared channel witnesses. **When:** at
registration and at will thereafter — freestanding, unowned, first come
first served; *ownership* of a nick is a services fiction the base
protocol knows nothing about. **Why:** because a chat network addresses
people, and people need handles shorter than a hostmask and warmer than
a number. **How:** the server checks the claim against its collision
rules (431/432/433/436 below), registers or refuses, and bursts the
result to its peers with a timestamp — the timestamp being the
tiebreaker when two servers disagree, the seed of the whole TS doctrine
Bahamut was built on.

**The teaching.** NICK is where IRC's anarchic constitution shows: the
protocol grants names by occupation, not by right. Everything the
founder's network policy says about channels — register it or lose it,
first come first served, fair takeover — was true of nicks first, in
1988, in this one message. NickServ was invented precisely because this
message has no memory.

**Four elements.** *Inputs:* nickname, optional server-side hopcount.
*Process:* syntax check (432), presence check (431), collision check
(433/436), registration and burst. *Outputs:* silence-and-welcome during
registration; a network-wide NICK event after it. *Tolerances:* must
ignore a client-supplied hopcount; must not case-fold beyond the RFC's
own casemapping ({}| are lowercase []\, a fossil of Scandinavian ASCII).

**House hookup.** In bleatsirc the NICK event is the client's heartbeat
— the trigger engine's `on NICK` and the bridge event both fire from the
single parse. In the house daemon, embedded nick services give the claim
a memory (registration) without repealing the protocol's rule: an
unregistered nick is still only held by occupation.

## Event: USER — the declaration of the person [1459 §4.1.3]

**The text:** `Command: USER · Parameters: <username> <hostname> <servername> <realname>` —
1459's own confession rides inside: the hostname and servername
parameters "are ignored by the IRC server" when the command arrives from
a directly connected client; they exist for the server-to-server story.
Later strata compress the middle to `<username> <mode> *`.

**On the wire:**
```
C→S  USER qasparr 8 * :Johnathan 'Qasparr' Monroe
       └─ username └─ mode bits (8 = +i in the living reading)
                     └─ the realname: free text, may contain spaces,
                        travels at the end because it must
```

**The six inquiries.** **Who:** the client, once, completing
registration. **What:** a username (the machine-account name, the `~`
-less half of every hostmask), mode wishes, and the realname — the GECOS
field, the protocol's one act of biography. **Where:** last of the
registration triad; PASS and NICK may precede it in either order, USER
seals the file. **When:** once — after registration, ERR_ALREADYREGISTRED
(462); before it, most other commands earn 451. **Why:** a nick is a
handle, but the network also needs a stable-ish account name for
hostmasks, bans, and blame: `nick!user@host` is the protocol's full
name for a person, and USER supplies its middle. **How:** on receipt of a
valid USER after NICK (and PASS where required), the server flips the
connection from *unregistered* to *registered* and fires the welcome
sequence — 001 through 004, then the MOTD block (Brick II).

**The teaching.** USER is a museum of 1993 trust: it asks the client to
state its own username and realname, and believes it — ident (RFC 1413)
was the separate, half-hearted audit. The lesson the house takes: the
base protocol *identifies* nobody; all real identity is layered —
services, certificates, keys — which is why this house binds nicks to
keypairs at that layer and never pretends USER did it.

**Four elements.** *Inputs:* username, two vestigial fields, realname.
*Process:* completeness check, registration flip. *Outputs:* the welcome
burst. *Tolerances:* must ignore the middle fields from a direct client;
must accept a realname with spaces (it is the trailing parameter, and
the colon is load-bearing).

**House hookup.** bleatsirc builds USER from the member's profile and
shows it in the raw window in registration traces — the first thing a
student should read when learning the protocol is their own birth,
annotated.

## Event: QUIT — the leaving [1459 §4.1.6]

**The text:** `Command: QUIT · Parameters: [ <Quit Message> ]` — the
server closes the connection; every shared channel sees the departure
with the message attached, and a client that simply vanishes gets the
default epitaph of its disconnection (a ping timeout, a reset).

**On the wire:**
```
C→S  QUIT :93 — Live, Love, and let Love, Live.
S→C  ERROR :Closing Link: Qasparr (Quit: 93 — Live, Love…)
chan  :Qasparr!qasparr@host QUIT :93 — Live, Love, and let Love, Live.
```

**The six inquiries.** **Who:** the departing client; the server speaks
it to everyone who shared a room with them. **What:** an optional final
sentence — the only message in the protocol that is simultaneously a
command, a broadcast, and an obituary. **Where:** the end of the
lifecycle, mirror of registration. **When:** at will, once. **Why:**
because presence was announced (JOIN, NICK), absence must be too —
otherwise every channel keeps a ghost at the table. **How:** the server
marks the client gone, emits QUIT to all common channels, sends ERROR to
the departing socket, and bursts the removal to its peers.

**The teaching.** QUIT is why IRC feels inhabited: departure is a public
event with a byline. The quit message became a folk form — jokes,
verses, protests, last words — because the protocol gave every exit a
caption. Design lesson: any system that announces arrivals owes its
people announced departures.

**Four elements.** *Inputs:* optional message. *Process:* deregistration,
broadcast, close. *Outputs:* QUIT to witnesses, ERROR to the leaver,
socket closed. *Tolerances:* must function with no message at all; must
not be refused — there is no numeric that talks a client out of leaving.

**House hookup.** In bleatsirc, `on QUIT` is a first-class trigger with
the message parsed; the client's own default quit line is per-network
config, because a house that respects last words lets its members write
their own.

## Numeric 001 — RPL_WELCOME [2812 §5.1; absent from 1459's tables]

**The text:** `"Welcome to the Internet Relay Network <nick>!<user>@<host>"`

**On the wire:**
```
S→C  :irc.house 001 Qasparr :Welcome to the Internet Relay Network Qasparr!qasparr@shell.house
```

**The six inquiries.** **Who:** the server, to the newly registered
client — the first word of the welcome burst. **What:** the greeting and,
inside it, the client's full protocol name: nick, username, host — the
identity the network will use for them, stated once, authoritatively.
**Where:** the head of registration's output; nothing the client wants
to do is legal before it. **When:** the instant registration completes.
**Why:** a connecting program needs a machine-readable *you are in*
signal, distinct from MOTD prose and server notices; 001 is that signal,
the green light every client waits for before joining channels or
starting scripts. **How:** the server emits it as the first of 001–004;
clients key their "connected" state, their auto-join lists, and their
`on CONNECT` triggers to its arrival — 1459-era clients guessed; the
living convention made 001 the flag.

**The teaching.** 001 is the collation's Exhibit A: absent from the 1993
tables, yet for seven years every server sent it and every client
required it. The protocol on paper and the protocol on the wire were two
documents, and the wire was winning. A student learns to ask of every
specification: *what does the wire actually do?*

**Four elements.** *Inputs:* completed registration. *Process:* identity
assembly. *Outputs:* one line, identity stated. *Tolerances:* clients
must not require the sentence's exact wording — only the code is law;
the prose after the colon is weather.

**House hookup.** In bleatsirc, numeric 001 is the registry's exemplar:
dispatched by hash lookup, carrying connection context, firing
`numeric:001` to every subscribed script — and it is the event that arms
the client's autojoins, never the socket connect itself.

## Numeric 002 — RPL_YOURHOST [2812 §5.1]

**The text:** `"Your host is <servername>, running version <ver>"`

**The six inquiries.** **Who:** server to fresh client. **What:** the
server's own name and software version — its introduction of itself,
answering 001's introduction of you. **Where:** second in the burst.
**When:** with 001, always. **Why:** because a client (and an operator,
and a historian) should know whose house they are in and what vintage
the timbers are; version strings are how a network's heterogeneity is
measured. **How:** free prose with two embedded facts; sane clients log
it and parse it loosely if at all.

**The teaching.** 002 and 003 are the protocol's vanity and its honesty
in one breath: a server announcing its version is also announcing its
vulnerabilities to anyone listening — a 1993 innocence later networks
learned to trim. The tension between *identify your software* and *do
not gift-wrap your attack surface* starts here.

**Four elements.** *Inputs:* server identity and version. *Process:*
none — pure statement. *Outputs:* one line. *Tolerances:* wording is
wholly unstandardized; the code alone is contract.

**House hookup.** bleatsirc files 002 under the connection's identity
card in the UI — server name and version on the TABVLA stats page come
from this line and its Brick II cousins, never from a guess.

## Numeric 003 — RPL_CREATED [2812 §5.1]

**The text:** `"This server was created <date>"`

**The six inquiries.** **Who:** server to fresh client. **What:** the
compile/creation date of the server binary — its birthday. **Where:**
third in the burst. **When:** with the welcome. **Why:** in a federated
network rebuilt by hand on a hundred machines, knowing how old a binary
is tells an operator whether its behavior is doctrine or archaeology.
**How:** one date, embedded in prose; clients display or ignore.

**The teaching.** 003 is the smallest numeric in the book and the most
human: software remembering when it was made. It teaches that the early
network expected *people* to read these lines — the whole welcome burst
is written for a human at a terminal, and the machine-readable parts are
the codes, never the sentences.

**Four elements.** *Inputs:* the binary's build date. *Process:* none.
*Outputs:* one line. *Tolerances:* date format unstandardized by design
— which is itself the lesson.

**House hookup.** House daemons keep 003 and mean it: build provenance
is doctrine in this house (a figure that cannot point to its numbers
does not ship; a binary that cannot name its birthday does not serve).

## Numeric 004 — RPL_MYINFO [2812 §5.1]

**The text:** `"<servername> <version> <available user modes> <available channel modes>"`

**On the wire:**
```
S→C  :irc.house 004 Qasparr irc.house bleats-ircd-1.0 ioswx abdefhiklmnopqrstv
                                              └─ user modes ─┘ └─ channel modes ┘
```

**The six inquiries.** **Who:** server to fresh client. **What:** the
only structurally parseable line of the welcome burst: server name,
version, and the two alphabets of possibility — every user mode and
channel mode this server supports. **Where:** last of 001–004, the
burst's seal. **When:** at registration, always. **Why:** because a
client must not offer its user buttons the server will refuse: the mode
letters are the network's local constitution, differing per server, and
004 is how a portable client learns them. **How:** clients split the
line on spaces and file the letters; later strata move the detailed
truth to 005's key=value tokens, leaving 004 as the summary.

**The teaching.** 004 is where a student first meets IRC's federation
problem: the protocol is one, the mode alphabets are many. Every
"standard" client feature — halfop buttons, owner keys — exists only
where the local 004 (and 005) says it does. Portability is not assumed;
it is *negotiated, at connect, in this line.*

**Four elements.** *Inputs:* server name, version, two mode alphabets.
*Process:* none server-side; client-side, capability capture.
*Outputs:* one dense line. *Tolerances:* clients must accept mode
letters they do not know — the alphabet grows, and an unknown letter is
information, not corruption.

**House hookup.** The house daemon's 004 is generated from its real mode
tables — the spec's prefix ladder lives here: when +h (halfop) is in the
alphabet, bleatsirc draws the `%`; when it is not, it does not. The UI
follows the wire, never the wish.

## Numeric 005 — RPL_BOUNCE, and the great collision [2812 §5.1; LIVING]

**The text [2812]:** `"Try server <server name>, port <port number>"` —
RPL_BOUNCE: the server refuses the connection and redirects it.

**The living fact:** on every modern network, **005 is ISUPPORT** — a
stream of key=value tokens (PREFIX, CHANMODES, MAXCHANNELS, NICKLEN,
NETWORK…) that is the real capability contract of the connection, far
outweighing 004. Two definitions, one number, zero overlap in meaning.

**The six inquiries.** **Who:** server to client, either at the door
(bounce) or inside the welcome (ISUPPORT). **What:** in 2812, a
redirection; in life, the server's full capability table. **Where:** the
welcome burst's tail on living networks. **When:** per connection.
**Why (both):** a growing network needed to refuse gracefully (bounce)
and to describe itself precisely (ISUPPORT); history needed the second
more, and took the number. **How:** clients parse 005 token by token;
a token without `=` is a flag; a leading `-` withdraws one. ISUPPORT
parsing is the single most consequential numeric-handling job a client
has — PREFIX alone defines what @, %, + (and ~, &) mean on that wire.

**The teaching.** Here is the Zero-Point Directive's home ground: 005
diverges at the *number itself*. The lesson is not that the standard
failed — it is that protocols are governed by deployment, and a
Teacher's Revision must teach the wire's truth with the paper's truth
beside it, both labeled. Students: when the book and the wire disagree,
the wire is the territory; the book is a map with a date on it.

**Four elements.** *Inputs:* refusal+redirect, or the capability set.
*Process:* tokenization and filing. *Outputs:* a redirected client, or a
configured one. *Tolerances:* parsers must accept unknown tokens
silently — the set grows yearly, on purpose.

**House hookup.** bleatsirc's numeric registry treats 005 as the
exemplar of strata labeling: `[2812]` bounce handler and `[LIVING]`
ISUPPORT handler share the dispatch entry, and the registry file says
so, in the open, where a student can see the collision instead of
tripping on it.

## Numerics 431 / 432 / 433 / 436 — the four refusals of a name [1459 §6.1]

**The texts:**
```
431 ERR_NONICKNAMEGIVEN   ":No nickname given"
432 ERR_ERRONEUSNICKNAME  "<nick> :Erroneus nickname"
433 ERR_NICKNAMEINUSE     "<nick> :Nickname is already in use"
436 ERR_NICKCOLLISION     "<nick> :Nickname collision KILL"
```

**On the wire (a registration, dying four ways):**
```
C→S  NICK                      → 431 (you asked for the empty name)
C→S  NICK 9bad nick            → 432 (the law of letters refuses it)
C→S  NICK Qasparr              → 433 (someone is standing in it)
S→S  (two Qasparrs, one split) → 436 (the network kills to resolve it)
```

**The six inquiries (taken together, as the family they are).** **Who:**
the server, refusing a NICK. **What:** four distinct verdicts — absence
(431), illegality (432), occupation (433), and the server-to-server
catastrophe (436) where two networks each hold the same name after a
link and one registration must be KILLed to heal the merge. **Where:**
registration, and (433) any later nick change. **When:** at the moment
of claim. **Why:** a namespace that admits collisions admits chaos; the
four errors are the boundary survey of the nick namespace — its syntax,
its occupancy, and its federal law. **How:** 431–433 go to the claimant
alone (note the `*` in place of a nick in the trace: the server does not
yet know who you are, and addresses the void). 436 precedes a KILL and
travels with the burst as the merge's scar tissue.

**The teaching.** This family teaches the difference between *in use*
and *collision* — between a person holding a name and a topology
holding it twice. 436 is the numeric form of a netsplit healing, and it
is why the TS doctrine exists: timestamps decide which Qasparr is the
elder, and the younger dies by protocol, without malice and without
appeal. The founder's channel law — first come, first served, occupation
is title — is this family's philosophy, generalized.

**Four elements.** *Inputs:* a claim. *Process:* syntax, occupancy, and
topology checks, in that order. *Outputs:* one refusal, or a KILL.
*Tolerances:* 433's text must be tolerated with any target placeholder —
a client that demands its own nick in the reply will fail registration
on half the networks alive.

**House hookup.** In bleatsirc these four are the registration wizard's
whole curriculum: 433 fires the alternate-nick ladder (a configured,
member-owned list — never random suffix spam), 432 is explained inline
in human words, and 436 in the raw window is annotated by the teaching
text of this very entry.

## Numeric 451 — ERR_NOTREGISTERED [1459 §6.1]

**The text:** `":You have not registered"`

**The six inquiries.** **Who:** the server, to a socket that has
connected but not completed PASS/NICK/USER, when it attempts nearly
anything else. **What:** the protocol's closed-door notice — not a
punishment, a state report. **Where:** the whole pre-registration
shadowland; it is the only numeric most commands can earn there.
**When:** on any premature command. **Why:** because the server cannot
file a JOIN or a PRIVMSG under a name that does not yet exist; state
must precede speech. **How:** one line, no parameters; the connection
stays open — 451 is an invitation to finish registering, not a refusal
of the person.

**The teaching.** 451 is the protocol's fail-closed capstone in numeric
form: *no justification, no action.* The house recognizes its own office
in it. A student should also mark what 451 is not: it is not a ban, not
an error of character — merely a door that opens from the other side,
after the three messages at the gate are given in their order.

**Four elements.** *Inputs:* any command from an unregistered
connection. *Process:* registration-state check, which precedes all
other processing. *Outputs:* one line; state unchanged. *Tolerances:*
must be sent for commands the server would otherwise have to parse
against a nonexistent user record — which is to say, nearly all.

**House hookup.** The house daemon answers 451 exactly once per command
and logs nothing about it (no logs doctrine): the door is closed, and
that is all the record says, because that is all that happened.

---

*Brick I ends. Brick II — The Server Confesses — follows in the brick
ladder: MOTD, LUSERS, VERSION, STATS, LINKS, TIME, ADMIN, INFO and the
200–391 numerics, each under the same anatomy.*

Flagpole of Claim and Coinage: Johnathan 'Qasparr' Monroe, ARR, All Rights Reserved, Without Prejudice. Right of claim hereby reserved and coined under the authority of the Living Man.

93 — Live, Love, and let Love, Live.
