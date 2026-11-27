"""Bolo Line parser (PRD section 4).

No network, database or file access when called. The station comes in as an argument, so tests call
`parse` and `confirm` directly as well as through the endpoint. The words of each language come from
its language pack (server/lang/<code>.json, loaded once by server/config.py): keywords, number
words, yes and no words, machine names and prompts. English words and digits are understood in
every language and stay in this file. Adding a language is adding a pack, not code.
Ported from the reference parser written alongside the spec.
"""
import re
import unicodedata
from types import SimpleNamespace

from .. import config

ORDER = ["batch_no", "machine", "temperature_c", "rejects"]
RANGES = {"batch_no": (1, 9999), "temperature_c": (0, 400), "rejects": (0, 1000)}


def norm(tok):
    """One normal form per token (PRD 4.1 steps 4 and 5)."""
    # NFD first, so a letter stored with its nukta built in (ड़ as one code point, Marathi ऱ) loses it too.
    t = unicodedata.normalize("NFD", tok.lower()).replace("़", "").replace("ँ", "ं")  # nukta; chandrabindu -> anusvara
    t = t.replace("‌", "").replace("‍", "")  # zero-width non-joiner and joiner
    if t.isascii():
        t = t.replace("aa", "a").replace("ee", "i").replace("oo", "u")
    return t


def words(*ws):
    return {norm(w) for w in ws}


# English, understood in every language. A pack adds its own words to each of these.
EN_SMALL = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen " \
           "sixteen seventeen eighteen nineteen".split()
EN_TENS = {norm(w): v for w, v in zip("twenty thirty forty fifty sixty seventy eighty ninety".split(),
                                      range(20, 100, 10))}
EN_KEY = {
    "batch": words("batch"),
    "degree": words("degree", "degrees", "celsius", "centigrade"),
    "temperature": words("temperature", "temp"),
    "reject": words("reject", "rejects", "rejected", "rejection"),
    "none": words("nil"),
    "any": set(),  # the pack's word for "no ..." before "reject" (Hindi "koi")
}
EN_SKIP = words("number", "no", "and", "the", "is", "was")
EN_YES = words("yes", "yeah", "ok", "okay")
EN_NO = words("no")

DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")  # other scripts' digits need no table: int() reads them
PUNCT = re.compile(r"[°,.;:!?।|/\\()\[\]\"'’‘“”\-–—]")
PAUSE = re.compile(r"[,;.!?।]")  # a number is never joined across one of these
INDIC = (0x0900, 0x0DFF)  # Devanagari to Sinhala: the blocks of the scripts a pack can be written in


def _tokens(text):
    """PRD 4.1: digits, punctuation, digit-letter split, then `norm` on every token.
    Also returns the indexes of the tokens that start after a comma or a full stop."""
    toks, pauses = [], set()
    for part in PAUSE.split(text.translate(DEVA_DIGITS)):
        pauses.add(len(toks))
        part = re.sub(r"(\d)(?=[^\d\s])", r"\1 ", PUNCT.sub(" ", part))  # "180c" -> "180 c"
        toks += [norm(t) for t in part.split()]
    return toks, pauses


def tokenize(text):
    return _tokens(text)[0]


def _compile(pack):
    """A language pack as the lookup tables the parser uses."""
    n = pack["numbers"]
    small = {}  # normalised word -> (value, "native" | "en")
    for value, spellings in n["words"].items():
        for w in spellings.split():
            small[norm(w)] = (int(value), "native")
    small[norm("zero")] = (0, "en")
    for v, w in enumerate(EN_SMALL, 1):
        small[norm(w)] = (v, "en")
    # Whole phrases for 0 to 999 (generated from CLDR) plus the pack's hand-written colloquial forms,
    # keyed by the phrase with its spaces removed: a recogniser may join or split a compound number.
    table, longest = {}, 0
    phrases = list((n["table"] or {}).items()) + [(c["phrase"], c["value"]) for c in n["colloquial"]]
    for phrase, value in phrases:
        toks = tokenize(phrase)
        if table.setdefault("".join(toks), value) != value:
            raise ValueError(f"language pack {pack['code']}: {phrase!r} stands for two numbers")
        longest = max(longest, len(toks))
    lo, hi = (int(pack["script"][k], 16) for k in ("first", "last"))
    return SimpleNamespace(
        code=pack["code"], locale=pack["locale"], prompts=pack["prompts"], machines=pack["machines"],
        join=pack["or"], small=small, table=table,
        max_run=longest + 2 if table else 0,  # ponytail: a number split into more pieces than this is not joined
        hundred=words("hundred", *n["hundred"]), thousand=words("thousand", *n["thousand"]),
        half_hundred={norm(w): v for w, v in n["half_hundred"].items()},  # "dedh sau" = 150, "dhai sau" = 250
        key={role: en | words(*pack["keywords"][role]) for role, en in EN_KEY.items()},
        skip=EN_SKIP | words(*pack["keywords"]["skip"]),
        yes=EN_YES | words(*pack["yes"]), no=EN_NO | words(*pack["no"]),
        script=(lo, hi),
    )


PACKS = {code: _compile(pack) for code, pack in config.LANGS.items()}


def _other_script(text, P):
    """True when the text holds a letter of an Indic script that is not the selected language's.
    Only letters and vowel signs count, so Latin, every script's digits and the danda (। sits in
    the Devanagari block but every Indic script uses it) are always allowed. Hindi and Marathi share
    Devanagari, so this check cannot tell those two apart: it catches a Tamil sentence on a Hindi
    station, not a Marathi one."""
    lo, hi = P.script
    return any(INDIC[0] <= ord(c) <= INDIC[1] and not lo <= ord(c) <= hi
               and unicodedata.category(c)[0] in "LM" for c in text)


def _small(toks, i, P):
    """A number below 100 starting at toks[i] -> (value, next index, language), or None."""
    if i >= len(toks):
        return None
    t = toks[i]
    if t in P.small:
        return P.small[t][0], i + 1, P.small[t][1]
    if t in EN_TENS:  # "eighty five" = 85
        nxt = P.small.get(toks[i + 1]) if i + 1 < len(toks) else None
        if nxt and nxt[1] == "en" and 1 <= nxt[0] <= 9:
            return EN_TENS[t] + nxt[0], i + 2, "en"
        return EN_TENS[t], i + 1, "en"
    return None


def _phrase(toks, i, pauses, P):
    """The longest run of tokens from toks[i] that, joined, is a phrase of the pack's number table."""
    for j in range(min(len(toks), i + P.max_run), i, -1):
        value = P.table.get("".join(toks[i:j]))
        if value is not None and not pauses & set(range(i + 1, j)):
            return value, j, "native"
    return None


def _below_thousand(toks, i, pauses, P):
    g = _phrase(toks, i, pauses, P)
    if g:
        return g
    t = toks[i]
    if t in P.half_hundred and i + 1 < len(toks) and toks[i + 1] in P.hundred:
        return P.half_hundred[t], i + 2, "native"
    if t in P.hundred:  # a bare "sau" = 100
        head, j, lang = 1, i, "native"
    else:
        g = _small(toks, i, P)
        if not g:
            return None
        head, j, lang = g
        if not (j < len(toks) and toks[j] in P.hundred and 1 <= head <= 9):
            return g
    j += 1  # past the hundred word
    if j < len(toks) and toks[j] == "and":
        j += 1
    tail = _small(toks, j, P)
    if tail:
        return head * 100 + tail[0], tail[1], lang
    return head * 100, j, lang


def _number_at(toks, i, pauses, P):
    t = toks[i]
    if t.isdecimal():
        # ponytail: digit strings over 9 long are not numbers (also keeps int() under Python's
        # 4300-digit limit); every field's range ends far below that anyway.
        return (int(t), i + 1, "digit") if len(t) <= 9 else None
    g = _below_thousand(toks, i, pauses, P)
    if g and g[1] < len(toks) and toks[g[1]] in P.thousand and 1 <= g[0] <= 99:
        rest = _below_thousand(toks, g[1] + 1, pauses, P) if g[1] + 1 < len(toks) else None
        if rest:
            return g[0] * 1000 + rest[0], rest[1], g[2]
        return g[0] * 1000, g[1] + 1, g[2]
    if t in P.thousand:
        return 1000, i + 1, "native"
    return g


def _lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _fold(toks, pauses, station, P):
    """Tokens -> items: ("NUM", value, lang) | ("KEY", role) | ("MACHINE", type, uncertain) | ("TOK", t)."""
    alias = {norm(a): typ for typ, al in station["machine_aliases"].items() for a in al}
    for typ in station["machine_aliases"]:  # the pack's own spellings of the station's machine types
        alias.update({norm(a): typ for a in P.machines.get(typ, {}).get("aliases", [])})
    known = set(P.small) | set(EN_TENS) | P.hundred | P.thousand | set(P.half_hundred) | P.skip | set(alias)
    known = known.union(*P.key.values())
    items, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in alias:
            items.append(("MACHINE", alias[t], False)); i += 1; continue
        key = next((k for k, ks in P.key.items() if t in ks), None)
        if key:
            items.append(("KEY", key)); i += 1; continue
        n = _number_at(toks, i, pauses, P)
        if n:
            items.append(("NUM", n[0], n[2])); i = n[1]; continue
        # "open" for "oven": uncertain machine word. Latin only: never match loosely in a script
        # that nobody on the team can check.
        if t not in known and t.isascii() and len(t) >= 4:
            near = [typ for a, typ in alias.items() if a.isascii() and _lev(t, a) <= 1]
            if near:
                items.append(("MACHINE", near[0], True)); i += 1; continue
        if t not in P.skip:
            items.append(("TOK", t))
        i += 1
    return items


def _bind(items, station, filled, expect):
    """PRD 4.5 steps 1-6. Returns (numbers by field, machine heard as (type, number, uncertain) or None)."""
    used, got, machine = set(), {}, None

    def num(j):
        return j if 0 <= j < len(items) and items[j][0] == "NUM" and j not in used else None

    def take(field, j):
        got[field] = items[j][1]
        used.add(j)

    for i, it in enumerate(items):  # 1. batch: BATCH NUM
        if it == ("KEY", "batch") and "batch_no" not in got and (j := num(i + 1)) is not None:
            take("batch_no", j)
    for i, it in enumerate(items):  # 2. machine: MACHINE NUM
        if it[0] == "MACHINE":
            j = num(i + 1)
            machine = (it[1], items[j][1] if j is not None else None, it[2])
            if j is not None:
                used.add(j)
            break
    for i, it in enumerate(items):  # 3. temperature: NUM DEG, with the "one eighty five" pair rule
        if it == ("KEY", "degree") and "temperature_c" not in got and (j := num(i - 1)) is not None:
            take("temperature_c", j)
            k, v = num(j - 1), items[j]
            if k is not None and items[k][2] == "en" and v[2] == "en" and 1 <= items[k][1] <= 9 \
                    and 10 <= v[1] <= 99:
                got["temperature_c"] += items[k][1] * 100
                used.add(k)
    for i, it in enumerate(items):  # 3b. temperature: TEMP NUM
        if it == ("KEY", "temperature") and "temperature_c" not in got and (j := num(i + 1)) is not None:
            take("temperature_c", j)
    for i, it in enumerate(items):  # 4. rejects: NUM REJ, else REJ NUM, else "reject nahi" / "koi reject"
        if it == ("KEY", "reject") and "rejects" not in got:
            if (j := num(i - 1)) is not None or (j := num(i + 1)) is not None:
                take("rejects", j)
            elif items[i + 1:i + 2] == [("KEY", "none")] or (i > 0 and items[i - 1] == ("KEY", "any")):
                got["rejects"] = 0
    left = [i for i in range(len(items)) if num(i) is not None]
    if expect and len(left) == 1:  # 5. follow-up answer
        if expect == "machine" and machine is None and filled.get("machine") is None:
            machine = (station["machines"][0]["type"], items[left[0]][1], False)
        elif expect != "machine" and expect not in got and filled.get(expect) is None:
            take(expect, left[0])
    if not expect and len(left) == 1 and "temperature_c" not in got \
            and filled.get("temperature_c") is None and 50 <= items[left[0]][1] <= 400:
        take("temperature_c", left[0])  # 6. rule L: one spare number, "degree" dropped
    return got, machine


def parse(text, station, prompts=None, draft=None, expect=None, lang="hi"):
    """One turn of `/api/parse` (PRD 3.4). Returns the response body as a dict.

    `lang` is a language pack code and must be a known one (the endpoint checks it). `prompts`
    replaces the pack's own prompt templates, key by key, when given."""
    P = PACKS[lang]
    draft = {f: v for f, v in (draft or {}).items() if f in ORDER and v is not None}
    text = text or ""
    fields = {f: None for f in ORDER}
    problems, suggest = [], None
    if _other_script(text, P):  # the station is set to another language: do not guess at the words
        return _result("not_understood", fields, None, None, problems, station, prompts, P, "wrong_language")
    toks, pauses = _tokens(text)
    if not toks and not draft:
        return _result("no_speech", fields, None, None, problems, station, prompts, P)

    items = _fold(toks, pauses, station, P)
    got, machine = _bind(items, station, draft, expect)

    # Validate. A draft comes back from the client, so it is checked like a fresh value.
    values = {f: v for f, v in draft.items() if f != "machine"}
    values.update(got)
    for f, v in values.items():
        lo, hi = RANGES[f]
        if lo <= v <= hi:
            fields[f] = v
        else:
            problems.append({"field": f, "value": v, "reason": "impossible"})
    names = {m["name"] for m in station["machines"]}
    if "machine" in draft:
        if draft["machine"] in names:
            fields["machine"] = draft["machine"]
        else:
            problems.append({"field": "machine", "value": draft["machine"], "reason": "unknown_machine"})
    typ, number, uncertain = machine or (None, None, False)
    if number is not None or uncertain:  # a machine heard in this turn replaces the draft's
        same = [m for m in station["machines"] if m["type"] == typ]
        exact = next((m for m in same if m["number"] == number), None)
        if exact and not uncertain:
            fields["machine"] = exact["name"]
        else:
            # Closest number of the same type, lower on a tie; with no number every machine ties.
            fields["machine"] = None
            target = exact or min(same, key=lambda m: (abs(m["number"] - (number or 0)), m["number"]))
            suggest = {"field": "machine", "value": target["name"]}
            if not exact and number is not None:
                problems.append({"field": "machine", "value": f"{typ} {number}", "reason": "unknown_machine"})

    if not draft and not got and machine is None:
        status, ask = "not_understood", None
    elif suggest:
        status, ask = "confirm_machine", None
    else:
        missing = [f for f in ORDER if fields[f] is None]
        status, ask = ("need_field", missing[0]) if missing else ("complete", None)
    return _result(status, fields, ask, suggest, problems, station, prompts, P)


def _result(status, fields, ask, suggest, problems, station, prompts, P, hint=None):
    limits = station["limits"]
    t, r = fields["temperature_c"], fields["rejects"]
    flags = {
        "temp_out_of_limit": t is not None and not limits["temperature_c"]["min"] <= t <= limits["temperature_c"]["max"],
        "rejects_over_limit": r is not None and r > limits["rejects"]["max"],
    }
    return {"status": status, "fields": fields, "ask": ask, "suggest": suggest, "problems": problems,
            "flags": flags, "hint": hint, "say": _say(hint or status, fields, ask, suggest, station, prompts, P)}


def _say(status, fields, ask, suggest, station, prompts, P):
    """PRD 4.7 and 4.8: `text` is spoken in the language `lang`, `roman` is shown. `hi` is the old
    name of `text` and stays for callers written before the language packs."""
    def local(m):  # the machine's name in the pack's script, for the voice
        kind = P.machines.get(m["type"])
        return f"{kind['name']} {m['number']}" if kind else m["name"]

    names = {m["name"]: local(m) for m in station["machines"]}
    if status == "complete":
        key, values = "readback", dict(fields, machine_local=names[fields["machine"]])
    elif status == "need_field":
        key, values = "ask_" + ask, {"machines": P.join["roman"].join(names),
                                     "machines_local": P.join["text"].join(names.values())}
    elif status == "confirm_machine":
        key, values = "confirm_machine", {"machine": suggest["value"], "machine_local": names[suggest["value"]]}
    else:
        key, values = status, {}
    for k in [k for k in values if k.endswith("_local")]:  # server/prompts.json calls these *_hi
        values[k.replace("_local", "_hi")] = values[k]
    template = (prompts or {}).get(key) or P.prompts[key]
    text = (template.get("text") or template["hi"]).format(**values)
    return {"hi": text, "roman": template["roman"].format(**values), "text": text, "lang": P.locale}


def confirm(text, lang="hi"):
    """PRD 4.4: any no-word wins, then any yes-word, else unclear."""
    P = PACKS[lang]
    toks = set(tokenize(text or ""))
    if toks & P.no:
        return "no"
    if toks & P.yes:
        return "yes"
    return "unclear"
