"""The generated number tables (server/lang/numbers_<code>.json) and the generator (tools/gen_numbers.py).

Spot values are typed by hand from the research file, never read back from the generator.
"""
import hashlib
import json
from pathlib import Path

import pytest

from server import config, parser
from tools import gen_numbers

ROOT = Path(__file__).resolve().parent.parent
CLDR = ROOT / "tools" / "cldr" / "release-49"
CODES = ["hi", "mr"]


def load(code):
    return json.loads((ROOT / "server" / "lang" / f"numbers_{code}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("code, phrase, value", [
    ("mr", "चौदा", 14), ("mr", "सतरा", 17), ("mr", "सत्तर", 70), ("mr", "एकशे पंच्याहत्तर", 175),
    ("mr", "एकशे ऐंशी", 180), ("mr", "दोनशे दहा", 210), ("mr", "नऊशे", 900),
    ("mr", "शून्य", 0), ("mr", "शंभर", 100), ("mr", "एकशे एक", 101), ("mr", "दोनशे", 200),
    ("hi", "चौवालीस", 44), ("hi", "निन्यानबे", 99), ("hi", "एक सौ अस्सी", 180),
    ("hi", "शून्य", 0), ("hi", "एक सौ", 100), ("hi", "नौ सौ", 900),
])
def test_spot_value(code, phrase, value):
    assert load(code)[phrase] == value


@pytest.mark.parametrize("code", CODES)
def test_table_is_complete_and_clean(code):
    table = load(code)
    assert len(table) == 1000
    assert sorted(table.values()) == list(range(1000))
    for phrase in table:
        assert phrase.strip() == phrase and phrase, repr(phrase)
        assert not set("<>[]=%|") & set(phrase), phrase


@pytest.mark.parametrize("code", CODES)
def test_committed_table_is_what_the_generator_writes(code):
    fresh = gen_numbers.table(CLDR / f"{code}.xml", ["spellout-cardinal"])
    assert list(fresh.items()) == list(load(code).items())


@pytest.mark.parametrize("code", CODES)
def test_vendored_cldr_file_matches_the_recorded_hash(code):
    digest = hashlib.sha256((CLDR / f"{code}.xml").read_bytes()).hexdigest()
    assert f"{digest}  {code}.xml" in (CLDR / "README").read_text(encoding="utf-8")


# Rule forms that the Hindi and Marathi files do not use but other CLDR 49 files do.
SYNTHETIC = """
%spellout-cardinal:
-x: minus >>;
0: zero;
1: one;
2: two;
3: =%%three=;
10: ten[ >>];
20: <%%tens<[-and->>|-flat];
100: << hundred[ >%%tail>];
%%three:
0: THREE;
%%tens:
2: twenty;
3: thirty;
%%tail:
0: 'and =%spellout-cardinal=;
"""


@pytest.mark.parametrize("n, phrase", [
    (0, "zero"), (3, "THREE"), (10, "ten"), (12, "ten two"),
    (20, "twenty-flat"), (21, "twenty-and-one"), (30, "thirty-flat"), (33, "thirty-and-THREE"),
    (100, "one hundred"), (203, "two hundred and THREE"), (321, "THREE hundred and twenty-and-one"),
])
def test_generator_rule_forms(n, phrase):
    sets = gen_numbers.read_sets(SYNTHETIC)
    assert gen_numbers.spell(sets, "%spellout-cardinal", n) == phrase


def test_generator_refuses_a_rule_it_cannot_expand():
    sets = gen_numbers.read_sets("%spellout-cardinal:\n0: zero;\n10: >> and >>;\n")
    with pytest.raises(NotImplementedError):
        gen_numbers.spell(sets, "%spellout-cardinal", 12)
    with pytest.raises(ValueError):
        gen_numbers.read_sets("%spellout-cardinal:\n0 zero\n")


def test_generator_reads_indented_rule_text():
    sets = gen_numbers.read_sets("   %spellout-cardinal:\n\n   0: zero;\n   1: one;\n")
    assert gen_numbers.spell(sets, "%spellout-cardinal", 1) == "one"


XML = '<ldml><rbnf><rulesetGrouping type="SpelloutRules"><rbnfRules><![CDATA[\n%s]]></rbnfRules></rulesetGrouping></rbnf></ldml>'


@pytest.mark.parametrize("rules, message", [
    ("%spellout-cardinal:\n0: zero;\n1: left = over;\n", "bad phrase for 1"),   # rule syntax left in a phrase
    ("%spellout-cardinal:\n0: ;\n", "bad phrase for 0"),                       # an empty phrase
    ("%spellout-cardinal:\n0: same;\n", "is both 0 and 1"),                    # one phrase, two values
])
def test_generator_refuses_to_write_a_bad_table(tmp_path, rules, message):
    path = tmp_path / "xx.xml"
    path.write_text(XML % rules, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        gen_numbers.table(path, ["spellout-cardinal"])


# The Hindi parser builds numbers from single words and "sau"; CLDR is an independent list of the
# same numbers. Every CLDR spelling must read as its value (this is where 44, 53, 63 and 91 to 99
# were found missing).
HI_TABLE = sorted(load("hi").items(), key=lambda kv: kv[1])


@pytest.mark.parametrize("phrase, n", HI_TABLE[:100], ids=[str(n) for _, n in HI_TABLE[:100]])
def test_hindi_parser_reads_every_cldr_word_below_100(phrase, n):
    assert parser.parse(f"{phrase} reject", config.STATION)["fields"]["rejects"] == n


def test_hindi_parser_reads_every_cldr_phrase_below_1000():
    wrong = [(p, n) for p, n in HI_TABLE if parser.parse(f"{p} reject", config.STATION)["fields"]["rejects"] != n]
    assert len(HI_TABLE) == 1000 and wrong == []


# The Marathi parser looks whole phrases up in the table: as written, with the words joined, and
# with a full stop after the phrase.
MR_TABLE = sorted(load("mr").items(), key=lambda kv: kv[1])


def test_marathi_parser_reads_every_table_phrase_split_or_joined():
    wrong = []
    for phrase, n in MR_TABLE:
        for text in (f"{phrase} रिजेक्ट", f"{phrase.replace(' ', '')} रिजेक्ट", f"रिजेक्ट {phrase}."):
            if parser.parse(text, config.STATION, lang="mr")["fields"]["rejects"] != n:
                wrong.append((text, n))
    assert len(MR_TABLE) == 1000 and wrong == []
