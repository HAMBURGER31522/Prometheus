"""Hover lookup for English subtitles (PLAN 15.4.9): the offline ECDICT component, lemmas
and the API. The tests install from a small sample in ECDICT's own CSV format."""

import time
from pathlib import Path

import pytest
from prometheus.dictionary import ecdict

SAMPLE = Path(__file__).parent / "fixtures" / "ecdict.sample.csv"


@pytest.fixture
def data_dir(tmp_path):
    from prometheus import paths

    root = tmp_path / "data"
    paths.init_data_dir(root)
    return root


@pytest.fixture
def installed(data_dir):
    ecdict.install(data_dir, source=str(SAMPLE))
    return data_dir


def _view(entry):
    return None if entry is None else (entry["query"], entry["headword"], entry["inflection"])


def test_exchange_lists_the_forms_and_the_lemma():
    assert ecdict.parse_exchange("p:went/d:gone/i:going/3:goes") == {"p": "went", "d": "gone", "i": "going", "3": "goes"}
    assert ecdict.parse_exchange("0:go/1:p") == {"0": "go", "1": "p"}
    assert ecdict.parse_exchange("") == {}


def test_a_plain_word_has_its_phonetic_and_translation_lines(installed):
    entry = ecdict.lookup(installed, "Imagine")
    assert _view(entry) == ("Imagine", "imagine", None)
    assert entry["phonetic"] == "i'mædʒin"
    assert entry["translation"] == ["vt. 想象，设想；猜想", "vi. 想象"]


def test_an_inflected_form_shows_its_lemma(installed):
    entry = ecdict.lookup(installed, "went")
    assert _view(entry) == ("went", "go", "过去式")
    assert entry["translation"][0].startswith("vi. 去")
    assert _view(ecdict.lookup(installed, "sitting")) == ("sitting", "sit", "现在分词")


def test_a_form_missing_from_the_dictionary_falls_back_to_suffix_rules(installed):
    assert _view(ecdict.lookup(installed, "earns")) == ("earns", "earn", None)
    assert _view(ecdict.lookup(installed, "pockets")) == ("pockets", "pocket", None)
    assert _view(ecdict.lookup(installed, "rebalancing")) == ("rebalancing", "rebalance", None)
    assert ecdict.lookup(installed, "xyzzy") is None


def test_phrases_and_entries_without_translation_are_left_out(installed):
    assert _view(ecdict.lookup(installed, "sit")) == ("sit", "sit", None)
    assert ecdict.lookup(installed, "vacuum") is None
    assert ecdict.lookup(installed, "sit down") is None


def test_the_lowercase_entry_wins_over_a_capitalised_one(installed):
    entry = ecdict.lookup(installed, "polish")
    assert entry is not None and entry["translation"][0].startswith("vt. 擦亮")


def test_before_install_nothing_is_there(data_dir):
    assert not ecdict.installed(data_dir)
    with pytest.raises(ecdict.NotInstalled):
        ecdict.lookup(data_dir, "go")


def test_a_cut_download_leaves_nothing_installed(data_dir):
    def broken(url, *, proxy=""):
        raise OSError("connection reset")

    with pytest.raises(ecdict.DictionaryInstallError):
        ecdict.install(data_dir, source="https://example.invalid/ecdict.csv", open_source=broken)
    assert not ecdict.installed(data_dir)


def test_the_api_installs_on_request_then_looks_words_up(client):
    missing = client.get("/api/dictionary/lookup", params={"word": "went"})
    assert missing.status_code == 409 and missing.json()["code"] == "DICTIONARY_NOT_INSTALLED"
    assert client.post("/api/dictionary/install").json()["started"] is True
    deadline = time.time() + 10
    while client.get("/api/dictionary").json()["state"] != "ready" and time.time() < deadline:
        time.sleep(0.05)
    assert client.get("/api/dictionary").json()["state"] == "ready"
    found = client.get("/api/dictionary/lookup", params={"word": "went"})
    assert found.status_code == 200 and found.json()["headword"] == "go"
    unknown = client.get("/api/dictionary/lookup", params={"word": "xyzzy"})
    assert unknown.status_code == 404 and unknown.json()["code"] == "WORD_NOT_FOUND"
