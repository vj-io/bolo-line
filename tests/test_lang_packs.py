"""Language packs (server/lang/<code>.json): what every pack must hold, what `/api/config` shows of
them, and that a caller who sends no `lang` still gets the body from before the packs existed.

The shape tests run over every pack in the folder, so a new language is checked by adding its file.
"""
import string

import pytest
from fastapi.testclient import TestClient

from server import config, parser
from server.main import app

client = TestClient(app)
PACKS = list(config.LANGS.values())
IDS = [p["code"] for p in PACKS]
PROMPT_KEYS = {"ask_batch_no", "ask_machine", "ask_temperature_c", "ask_rejects", "confirm_machine", "no_speech",
               "not_understood", "unclear_confirm", "retry", "saved", "readback", "wrong_language"}
LABEL_KEYS = {"mic", "mic_unavailable", "yes", "no", "temp_limit", "rejects_limit", "example"}
ROLES = {"batch", "degree", "temperature", "reject", "none", "any", "skip"}
# What a template may ask for: `text` is spoken (machine names in the pack's script), `roman` is shown.
PLACEHOLDERS = {"text": {"batch_no", "temperature_c", "rejects", "machine_local", "machines_local"},
                "roman": {"batch_no", "temperature_c", "rejects", "machine", "machines"}}


def fields_of(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_hindi_is_first_and_marathi_is_there():
    assert IDS[0] == "hi" and "mr" in IDS
    assert config.LANGS["hi"]["status"] == "ready" and config.LANGS["mr"]["status"] == "beta"


@pytest.mark.parametrize("pack", PACKS, ids=IDS)
def test_pack_shape(pack):
    assert pack["locale"].startswith(pack["code"] + "-") and pack["name"] and pack["name_en"]
    assert pack["status"] in ("ready", "beta")
    assert pack["status"] == "ready" or len(pack["notes"]) > 40  # a beta pack says what is unchecked
    assert set(pack["keywords"]) == ROLES
    assert pack["keywords"]["batch"] and pack["keywords"]["reject"] and pack["yes"] and pack["no"]
    assert set(pack["labels"]) == LABEL_KEYS and all(pack["labels"].values())
    assert fields_of(pack["labels"]["temp_limit"]) == {"min", "max"}
    assert fields_of(pack["labels"]["rejects_limit"]) == {"max"}
    assert set(pack["or"]) == {"text", "roman"}
    assert set(pack["prompts"]) == PROMPT_KEYS
    for key, template in pack["prompts"].items():
        assert set(template) == {"text", "roman"} and template["text"] and template["roman"], key
        for form in ("text", "roman"):
            assert fields_of(template[form]) <= PLACEHOLDERS[form], (key, form)
    for sample in pack["samples"]:
        assert set(sample) == {"id", "label", "when", "text", "audio_url"}


@pytest.mark.parametrize("pack", PACKS, ids=IDS)
def test_every_pack_word_is_in_the_packs_own_script(pack):
    # A word in another Indic script could never match: the script check refuses the sentence first.
    P = parser.PACKS[pack["code"]]
    n = pack["numbers"]
    listed = [w for ws in pack["keywords"].values() for w in ws] + pack["yes"] + pack["no"]
    listed += [a for m in pack["machines"].values() for a in m["aliases"] + [m["name"]]]
    listed += n["hundred"] + n["thousand"] + list(n["half_hundred"]) + [c["phrase"] for c in n["colloquial"]]
    listed += [w for s in n["words"].values() for w in s.split()] + list(n["table"] or {})
    listed += [t["text"] for t in pack["prompts"].values()] + [s["text"] for s in pack["samples"]]
    assert len(listed) > 60
    assert [w for w in listed if parser._other_script(w, P)] == []


@pytest.mark.parametrize("pack", PACKS, ids=IDS)
def test_colloquial_numbers_are_marked_unconfirmed_or_name_who_confirmed(pack):
    for entry in pack["numbers"]["colloquial"]:
        assert set(entry) == {"phrase", "value", "confirmed_by"}


def test_marathi_colloquial_list():
    got = {c["phrase"]: c["value"] for c in config.LANGS["mr"]["numbers"]["colloquial"]}
    assert got == {"दीडशे": 150, "अडीचशे": 250, "शंभर": 100, "एकशे": 100}
    assert all(c["confirmed_by"] is None for c in config.LANGS["mr"]["numbers"]["colloquial"])


def test_a_pack_whose_phrase_means_two_numbers_is_refused():
    pack = dict(config.LANGS["mr"], numbers=dict(config.LANGS["mr"]["numbers"],
                                                colloquial=[{"phrase": "शं भर", "value": 101, "confirmed_by": None}]))  # शंभर is 100
    with pytest.raises(ValueError):
        parser._compile(pack)


def test_hindi_pack_prompts_are_the_prompts_file():
    # server/prompts.json is still what `/api/config` serves as `prompts`; the Hindi pack holds the
    # same eleven lines in the pack shape. This keeps the two copies from drifting.
    pack = config.LANGS["hi"]["prompts"]
    assert set(pack) - set(config.PROMPTS) == {"wrong_language"}
    for key, old in config.PROMPTS.items():
        assert {"hi": pack[key]["text"].replace("_local}", "_hi}"), "roman": pack[key]["roman"]} == old


# ---------- /api/config ----------
def test_config_lists_languages_and_keeps_the_old_fields():
    body = client.get("/api/config").json()
    assert set(body) == {"station", "engines", "samples", "prompts", "languages"}
    assert body["prompts"] == config.PROMPTS and body["samples"] == config.SAMPLES
    assert [(l["code"], l["locale"], l["name"], l["name_en"], l["status"]) for l in body["languages"]] == [
        ("hi", "hi-IN", "हिंदी", "Hindi", "ready"), ("mr", "mr-IN", "मराठी", "Marathi", "beta")]
    for entry in body["languages"]:
        assert set(entry) == {"code", "locale", "name", "name_en", "status", "labels", "prompts", "samples"}
        assert set(entry["labels"]) == LABEL_KEYS and set(entry["prompts"]) == PROMPT_KEYS
        assert all(s["lang"] == entry["code"] for s in entry["samples"])
    mr = body["languages"][1]
    assert (mr["labels"]["mic"], mr["labels"]["yes"], mr["labels"]["no"]) == ("दाबून बोला", "हो", "नाही")
    assert mr["prompts"]["saved"] == {"text": "सेव्ह झालं", "roman": "Save jhala"}
    hi = body["languages"][0]
    assert (hi["labels"]["mic"], hi["labels"]["yes"], hi["labels"]["no"]) == ("Daba ke bolo", "Haan", "Nahi")
    assert hi["samples"] == []


def test_marathi_samples_have_no_recording_and_parse():
    samples = {s["id"]: s for s in client.get("/api/config").json()["languages"][1]["samples"]}
    assert set(samples) == {"mr1", "mr2"} and all(s["audio_url"] is None for s in samples.values())

    def run(sample_id):
        r = client.post("/api/parse", json={"station_id": "oven-line", "text": samples[sample_id]["text"], "lang": "mr"})
        return r.json()

    one, two = run("mr1"), run("mr2")
    assert (one["status"], one["fields"]) == ("complete", {"batch_no": 14, "machine": "Oven 2", "temperature_c": 180, "rejects": 3})
    assert (two["status"], two["fields"]) == ("complete", {"batch_no": 15, "machine": "Oven 1", "temperature_c": 210, "rejects": 2})
    assert two["flags"] == {"temp_out_of_limit": True, "rejects_over_limit": False}


# ---------- the body with and without `lang` ----------
OLD_KEYS = {"status", "fields", "ask", "suggest", "problems", "flags", "say"}
SENTENCE = "Batch chaudah, oven do, ek sau assi degree, teen reject"


def test_request_without_lang_gets_the_old_body():
    body = client.post("/api/parse", json={"station_id": "oven-line", "text": SENTENCE}).json()
    assert set(body) == OLD_KEYS
    assert body["say"] == {"hi": "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?",
                           "roman": "Batch 14, Oven 2, 180 degree, 3 reject. Sahi hai?"}


def test_request_with_lang_hi_adds_text_lang_and_hint():
    body = client.post("/api/parse", json={"station_id": "oven-line", "text": SENTENCE, "lang": "hi"}).json()
    assert set(body) == OLD_KEYS | {"hint"} and body["hint"] is None
    assert body["say"] == {"hi": "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?",
                           "roman": "Batch 14, Oven 2, 180 degree, 3 reject. Sahi hai?",
                           "text": "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?", "lang": "hi-IN"}
    old = client.post("/api/parse", json={"station_id": "oven-line", "text": SENTENCE}).json()
    assert {k: body[k] for k in OLD_KEYS - {"say"}} == {k: old[k] for k in OLD_KEYS - {"say"}}


def test_other_script_without_lang_keeps_the_old_body_shape():
    body = client.post("/api/parse", json={"station_id": "oven-line", "text": "ஓவன் இரண்டு"}).json()
    assert set(body) == OLD_KEYS and body["status"] == "not_understood"
    assert body["say"] == {"hi": "भाषा अलग लग रही है। ऊपर अपनी भाषा चुनिए",
                           "roman": "Bhasha alag lag rahi hai. Upar apni bhasha chuniye"}


def test_prompts_argument_replaces_the_packs_templates():
    custom = {"saved": {"hi": "x", "roman": "x"}, "not_understood": {"text": "नहीं समझा", "roman": "Nahi samjha"}}
    say = parser.parse("aaj mausam", config.STATION, custom)["say"]
    assert (say["text"], say["roman"]) == ("नहीं समझा", "Nahi samjha")
    say = parser.parse("", config.STATION, custom)["say"]  # a key the argument lacks comes from the pack
    assert say["roman"] == "Awaaz nahi aayi, phir se boliye"


def test_precomposed_nukta_letter_reads_like_the_two_code_point_form():
    # अड़तीस (38) with ड़ as one code point (U+095C) and as ड plus the nukta sign.
    for word in ("अड़तीस", "अड़तीस"):
        assert parser.parse(f"batch {word}", config.STATION)["fields"]["batch_no"] == 38


def test_old_prompt_templates_still_format():
    # server/prompts.json names the spoken machine {machine_hi} and {machines_hi}; a caller that
    # passes those templates gets the same lines as before.
    say = parser.parse(SENTENCE, config.STATION, config.PROMPTS)["say"]
    assert say["hi"] == "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?"
    say = parser.parse("batch 5 180 degree 3 reject", config.STATION, config.PROMPTS)["say"]
    assert (say["hi"], say["roman"]) == ("कौन सी मशीन? ओवन 1 या ओवन 2?", "Kaun si machine? Oven 1 ya Oven 2?")
    say = parser.parse("batch 5 oven 3 180 degree 3 reject", config.STATION, config.PROMPTS)["say"]
    assert say["hi"] == "ओवन 2 बोला? हाँ या नहीं?"


def test_text_none_is_no_speech():
    assert parser.parse(None, config.STATION)["status"] == "no_speech"
    assert parser.confirm(None) == "unclear"


def test_script_check_for_a_pack_in_another_script():
    # No Gujarati pack exists yet; this is the Marathi pack with Gujarati's block as its script.
    gu = parser._compile(dict(config.LANGS["mr"], script={"name": "Gujarati", "first": "0A80", "last": "0AFF"}))
    assert parser._other_script("बॅच चौदा", gu)             # Devanagari on a Gujarati station
    assert parser._other_script("பேட்ச்", gu)                # Tamil too
    assert not parser._other_script("બેચ ૧૪ batch 14", gu)   # its own script, digits, Latin
    assert not parser._other_script("બેચ ચૌદ। ॥", gu)        # the danda is not a Devanagari letter
    assert not parser._other_script("१४ ௧௪", gu)             # digits of other scripts
