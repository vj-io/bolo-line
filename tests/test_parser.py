"""Parser tests: PRD 4.6 table, 4.4 confirm cases, 4.2 number words, 4.7/4.8 texts, 3.5 samples.

Expected values are typed from the PRD, never computed by the parser.
"""
import pytest
from fastapi.testclient import TestClient

from server import config, parser
from server.main import app

client = TestClient(app)


def F(b, m, t, r):
    return {"batch_no": b, "machine": m, "temperature_c": t, "rejects": r}


def post_parse(text, draft=None, expect=None, station_id="oven-line"):
    r = client.post("/api/parse", json={"station_id": station_id, "text": text, "draft": draft, "expect": expect})
    assert r.status_code == 200, r.text
    return r.json()


# PRD 4.6: (row, utterance, draft, expect, status, fields, ask, suggested machine)
TABLE = [
    (1, "Batch chaudah, oven do, ek sau assi degree, teen reject", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (2, "बैच चौदह ओवन दो एक सौ अस्सी डिग्री तीन रिजेक्ट", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (3, "बैच 14 ओवन 2 180 डिग्री 3 रिजेक्ट", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (4, "batch fourteen, oven do, 180 degree, teen reject", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (5, "batch seventeen oven two one eighty five degree saat reject", None, None, "complete", F(17, "Oven 2", 185, 7), None, None),
    (6, "Batch pandrah, oven ek, do sau das degree, do reject", None, None, "complete", F(15, "Oven 1", 210, 2), None, None),
    (7, "oven ek batch number bees temperature ek sau pachattar reject paanch", None, None, "complete", F(20, "Oven 1", 175, 5), None, None),
    (8, "Batch solah, oven do, chaar reject", None, None, "need_field", F(16, "Oven 2", None, 4), "temperature_c", None),
    (9, "ek sau pachattar", F(16, "Oven 2", None, 4), "temperature_c", "complete", F(16, "Oven 2", 175, 4), None, None),
    (10, "Batch athaarah, oven teen, ek sau assi degree, ek reject", None, None, "confirm_machine", F(18, None, 180, 1), None, "Oven 2"),
    (11, "batch unnis open do ek sau nabbe degree do reject", None, None, "confirm_machine", F(19, None, 190, 2), None, "Oven 2"),
    (12, "Batch bees, oven ek, nau sau degree, do reject", None, None, "need_field", F(20, "Oven 1", None, 2), "temperature_c", None),
    (13, "batch ikkis oven do ek sau assi degree do hazaar reject", None, None, "need_field", F(21, "Oven 2", 180, None), "rejects", None),
    (14, "batch bais oven ek ek sau saath degree koi reject nahi", None, None, "complete", F(22, "Oven 1", 160, 0), None, None),
    (15, "batch teis oven do dedh sau degree zero reject", None, None, "complete", F(23, "Oven 2", 150, 0), None, None),
    (16, "batch 24 oven 2 one hundred and eighty two degrees 6 rejects", None, None, "complete", F(24, "Oven 2", 182, 6), None, None),
    (17, "batch pachchis oven do ek sau assi teen reject", None, None, "complete", F(25, "Oven 2", 180, 3), None, None),
    (18, "oven do, ek sau assi degree, teen reject", None, None, "need_field", F(None, "Oven 2", 180, 3), "batch_no", None),
    (19, "aaj mausam achha hai", None, None, "not_understood", F(None, None, None, None), None, None),
    (20, "", None, None, "no_speech", F(None, None, None, None), None, None),
    (21, "", F(18, "Oven 2", 180, 1), None, "complete", F(18, "Oven 2", 180, 1), None, None),
    (22, "do", F(18, None, 180, 1), "machine", "complete", F(18, "Oven 2", 180, 1), None, None),
    (23, "batch chhabbis oven ek 175° 2 reject", None, None, "complete", F(26, "Oven 1", 175, 2), None, None),
]
ROW = {row[0]: row for row in TABLE}


def run_row(n):
    _, text, draft, expect, *_ = ROW[n]
    return post_parse(text, draft, expect)


@pytest.mark.parametrize("row", TABLE, ids=[f"row{r[0]}" for r in TABLE])
def test_table_row(row):
    _, text, draft, expect, status, fields, ask, suggest = row
    body = post_parse(text, draft, expect)
    assert body["status"] == status
    assert body["fields"] == fields
    assert body["ask"] == ask
    assert (body["suggest"] or {}).get("value") == suggest


def test_row12_problem_is_exactly_the_impossible_temperature():
    assert run_row(12)["problems"] == [{"field": "temperature_c", "value": 900, "reason": "impossible"}]


def test_row13_problem_is_the_impossible_rejects():
    assert run_row(13)["problems"] == [{"field": "rejects", "value": 2000, "reason": "impossible"}]


def test_row10_unknown_machine_problem_and_suggest():
    body = run_row(10)
    assert body["problems"] == [{"field": "machine", "value": "oven 3", "reason": "unknown_machine"}]
    assert body["suggest"] == {"field": "machine", "value": "Oven 2"}


def test_row11_uncertain_word_suggests_without_problem():
    assert run_row(11)["problems"] == []


@pytest.mark.parametrize("n, temp_flag, rejects_flag", [
    (1, False, False), (6, True, False), (14, True, False), (15, True, False), (16, False, True),
])
def test_flags(n, temp_flag, rejects_flag):
    assert run_row(n)["flags"] == {"temp_out_of_limit": temp_flag, "rejects_over_limit": rejects_flag}


# PRD 4.7 and 4.8, typed from the PRD text.
@pytest.mark.parametrize("text, draft, expect, hi, roman", [
    (ROW[1][1], None, None, "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?", "Batch 14, Oven 2, 180 degree, 3 reject. Sahi hai?"),
    (ROW[8][1], None, None, "टेम्परेचर कितना था?", "Temperature kitna tha?"),
    (ROW[18][1], None, None, "बैच नंबर क्या है?", "Batch number kya hai?"),
    ("batch 5 180 degree 3 reject", None, None, "कौन सी मशीन? ओवन 1 या ओवन 2?", "Kaun si machine? Oven 1 ya Oven 2?"),
    (ROW[13][1], None, None, "कितने रिजेक्ट हुए?", "Kitne reject hue?"),
    (ROW[10][1], None, None, "ओवन 2 बोला? हाँ या नहीं?", "Oven 2 bola? Haan ya nahi?"),
    (ROW[19][1], None, None, "समझ नहीं आया, फिर से बोलिए", "Samajh nahi aaya, phir se boliye"),
    ("", None, None, "आवाज़ नहीं आई, फिर से बोलिए", "Awaaz nahi aayi, phir se boliye"),
], ids=["readback", "ask_temperature", "ask_batch", "ask_machine", "ask_rejects", "confirm_machine",
        "not_understood", "no_speech"])
def test_say(text, draft, expect, hi, roman):
    assert post_parse(text, draft, expect)["say"] == {"hi": hi, "roman": roman}


# PRD 4.4
@pytest.mark.parametrize("text, answer", [
    ("haan", "yes"), ("हाँ", "yes"), ("ji haan sahi hai", "yes"), ("yes", "yes"), ("theek hai", "yes"),
    ("nahi", "no"), ("नहीं", "no"), ("no", "no"), ("sahi nahi hai", "no"), ("galat", "no"),
    ("kya", "unclear"), ("", "unclear"),
])
def test_confirm(text, answer):
    r = client.post("/api/confirm", json={"text": text})
    assert r.status_code == 200 and r.json() == {"answer": answer}


# PRD 4.2, every roman and Devanagari word, extracted from the PRD table.
NUMBER_WORDS = [
    ("shunya", 0), ("zero", 0), ("शून्य", 0), ("ज़ीरो", 0), ("pachchis", 25), ("पच्चीस", 25),
    ("pachas", 50), ("पचास", 50), ("pachhattar", 75), ("पचहत्तर", 75), ("ek", 1), ("एक", 1),
    ("chhabbis", 26), ("छब्बीस", 26), ("ikyavan", 51), ("इक्यावन", 51), ("chhihattar", 76),
    ("छिहत्तर", 76), ("do", 2), ("दो", 2), ("sattais", 27), ("सत्ताईस", 27), ("bavan", 52),
    ("बावन", 52), ("satahattar", 77), ("सतहत्तर", 77), ("teen", 3), ("तीन", 3), ("atthais", 28),
    ("अट्ठाईस", 28), ("tirpan", 53), ("तिरपन", 53), ("athahattar", 78), ("अठहत्तर", 78),
    ("chaar", 4), ("चार", 4), ("untis", 29), ("उनतीस", 29), ("chauvan", 54), ("चौवन", 54),
    ("unasi", 79), ("उनासी", 79), ("paanch", 5), ("पांच", 5), ("tees", 30), ("तीस", 30),
    ("pachpan", 55), ("पचपन", 55), ("assi", 80), ("अस्सी", 80), ("chhah", 6), ("chhe", 6),
    ("छह", 6), ("छः", 6), ("ikattis", 31), ("इकतीस", 31), ("chhappan", 56), ("छप्पन", 56),
    ("ikyasi", 81), ("इक्यासी", 81), ("saat", 7), ("सात", 7), ("battis", 32), ("बत्तीस", 32),
    ("sattavan", 57), ("सत्तावन", 57), ("bayasi", 82), ("बयासी", 82), ("aath", 8), ("आठ", 8),
    ("taintis", 33), ("तैंतीस", 33), ("atthavan", 58), ("अट्ठावन", 58), ("tirasi", 83),
    ("तिरासी", 83), ("nau", 9), ("नौ", 9), ("chauntis", 34), ("चौंतीस", 34), ("unsath", 59),
    ("उनसठ", 59), ("chaurasi", 84), ("चौरासी", 84), ("das", 10), ("दस", 10), ("paintis", 35),
    ("पैंतीस", 35), ("saath", 60), ("साठ", 60), ("pachasi", 85), ("पचासी", 85), ("gyarah", 11),
    ("ग्यारह", 11), ("chhattis", 36), ("छत्तीस", 36), ("iksath", 61), ("इकसठ", 61),
    ("chhiyasi", 86), ("छियासी", 86), ("barah", 12), ("बारह", 12), ("saintis", 37), ("सैंतीस", 37),
    ("basath", 62), ("बासठ", 62), ("sattasi", 87), ("सत्तासी", 87), ("terah", 13), ("तेरह", 13),
    ("adtis", 38), ("अड़तीस", 38), ("tirsath", 63), ("तिरसठ", 63), ("atthasi", 88),
    ("अट्ठासी", 88), ("chaudah", 14), ("चौदह", 14), ("untalis", 39), ("उनतालीस", 39),
    ("chaunsath", 64), ("चौंसठ", 64), ("navasi", 89), ("नवासी", 89), ("pandrah", 15),
    ("पंद्रह", 15), ("chalis", 40), ("चालीस", 40), ("painsath", 65), ("पैंसठ", 65), ("nabbe", 90),
    ("नब्बे", 90), ("solah", 16), ("सोलह", 16), ("iktalis", 41), ("इकतालीस", 41),
    ("chhiyasath", 66), ("छियासठ", 66), ("ikyanve", 91), ("इक्यानवे", 91), ("satrah", 17),
    ("सत्रह", 17), ("bayalis", 42), ("बयालीस", 42), ("sadsath", 67), ("सड़सठ", 67), ("banve", 92),
    ("बानवे", 92), ("atharah", 18), ("अठारह", 18), ("taintalis", 43), ("तैंतालीस", 43),
    ("adsath", 68), ("अड़सठ", 68), ("tiranve", 93), ("तिरानवे", 93), ("unnis", 19), ("उन्नीस", 19),
    ("chavalis", 44), ("चवालीस", 44), ("unhattar", 69), ("उनहत्तर", 69), ("chauranve", 94),
    ("चौरानवे", 94), ("bees", 20), ("बीस", 20), ("paintalis", 45), ("पैंतालीस", 45),
    ("sattar", 70), ("सत्तर", 70), ("panchanve", 95), ("पंचानवे", 95), ("ikkis", 21),
    ("इक्कीस", 21), ("chhiyalis", 46), ("छियालीस", 46), ("ikhattar", 71), ("इकहत्तर", 71),
    ("chhiyanve", 96), ("छियानवे", 96), ("bais", 22), ("बाईस", 22), ("saintalis", 47),
    ("सैंतालीस", 47), ("bahattar", 72), ("बहत्तर", 72), ("sattanve", 97), ("सत्तानवे", 97),
    ("teis", 23), ("तेईस", 23), ("adtalis", 48), ("अड़तालीस", 48), ("tihattar", 73),
    ("तिहत्तर", 73), ("atthanve", 98), ("अट्ठानवे", 98), ("chaubis", 24), ("चौबीस", 24),
    ("unchas", 49), ("उनचास", 49), ("chauhattar", 74), ("चौहत्तर", 74), ("ninyanve", 99),
    ("निन्यानवे", 99),
]


def test_number_word_count():
    assert len(NUMBER_WORDS) >= 200 and {n for _, n in NUMBER_WORDS} == set(range(100))


@pytest.mark.parametrize("word, n", NUMBER_WORDS)
def test_number_word(word, n):
    body = parser.parse(f"{word} reject", config.STATION, config.PROMPTS)
    assert body["fields"]["rejects"] == n


# PRD 3.5: the stored samples, read from server/samples.json, through the endpoint.
def test_samples():
    sample = {s["id"]: s["text"] for s in config.SAMPLES}
    s1 = post_parse(sample["s1"])
    assert (s1["status"], s1["fields"], s1["flags"]) == (
        "complete", F(14, "Oven 2", 180, 3), {"temp_out_of_limit": False, "rejects_over_limit": False})
    s2 = post_parse(sample["s2"])
    assert (s2["status"], s2["fields"], s2["flags"]) == (
        "complete", F(15, "Oven 1", 210, 2), {"temp_out_of_limit": True, "rejects_over_limit": False})
    s3 = post_parse(sample["s3"])
    assert (s3["status"], s3["ask"]) == ("need_field", "temperature_c")
    s3b = post_parse(sample["s3b"], draft=s3["fields"], expect=s3["ask"])
    assert (s3b["status"], s3b["fields"]) == ("complete", F(16, "Oven 2", 175, 4))
    s4 = post_parse(sample["s4"])
    assert (s4["status"], s4["fields"], s4["flags"]) == (
        "complete", F(17, "Oven 2", 185, 7), {"temp_out_of_limit": False, "rejects_over_limit": True})


def test_unknown_station_is_404():
    r = client.post("/api/parse", json={"station_id": "nope", "text": "batch 5"})
    assert r.status_code == 404 and r.json()["error"] == "unknown_station"


# Inputs beyond the table.
def test_known_limit_reads_hundred_and_three_rejects():  # PRD 4.6, "Known limit, accepted"
    body = post_parse("batch 5 oven 1 ek sau teen reject")
    assert (body["status"], body["ask"], body["fields"]["rejects"]) == ("need_field", "temperature_c", 103)


def test_punctuation_only_is_no_speech():
    assert post_parse(" ... । ")["status"] == "no_speech"


def test_all_null_draft_counts_as_no_draft():
    assert post_parse("", draft=F(None, None, None, None))["status"] == "no_speech"


def test_draft_values_are_checked_again():
    body = post_parse("", draft=F(18, "Oven 9", 900, 1))
    assert body["fields"] == F(18, None, None, 1)
    assert body["problems"] == [{"field": "temperature_c", "value": 900, "reason": "impossible"},
                                {"field": "machine", "value": "Oven 9", "reason": "unknown_machine"}]


def test_newer_turn_overrides_draft():
    body = post_parse("batch bees", draft=F(16, "Oven 2", 175, 4))
    assert (body["status"], body["fields"]["batch_no"]) == ("complete", 20)


def test_machine_word_without_number_keeps_draft_machine():
    body = post_parse("oven", draft=F(16, "Oven 2", 175, 4))
    assert (body["status"], body["fields"]["machine"]) == ("complete", "Oven 2")


def test_uncertain_machine_word_without_number_suggests_lowest():
    body = post_parse("batch 5 open temperature 180 3 reject")
    assert (body["status"], body["suggest"], body["problems"]) == (
        "confirm_machine", {"field": "machine", "value": "Oven 1"}, [])


def test_expect_machine_bare_unknown_number_asks_to_confirm():
    body = post_parse("teen", draft=F(18, None, 180, 1), expect="machine")
    assert (body["status"], body["suggest"]["value"]) == ("confirm_machine", "Oven 2")


def test_expect_ignored_when_two_numbers_left():
    body = post_parse("ek do", draft=F(16, "Oven 2", None, 4), expect="temperature_c")
    assert (body["status"], body["ask"]) == ("need_field", "temperature_c")


@pytest.mark.parametrize("text, batch", [
    ("batch १४", 14),       # Devanagari digits
    ("batch ২৫", 25),       # another script's decimal digits
    ("batch 14c", 14),       # digit then letter
    ("batch ²", None),       # superscript: isdigit() but not a decimal, must not crash
    ("batch 1" + "0" * 5000, None),  # over Python's int() digit limit, must not crash
])
def test_digit_tokens(text, batch):
    assert post_parse(text)["fields"]["batch_no"] == batch


@pytest.mark.parametrize("text, batch", [
    ("batch twenty", 20),             # bare English tens
    ("batch sau", 100),               # bare "sau" = 100 (PRD 4.2)
    ("batch hazaar", 1000),           # bare "hazaar"
    ("batch do hazaar paanch sau", 2500),  # thousand with a remainder
    ("batch do sau", 200),            # hundred word last in the text
    ("batch चौ‍दह", 14),         # zero-width joiner inside a word (PRD 4.1 step 4)
    ("batch kal 14", None),           # another word between keyword and number breaks the pair
])
def test_number_shapes(text, batch):
    assert post_parse(text)["fields"]["batch_no"] == batch


def test_first_machine_word_wins():
    assert post_parse("batch 5 oven 1 oven 2 180 degree 3 reject")["fields"]["machine"] == "Oven 1"


def test_pair_rule_consumes_both_words():
    # "one" joins "eighty five"; it must not be left over to answer the expected field.
    body = post_parse("one eighty five degree", draft=F(5, "Oven 1", None, None), expect="rejects")
    assert body["fields"] == F(5, "Oven 1", 185, None)
    assert (body["status"], body["ask"]) == ("need_field", "rejects")


def test_unknown_machine_clears_draft_machine():
    body = post_parse("oven teen", draft=F(16, "Oven 2", 175, 4))
    assert body["status"] == "confirm_machine" and body["fields"]["machine"] is None


def test_out_of_range_batch_is_impossible():
    body = post_parse("batch 12345 oven 1 180 degree 2 reject")
    assert body["problems"] == [{"field": "batch_no", "value": 12345, "reason": "impossible"}]
    assert (body["status"], body["ask"]) == ("need_field", "batch_no")
