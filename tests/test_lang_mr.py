"""Marathi language pack: the test table and confirm cases of the language research (A4), through
`/api/parse` and `/api/confirm` with `lang: "mr"`.

Expected values are typed from the research table, never computed by the parser. The sentences were
written without a native speaker; the pack is marked beta for that reason.
"""
import pytest
from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)
NO_FLAGS = {"temp_out_of_limit": False, "rejects_over_limit": False}


def F(b, m, t, r):
    return {"batch_no": b, "machine": m, "temperature_c": t, "rejects": r}


def post(text, lang="mr", draft=None, expect=None):
    r = client.post("/api/parse", json={"station_id": "oven-line", "text": text, "draft": draft,
                                        "expect": expect, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


# (row, utterance, draft, expect, status, fields, ask, suggested machine)
MR_ROWS = [
    (1, "बॅच चौदा, ओव्हन दोन, एकशे ऐंशी डिग्री, तीन रिजेक्ट", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (2, "बॅच 14 ओव्हन 2 180 डिग्री 3 रिजेक्ट", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (3, "batch 14 ओव्हन 2 180 degree 3 reject", None, None, "complete", F(14, "Oven 2", 180, 3), None, None),
    (4, "batch fifteen, oven एक, दोनशे दहा degree, दोन reject", None, None, "complete", F(15, "Oven 1", 210, 2), None, None),
    (5, "बॅच सोळा, ओव्हन दोन, चार रिजेक्ट", None, None, "need_field", F(16, "Oven 2", None, 4), "temperature_c", None),
    (6, "एकशे पंच्याहत्तर", F(16, "Oven 2", None, 4), "temperature_c", "complete", F(16, "Oven 2", 175, 4), None, None),
    (7, "बॅच वीस, ओव्हन एक, नऊशे डिग्री, दोन रिजेक्ट", None, None, "need_field", F(20, "Oven 1", None, 2), "temperature_c", None),
    (8, "बॅच अठरा, ओव्हन तीन, एकशे ऐंशी डिग्री, एक रिजेक्ट", None, None, "confirm_machine", F(18, None, 180, 1), None, "Oven 2"),
    (9, "बॅच बावीस, ओव्हन एक, एकशे साठ डिग्री, रिजेक्ट नाही", None, None, "complete", F(22, "Oven 1", 160, 0), None, None),
    (10, "बॅच तेवीस, ओव्हन दोन, दीडशे डिग्री, शून्य रिजेक्ट", None, None, "complete", F(23, "Oven 2", 150, 0), None, None),
    (11, "बॅच सतरा, ओव्हन दोन, एकशे सत्तर डिग्री, सात रिजेक्ट", None, None, "complete", F(17, "Oven 2", 170, 7), None, None),
    (12, "आज पाऊस आहे", None, None, "not_understood", F(None, None, None, None), None, None),
]
MR = {row[0]: row for row in MR_ROWS}


def run(n):
    _, text, draft, expect, *_ = MR[n]
    return post(text, draft=draft, expect=expect)


@pytest.mark.parametrize("row", MR_ROWS, ids=[f"row{r[0]}" for r in MR_ROWS])
def test_marathi_table_row(row):
    _, text, draft, expect, status, fields, ask, suggest = row
    body = post(text, draft=draft, expect=expect)
    assert body["status"] == status
    assert body["fields"] == fields
    assert body["ask"] == ask
    assert (body["suggest"] or {}).get("value") == suggest
    assert body["hint"] is None


@pytest.mark.parametrize("n, temp_flag, rejects_flag", [
    (1, False, False), (4, True, False), (9, True, False), (10, True, False), (11, False, True),
])
def test_marathi_flags(n, temp_flag, rejects_flag):
    assert run(n)["flags"] == {"temp_out_of_limit": temp_flag, "rejects_over_limit": rejects_flag}


def test_marathi_row7_problem_is_the_impossible_temperature():
    assert run(7)["problems"] == [{"field": "temperature_c", "value": 900, "reason": "impossible"}]


def test_marathi_row8_unknown_machine():
    body = run(8)
    assert body["problems"] == [{"field": "machine", "value": "oven 3", "reason": "unknown_machine"}]
    assert body["suggest"] == {"field": "machine", "value": "Oven 2"}


# The prompts of the research file (A2.5): `text` is spoken, `roman` is shown.
@pytest.mark.parametrize("n, text, roman", [
    (1, "बॅच 14, ओव्हन 2, 180 डिग्री, 3 रिजेक्ट. बरोबर आहे?", "Batch 14, Oven 2, 180 degree, 3 reject. Barobar aahe?"),
    (5, "टेंपरेचर किती होतं?", "Temperature kiti hota?"),
    (8, "ओव्हन 2 म्हणालात? हो की नाही?", "Oven 2 mhanalat? Ho ki nahi?"),
    (12, "समजलं नाही, पुन्हा बोला", "Samajla nahi, punha bola"),
], ids=["readback", "ask_temperature", "confirm_machine", "not_understood"])
def test_marathi_say(n, text, roman):
    assert run(n)["say"] == {"hi": text, "roman": roman, "text": text, "lang": "mr-IN"}


@pytest.mark.parametrize("utterance, text, roman", [
    ("ओव्हन दोन, एकशे ऐंशी डिग्री, तीन रिजेक्ट", "बॅच नंबर काय आहे?", "Batch number kay aahe?"),
    ("बॅच 5, 180 डिग्री, 3 रिजेक्ट", "कोणती मशीन? ओव्हन 1 की ओव्हन 2?", "Konti machine? Oven 1 ki Oven 2?"),
    ("बॅच 5, ओव्हन 1, 180 डिग्री", "किती रिजेक्ट झाले?", "Kiti reject jhale?"),
    ("", "आवाज आला नाही, पुन्हा बोला", "Aavaj aala nahi, punha bola"),
], ids=["ask_batch", "ask_machine", "ask_rejects", "no_speech"])
def test_marathi_questions(utterance, text, roman):
    say = post(utterance)["say"]
    assert (say["text"], say["roman"]) == (text, roman)


@pytest.mark.parametrize("text, answer", [
    ("हो", "yes"), ("होय", "yes"), ("बरोबर आहे", "yes"), ("yes", "yes"),
    ("नाही", "no"), ("नको", "no"), ("बरोबर नाही", "no"), ("चूक", "no"),
    ("काय", "unclear"), ("", "unclear"),
])
def test_marathi_confirm(text, answer):
    r = client.post("/api/confirm", json={"text": text, "lang": "mr"})
    assert r.status_code == 200 and r.json() == {"answer": answer}


def test_confirm_words_belong_to_one_language():
    # Hindi "haan" is not a Marathi yes-word and Marathi "हो" is not a Hindi one.
    assert client.post("/api/confirm", json={"text": "haan", "lang": "mr"}).json() == {"answer": "unclear"}
    assert client.post("/api/confirm", json={"text": "हो", "lang": "hi"}).json() == {"answer": "unclear"}
    assert client.post("/api/confirm", json={"text": "हो"}).json() == {"answer": "unclear"}


@pytest.mark.parametrize("text, fields", [
    ("batch 14 oven 2 180 degree 3 reject", F(14, "Oven 2", 180, 3)),
    ("batch seventeen oven two one eighty five degree seven rejects", F(17, "Oven 2", 185, 7)),
    ("batch 24 oven 2 one hundred and eighty two degrees zero rejects", F(24, "Oven 2", 182, 0)),
    ("oven 1 batch number twenty temperature 175 reject nil", F(20, "Oven 1", 175, 0)),
])
def test_english_and_digits_read_the_same_in_every_language(text, fields):
    hi, mr = post(text, lang="hi"), post(text, lang="mr")
    assert hi["fields"] == fields and mr["fields"] == fields
    assert hi["status"] == mr["status"] == "complete"


@pytest.mark.parametrize("text, temp", [
    ("दीडशे डिग्री", 150), ("अडीचशे डिग्री", 250), ("शंभर डिग्री", 100), ("एकशे डिग्री", 100),
])
def test_marathi_colloquial_numbers(text, temp):
    assert post(text)["fields"]["temperature_c"] == temp


def test_marathi_thousand():
    assert post("बॅच दोन हजार पाचशे")["fields"]["batch_no"] == 2500


def test_split_number_is_joined_but_never_across_a_comma():
    # A recogniser may write एकवीस (21) as two words. The same two words with a comma between them
    # are two numbers: machine 1, then 20 rejects.
    assert post("बॅच एक वीस")["fields"]["batch_no"] == 21
    body = post("बॅच 5, ओव्हन एक, वीस रिजेक्ट")
    assert (body["fields"]["machine"], body["fields"]["rejects"]) == ("Oven 1", 20)


def test_eyelash_ra_in_either_encoding():
    # 74 as CLDR writes it (र, virama, zero-width joiner) and with the single letter ऱ (U+0931).
    assert post("बॅच चौर्‍याहत्तर")["fields"]["batch_no"] == 74
    assert post("बॅच चौऱ्याहत्तर")["fields"]["batch_no"] == 74


def test_number_words_belong_to_one_language():
    # 17 is "satrah" / सत्रह in Hindi and सतरा in Marathi; 2 is दो and दोन. Only the selected
    # language's words are numbers.
    assert post("batch सतरा", lang="mr")["fields"]["batch_no"] == 17
    assert post("batch सतरा", lang="hi")["fields"]["batch_no"] is None
    assert post("batch सत्रह", lang="hi")["fields"]["batch_no"] == 17
    assert post("batch सत्रह", lang="mr")["fields"]["batch_no"] is None
    assert post("batch satrah", lang="mr")["fields"]["batch_no"] is None
    assert post("ओव्हन दोन", lang="mr")["fields"]["machine"] == "Oven 2"
    assert post("ओवन दोन", lang="hi")["fields"]["machine"] is None


@pytest.mark.parametrize("text", [
    "બેચ ચૌદ, ઓવન બે, એક સો એંસી ડિગ્રી, ત્રણ રિજેક્ટ",       # Gujarati
    "பேட்ச் பதினான்கு, ஓவன் இரண்டு, நூற்று எண்பது டிகிரி",  # Tamil
    "batch 14 ஓவன் 2 180 degree 3 reject",                     # one Tamil word among English
])
@pytest.mark.parametrize("lang", ["mr", "hi"])
def test_other_script_is_refused_with_a_hint(text, lang):
    body = post(text, lang=lang)
    assert (body["status"], body["hint"]) == ("not_understood", "wrong_language")
    assert body["fields"] == F(None, None, None, None) and body["flags"] == NO_FLAGS


def test_wrong_language_prompt_and_draft():
    body = post("ஓவன் இரண்டு", draft=F(16, None, 175, 4), expect="machine")
    assert (body["status"], body["hint"], body["ask"]) == ("not_understood", "wrong_language", None)
    assert body["say"] == {"hi": "भाषा वेगळी वाटते. वर तुमची भाषा निवडा", "roman": "Bhasha vegli vatte. Var tumchi bhasha nivda",
                           "text": "भाषा वेगळी वाटते. वर तुमची भाषा निवडा", "lang": "mr-IN"}


@pytest.mark.parametrize("text, batch", [
    ("batch ૧૪", 14),            # Gujarati digits: digits of any script are allowed
    ("batch 14।", 14),           # the danda is shared by every Indic script
    ("बॅच 14 oven 2", 14),       # Latin and Devanagari together
])
def test_script_check_lets_digits_latin_and_danda_through(text, batch):
    body = post(text)
    assert (body["hint"], body["fields"]["batch_no"]) == (None, batch)


@pytest.mark.parametrize("path, body", [
    ("/api/parse", {"station_id": "oven-line", "text": "batch 5", "lang": "xx"}),
    ("/api/confirm", {"text": "yes", "lang": "xx"}),
])
def test_unknown_language_is_404(path, body):
    r = client.post(path, json=body)
    assert r.status_code == 404 and r.json()["error"] == "unknown_language"


def test_number_split_into_more_words_than_the_table_writes():
    # एकशे ऐंशी (180) is two words in the table; a recogniser may write three.
    assert post("एक शे ऐंशी डिग्री")["fields"]["temperature_c"] == 180
    assert post("दोन शे दहा डिग्री")["fields"]["temperature_c"] == 210
