"""Hover lookup for English subtitles (PLAN 15.4.9): the offline ECDICT component, lemmas
and the API. The tests install from a small sample in ECDICT's own CSV format."""

import sqlite3
import time
from contextlib import closing
from pathlib import Path

import pytest
from prometheus.dictionary import ecdict

SAMPLE = Path(__file__).parents[1] / "fixtures" / "ecdict.sample.csv"


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


def test_a_short_row_is_skipped_not_fatal(data_dir, tmp_path):
    ragged = tmp_path / "ragged.csv"
    ragged.write_text(SAMPLE.read_text(encoding="utf-8") + "zebra,'zi:brə\n", encoding="utf-8")
    try:
        ecdict.install(data_dir, source=str(ragged))
    except Exception as exc:  # noqa: BLE001 - the point of the test
        pytest.fail(f"a short row broke the install: {exc!r}")
    assert _view(ecdict.lookup(data_dir, "went")) == ("went", "go", "过去式")
    assert ecdict.lookup(data_dir, "zebra") is None


# --- 英英释义 (PLAN 15.4.10) ------------------------------------------------------------------

SIT = ["v. be seated", "v. be around, often idly or without specific purpose", "v. take a seat"]


def _old_dictionary(data_dir):
    """What R7c installed: the same words without ECDICT's definition column."""
    target = ecdict.db_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as db:
        db.execute("CREATE TABLE words (key TEXT PRIMARY KEY, word TEXT, phonetic TEXT, translation TEXT, "
                   "exchange TEXT) WITHOUT ROWID")
        db.executemany("INSERT INTO words VALUES (?, ?, ?, ?, ?)", [
            ("go", "go", "gәu", "vi. 去，走；变为；运转\\nn. 尝试；轮到的机会", "p:went/d:gone/i:going/3:goes/s:goes"),
            ("went", "went", "went", "v. 去（go的过去式）", "0:go/1:p"),
        ])
        db.commit()


def test_up_to_three_english_definitions_come_with_the_chinese_meaning(installed):
    entry = ecdict.lookup(installed, "sitting")
    assert _view(entry) == ("sitting", "sit", "现在分词")
    assert entry["translation"] == ["vi. 坐；位于；栖息", "vt. 使就座"]
    assert entry["definition"] == SIT
    assert entry["needs_update"] is False


def test_definitions_of_the_chinese_meaning_s_part_of_speech_come_first(installed):
    # ECDICT lists the nouns of "go" first; went is a verb, and so is go's first Chinese meaning.
    assert ecdict.lookup(installed, "went")["definition"] == [
        "v. change location; move, travel, or proceed, also metaphorically",
        "v. follow a procedure or take a course",
        "n. a time for working (after which you will be relieved by someone else)",
    ]
    assert ecdict.lookup(installed, "pockets")["definition"] == [
        "n. a small pouch inside a garment for carrying small articles", "n. an enclosed space",
        "v. put in one's pocket"]


def test_wrapped_and_crlf_definition_lines_are_read_whole(installed):
    assert ecdict.lookup(installed, "rebalancing")["definition"] == [
        "v. bring back into balance, especially after a change in the size of its parts"]
    assert ecdict.lookup(installed, "money")["definition"] == [
        "n. the most common medium of exchange; functions as legal tender", "n. wealth reckoned in terms of money",
        "n. the official currency issued by a government or national bank"]


def test_a_word_without_english_definitions_has_none(installed):
    entry = ecdict.lookup(installed, "polish")
    assert entry["translation"][0].startswith("vt. 擦亮")
    assert entry["definition"] == [] and entry["needs_update"] is False
    assert ecdict.lookup(installed, "imagine")["definition"] == [
        "v. form a mental image of something that is not present or that is not the case",
        "v. expect, believe, or suppose"]


def test_an_old_dictionary_keeps_its_chinese_meanings_and_asks_for_an_update(data_dir):
    _old_dictionary(data_dir)
    entry = ecdict.lookup(data_dir, "went")
    assert _view(entry) == ("went", "go", "过去式")
    assert entry["translation"] == ["vi. 去，走；变为；运转", "n. 尝试；轮到的机会"]
    assert entry["definition"] == [] and entry["needs_update"] is True


def test_updating_an_old_dictionary_brings_the_definitions(data_dir):
    _old_dictionary(data_dir)
    ecdict.install(data_dir, source=str(SAMPLE))
    entry = ecdict.lookup(data_dir, "sitting")
    assert entry["definition"] == SIT and entry["needs_update"] is False


def _wait_for_install(client):
    deadline = time.time() + 10
    while client.get("/api/dictionary").json()["state"] == "installing" and time.time() < deadline:
        time.sleep(0.05)


def test_the_api_returns_the_english_definitions(client):
    assert client.post("/api/dictionary/install").json()["started"] is True
    _wait_for_install(client)
    found = client.get("/api/dictionary/lookup", params={"word": "sitting"}).json()
    assert found["definition"] == SIT and found["needs_update"] is False


def test_a_failed_update_says_why_while_the_old_dictionary_keeps_working(client, monkeypatch):
    _old_dictionary(client.app.state.data_dir)

    def cut(data_dir, **kwargs):
        raise ecdict.DictionaryInstallError("离线词典下载失败：连接被重置")

    monkeypatch.setattr(ecdict, "install", cut)
    assert client.post("/api/dictionary/install").json()["started"] is True
    _wait_for_install(client)
    status = client.get("/api/dictionary").json()
    assert status["state"] == "failed" and "连接被重置" in status["detail"]
    old = client.get("/api/dictionary/lookup", params={"word": "went"}).json()
    assert old["headword"] == "go" and old["translation"][0].startswith("vi. 去") and old["needs_update"] is True


def test_a_relative_data_dir_works(tmp_path, monkeypatch):
    from prometheus import paths

    monkeypatch.chdir(tmp_path)
    paths.init_data_dir(Path("data"))
    ecdict.install(Path("data"), source=str(SAMPLE))
    try:
        entry = ecdict.lookup(Path("data"), "went")
    except ValueError as exc:
        pytest.fail(f"lookup broke on a relative data dir: {exc!r}")
    assert _view(entry) == ("went", "go", "过去式")
