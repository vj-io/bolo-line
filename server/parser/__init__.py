"""Bolo Line parser (PRD section 4).

Pure: no file, network or database access. The station and the prompts come in as
arguments, so tests call `parse` and `confirm` directly as well as through the endpoint.
Ported from round2/research/parser_reference.py.
"""
import re

ORDER = ["batch_no", "machine", "temperature_c", "rejects"]
RANGES = {"batch_no": (1, 9999), "temperature_c": (0, 400), "rejects": (0, 1000)}


def norm(tok):
    """One normal form per token (PRD 4.1 steps 4 and 5)."""
    t = tok.lower().replace("़", "").replace("ँ", "ं")  # nukta; chandrabindu -> anusvara
    t = t.replace("‌", "").replace("‍", "")  # zero-width non-joiner and joiner
    if t.isascii():
        t = t.replace("aa", "a").replace("ee", "i").replace("oo", "u")
    return t


def words(*ws):
    return {norm(w) for w in ws}


HI = {  # value -> spellings: PRD table 4.2 plus common short variants
    0: "shunya sunya zero jiro शून्य ज़ीरो जीरो", 1: "ek एक", 2: "do दो", 3: "teen tin तीन",
    4: "chaar char चार", 5: "paanch panch पांच पाँच", 6: "chhah chah chhe che छह छः छे",
    7: "saat sat सात", 8: "aath ath आठ", 9: "nau नौ", 10: "das दस",
    11: "gyarah gyara ग्यारह", 12: "barah bara बारह", 13: "terah tera तेरह",
    14: "chaudah chauda चौदह", 15: "pandrah pandra पंद्रह पन्द्रह", 16: "solah sola सोलह",
    17: "satrah satra सत्रह", 18: "atharah athara अठारह", 19: "unnis उन्नीस", 20: "bees bis बीस",
    21: "ikkis इक्कीस", 22: "bais baees बाईस", 23: "teis teees तेईस", 24: "chaubis चौबीस",
    25: "pachchis pachis पच्चीस", 26: "chhabbis chabbis छब्बीस", 27: "sattais सत्ताईस",
    28: "atthais athais अट्ठाईस", 29: "untis उनतीस", 30: "tees tis तीस", 31: "ikattis iktis इकतीस",
    32: "battis बत्तीस", 33: "taintis tentis तैंतीस", 34: "chauntis chautis चौंतीस",
    35: "paintis pentis पैंतीस", 36: "chhattis chattis छत्तीस", 37: "saintis sentis सैंतीस",
    38: "adtis artis अड़तीस", 39: "untalis उनतालीस", 40: "chalis चालीस", 41: "iktalis इकतालीस",
    42: "bayalis बयालीस", 43: "taintalis tentalis तैंतालीस", 44: "chavalis chauvalis चवालीस",
    45: "paintalis pentalis पैंतालीस", 46: "chhiyalis chiyalis छियालीस",
    47: "saintalis sentalis सैंतालीस", 48: "adtalis artalis अड़तालीस", 49: "unchas उनचास",
    50: "pachas पचास", 51: "ikyavan इक्यावन", 52: "bavan बावन", 53: "tirpan तिरपन",
    54: "chauvan चौवन", 55: "pachpan पचपन", 56: "chhappan chappan छप्पन", 57: "sattavan सत्तावन",
    58: "atthavan athavan अट्ठावन", 59: "unsath उनसठ", 60: "saath sath साठ", 61: "iksath इकसठ",
    62: "basath बासठ", 63: "tirsath तिरसठ", 64: "chaunsath chausath चौंसठ",
    65: "painsath pensath पैंसठ", 66: "chhiyasath chiyasath छियासठ", 67: "sadsath sarsath सड़सठ",
    68: "adsath arsath अड़सठ", 69: "unhattar उनहत्तर", 70: "sattar सत्तर", 71: "ikhattar इकहत्तर",
    72: "bahattar बहत्तर", 73: "tihattar तिहत्तर", 74: "chauhattar चौहत्तर",
    75: "pachhattar pachattar पचहत्तर", 76: "chhihattar chihattar छिहत्तर",
    77: "satahattar sathattar सतहत्तर", 78: "athahattar athhattar अठहत्तर", 79: "unasi उनासी",
    80: "assi asi अस्सी", 81: "ikyasi इक्यासी", 82: "bayasi बयासी", 83: "tirasi तिरासी",
    84: "chaurasi चौरासी", 85: "pachasi पचासी", 86: "chhiyasi chiyasi छियासी", 87: "sattasi सत्तासी",
    88: "atthasi athasi अट्ठासी", 89: "navasi नवासी", 90: "nabbe nabbai नब्बे",
    91: "ikyanve इक्यानवे", 92: "banve बानवे", 93: "tiranve तिरानवे", 94: "chauranve चौरानवे",
    95: "panchanve पंचानवे", 96: "chhiyanve chiyanve छियानवे", 97: "sattanve सत्तानवे",
    98: "atthanve athanve अट्ठानवे", 99: "ninyanve ninanve निन्यानवे",
}
EN_SMALL = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen " \
           "sixteen seventeen eighteen nineteen".split()
EN_TENS = {norm(w): v for w, v in zip("twenty thirty forty fifty sixty seventy eighty ninety".split(),
                                      range(20, 100, 10))}
SMALL = {}  # normalised word -> (value, "hi" | "en")
for _v, _spellings in HI.items():
    for _w in _spellings.split():
        SMALL[norm(_w)] = (_v, "hi")
for _v, _w in enumerate(EN_SMALL, 1):
    SMALL[norm(_w)] = (_v, "en")
HUNDRED = words("sau", "so", "सौ", "hundred", "हंड्रेड")
THOUSAND = words("hazaar", "hazar", "hajar", "हजार", "thousand")
HALF_HUNDRED = {norm(w): v for w, v in  # "dedh sau" = 150, "dhai sau" = 250
                [("dedh", 150), ("derh", 150), ("डेढ़", 150), ("dhai", 250), ("adhai", 250), ("ढाई", 250)]}

KEY = {
    "BATCH": words("batch", "bach", "baich", "बैच", "बॅच", "बेच"),
    "DEG": words("degree", "degrees", "digri", "digree", "डिग्री", "celsius", "सेल्सियस", "centigrade"),
    "TEMP": words("temperature", "temp", "tapman", "taapmaan", "तापमान", "टेम्परेचर", "टेंपरेचर"),
    "REJ": words("reject", "rejects", "rejected", "rejection", "rijekt", "रिजेक्ट", "रिजेक्टेड",
                 "kharab", "kharaab", "खराब"),
    "NEG": words("nahi", "nahin", "nai", "नहीं", "नही", "nil", "निल"),
    "KOI": words("koi", "कोई"),
}
SKIP = words("number", "nambar", "नंबर", "no", "ka", "ki", "ke", "का", "की", "के", "hai", "है",
             "tha", "था", "thi", "थी", "par", "pe", "पर", "पे", "mein", "me", "में", "aur", "और",
             "and", "the", "is", "was", "wala", "wali", "वाला", "वाली", "hue", "hua", "हुए", "हुआ")
YES = words("haan", "han", "ha", "haa", "ji", "yes", "yeah", "sahi", "theek", "thik", "ok", "okay",
            "हां", "हाँ", "हा", "जी", "सही", "ठीक", "यस", "ओके")
NO = words("nahi", "nahin", "nai", "na", "no", "galat", "नहीं", "नही", "ना", "गलत", "नो")

DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
PUNCT = re.compile(r"[°,.;:!?।|/\\()\[\]\"'’‘“”\-–—]")


def tokenize(text):
    """PRD 4.1: digits, punctuation, digit-letter split, then `norm` on every token."""
    text = PUNCT.sub(" ", text.translate(DEVA_DIGITS))
    text = re.sub(r"(\d)(?=[^\d\s])", r"\1 ", text)  # "180c" -> "180 c"
    return [norm(t) for t in text.split()]


def _small(toks, i):
    """A number below 100 starting at toks[i] -> (value, next index, language), or None."""
    if i >= len(toks):
        return None
    t = toks[i]
    if t in SMALL:
        return SMALL[t][0], i + 1, SMALL[t][1]
    if t in EN_TENS:  # "eighty five" = 85
        nxt = SMALL.get(toks[i + 1]) if i + 1 < len(toks) else None
        if nxt and nxt[1] == "en" and 1 <= nxt[0] <= 9:
            return EN_TENS[t] + nxt[0], i + 2, "en"
        return EN_TENS[t], i + 1, "en"
    return None


def _below_thousand(toks, i):
    t = toks[i]
    if t in HALF_HUNDRED and i + 1 < len(toks) and toks[i + 1] in HUNDRED:
        return HALF_HUNDRED[t], i + 2, "hi"
    if t in HUNDRED:  # a bare "sau" = 100
        head, j, lang = 1, i, "hi"
    else:
        g = _small(toks, i)
        if not g:
            return None
        head, j, lang = g
        if not (j < len(toks) and toks[j] in HUNDRED and 1 <= head <= 9):
            return g
    j += 1  # past the hundred word
    if j < len(toks) and toks[j] == "and":
        j += 1
    tail = _small(toks, j)
    if tail:
        return head * 100 + tail[0], tail[1], lang
    return head * 100, j, lang


def _number_at(toks, i):
    t = toks[i]
    if t.isdecimal():
        # ponytail: digit strings over 9 long are not numbers (also keeps int() under Python's
        # 4300-digit limit); every field's range ends far below that anyway.
        return (int(t), i + 1, "digit") if len(t) <= 9 else None
    g = _below_thousand(toks, i)
    if g and g[1] < len(toks) and toks[g[1]] in THOUSAND and 1 <= g[0] <= 99:
        rest = _below_thousand(toks, g[1] + 1) if g[1] + 1 < len(toks) else None
        if rest:
            return g[0] * 1000 + rest[0], rest[1], g[2]
        return g[0] * 1000, g[1] + 1, g[2]
    if t in THOUSAND:
        return 1000, i + 1, "hi"
    return g


def _lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _fold(toks, station):
    """Tokens -> items: ("NUM", value, lang) | ("KEY", name) | ("MACHINE", type, uncertain) | ("TOK", t)."""
    alias = {norm(a): typ for typ, al in station["machine_aliases"].items() for a in al}
    known = set(SMALL) | set(EN_TENS) | HUNDRED | THOUSAND | set(HALF_HUNDRED) | SKIP | set(alias)
    known = known.union(*KEY.values())
    items, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in alias:
            items.append(("MACHINE", alias[t], False)); i += 1; continue
        key = next((k for k, ks in KEY.items() if t in ks), None)
        if key:
            items.append(("KEY", key)); i += 1; continue
        n = _number_at(toks, i)
        if n:
            items.append(("NUM", n[0], n[2])); i = n[1]; continue
        if t not in known and t.isascii() and len(t) >= 4:  # "open" for "oven": uncertain machine word
            near = [typ for a, typ in alias.items() if a.isascii() and _lev(t, a) <= 1]
            if near:
                items.append(("MACHINE", near[0], True)); i += 1; continue
        if t not in SKIP:
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
        if it == ("KEY", "BATCH") and "batch_no" not in got and (j := num(i + 1)) is not None:
            take("batch_no", j)
    for i, it in enumerate(items):  # 2. machine: MACHINE NUM
        if it[0] == "MACHINE":
            j = num(i + 1)
            machine = (it[1], items[j][1] if j is not None else None, it[2])
            if j is not None:
                used.add(j)
            break
    for i, it in enumerate(items):  # 3. temperature: NUM DEG, with the "one eighty five" pair rule
        if it == ("KEY", "DEG") and "temperature_c" not in got and (j := num(i - 1)) is not None:
            take("temperature_c", j)
            k, v = num(j - 1), items[j]
            if k is not None and items[k][2] == "en" and v[2] == "en" and 1 <= items[k][1] <= 9 \
                    and 10 <= v[1] <= 99:
                got["temperature_c"] += items[k][1] * 100
                used.add(k)
    for i, it in enumerate(items):  # 3b. temperature: TEMP NUM
        if it == ("KEY", "TEMP") and "temperature_c" not in got and (j := num(i + 1)) is not None:
            take("temperature_c", j)
    for i, it in enumerate(items):  # 4. rejects: NUM REJ, else REJ NUM, else "reject nahi" / "koi reject"
        if it == ("KEY", "REJ") and "rejects" not in got:
            if (j := num(i - 1)) is not None or (j := num(i + 1)) is not None:
                take("rejects", j)
            elif items[i + 1:i + 2] == [("KEY", "NEG")] or (i > 0 and items[i - 1] == ("KEY", "KOI")):
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


def parse(text, station, prompts, draft=None, expect=None):
    """One turn of `/api/parse` (PRD 3.4). Returns the response body as a dict."""
    draft = {f: v for f, v in (draft or {}).items() if f in ORDER and v is not None}
    toks = tokenize(text or "")
    fields = {f: None for f in ORDER}
    problems, suggest = [], None
    if not toks and not draft:
        return _result("no_speech", fields, None, None, problems, station, prompts)

    items = _fold(toks, station)
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
    return _result(status, fields, ask, suggest, problems, station, prompts)


def _result(status, fields, ask, suggest, problems, station, prompts):
    limits = station["limits"]
    t, r = fields["temperature_c"], fields["rejects"]
    flags = {
        "temp_out_of_limit": t is not None and not limits["temperature_c"]["min"] <= t <= limits["temperature_c"]["max"],
        "rejects_over_limit": r is not None and r > limits["rejects"]["max"],
    }
    return {"status": status, "fields": fields, "ask": ask, "suggest": suggest, "problems": problems,
            "flags": flags, "say": _say(status, fields, ask, suggest, station, prompts)}


def _say(status, fields, ask, suggest, station, prompts):
    """PRD 4.7 and 4.8: `hi` is spoken, `roman` is shown."""
    hindi = {m["name"]: m["name_hi"] for m in station["machines"]}
    if status == "complete":
        key, values = "readback", dict(fields, machine_hi=hindi[fields["machine"]])
    elif status == "need_field":
        key, values = "ask_" + ask, {"machines": " ya ".join(hindi), "machines_hi": " या ".join(hindi.values())}
    elif status == "confirm_machine":
        key, values = "confirm_machine", {"machine": suggest["value"], "machine_hi": hindi[suggest["value"]]}
    else:
        key, values = status, {}
    return {k: prompts[key][k].format(**values) for k in ("hi", "roman")}


def confirm(text):
    """PRD 4.4: any no-word wins, then any yes-word, else unclear."""
    toks = set(tokenize(text or ""))
    if toks & NO:
        return "no"
    if toks & YES:
        return "yes"
    return "unclear"
