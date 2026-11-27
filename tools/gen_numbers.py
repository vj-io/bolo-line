"""Expand Unicode CLDR spell-out rules into a phrase -> value table for 0 to 999.

Development-time only: the server reads the committed tables and never runs this.

    python tools/gen_numbers.py                 # every tools/cldr/release-49/<code>.xml
    python tools/gen_numbers.py mr              # one language
    python tools/gen_numbers.py ta --sets spellout-numbering spellout-cardinal   # merge two rule sets

Output: server/lang/numbers_<code>.json. Never edit that file by hand; spoken forms that CLDR does
not have go in the language pack's `numbers.colloquial` list.

Rule syntax handled (ICU rule-based number format, as written in the CLDR 49 files):
  `<<` and `>>`               the quotient and the remainder, spelled with the same rule set
  `<%set<`, `>%set>`          the same, spelled with another rule set (`%%set` is a private set)
  `=%set=`                    the whole number, spelled with another rule set
  `[text]`                    text kept only when the remainder is not zero
  `[text|other]`              `text` when the remainder is not zero, `other` when it is zero
Anything else (plural forms, decimal patterns, two remainder parts in one rule) stops the run with
an error instead of writing a wrong table.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLDR = ROOT / "tools" / "cldr" / "release-49"
OUT = ROOT / "server" / "lang"
LIMIT = 1000
SYNTAX = set("<>[]=%|")
PART = re.compile(r"<<|>>|<(%%?[\w-]+)<|>(%%?[\w-]+)>|=(%%?[\w-]+)=")
BRACKET = re.compile(r"\[([^\]|]*)(?:\|([^\]]*))?\]")


def read_sets(text):
    """Rule text -> {"%name": [(base, radix, body), ...]}. Rules for fractions, negatives and
    infinity (`x.x`, `-x`, `Inf`, `NaN`) are left out: the table holds whole numbers only."""
    sets, current = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("%") and line.endswith(":"):
            current = sets.setdefault(line[:-1], [])
            continue
        descriptor, sep, body = line.partition(":")
        if not sep or not body.endswith(";") or current is None:
            raise ValueError(f"cannot read rule line: {line!r}")
        base, _, radix = descriptor.strip().partition("/")
        if not base.isdecimal():
            continue
        body = body[:-1].strip()
        current.append((int(base), int(radix or 10), body[1:] if body.startswith("'") else body))
    return sets


def spell(sets, name, n):
    """The words for n in rule set `name`."""
    base, radix, body = max((r for r in sets[name] if r[0] <= n), key=lambda r: r[0])
    divisor = 1
    while divisor * radix <= base:
        divisor *= radix
    quotient, remainder = divmod(n, divisor)
    if len(re.findall(r">>|>%", body)) > 1:
        raise NotImplementedError(f"two remainder parts in one rule: {body!r}")
    body = BRACKET.sub(lambda m: m.group(1) if remainder else (m.group(2) or ""), body)

    def part(m):
        token = m.group(0)
        if token[0] == "<":
            return spell(sets, m.group(1) or name, quotient)
        if token[0] == ">":
            return spell(sets, m.group(2) or name, remainder)
        return spell(sets, m.group(3), n)

    return " ".join(PART.sub(part, body).split())


def table(xml_path, set_names):
    """{phrase: value} for 0 to 999, in value order. Raises if any phrase is empty, still holds rule
    syntax, or stands for two different values."""
    rules = ET.parse(xml_path).find("./rbnf/rulesetGrouping[@type='SpelloutRules']/rbnfRules")
    sets = read_sets(rules.text)
    out = {}
    for n in range(LIMIT):
        for name in set_names:
            phrase = spell(sets, "%" + name, n)
            if not phrase or SYNTAX & set(phrase):
                raise ValueError(f"{xml_path.name}: bad phrase for {n}: {phrase!r}")
            if out.setdefault(phrase, n) != n:
                raise ValueError(f"{xml_path.name}: {phrase!r} is both {out[phrase]} and {n}")
    return out


def write(code, set_names):
    phrases = table(CLDR / f"{code}.xml", set_names)
    lines = ",\n".join(f"  {json.dumps(p, ensure_ascii=False)}: {v}" for p, v in phrases.items())
    path = OUT / f"numbers_{code}.json"
    path.write_text("{\n" + lines + "\n}\n", encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: {len(phrases)} phrases for 0 to {LIMIT - 1}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("codes", nargs="*", help="language codes; default: every file in tools/cldr/release-49")
    ap.add_argument("--sets", nargs="+", default=["spellout-cardinal"], help="rule sets to expand and merge")
    args = ap.parse_args(argv)
    codes = args.codes or sorted(p.stem for p in CLDR.glob("*.xml"))
    if not codes:
        sys.exit(f"no CLDR files in {CLDR}")
    for code in codes:
        write(code, args.sets)


if __name__ == "__main__":
    main()
