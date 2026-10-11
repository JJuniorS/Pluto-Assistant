from pluto.cleaner import clean, DEFAULT_FILLERS


def test_removes_isolated_fillers():
    assert clean("Hum, então, éé, vamos começar o projeto.") == "Então, vamos começar o projeto."


def test_keeps_verb_e_inside_sentence():
    assert clean("isso é muito bom") == "Isso é muito bom."


def test_removes_e_filler_at_sentence_start_with_pause():
    assert clean("É, acho que vai dar certo.") == "Acho que vai dar certo."


def test_removes_duplicated_words():
    assert clean("o o projeto está está pronto") == "O projeto está pronto."


def test_removes_duplicated_bigrams():
    assert clean("a gente a gente vai lá") == "A gente vai lá."


def test_normalizes_whitespace_and_punctuation_spacing():
    assert clean("  olá ,  mundo  .  tudo bem ?") == "Olá, mundo. Tudo bem?"


def test_capitalizes_each_sentence():
    assert clean("primeira frase. segunda frase! terceira?") == "Primeira frase. Segunda frase! Terceira?"


def test_custom_fillers_list():
    assert clean("tipo, isso aí é legal", fillers=["tipo"]) == "Isso aí é legal."


def test_ne_filler_removed_but_not_in_words():
    assert clean("ficou bom, né, o resultado") == "Ficou bom, o resultado."
    assert clean("o nenê dormiu") == "O nenê dormiu."


def test_tag_question_filler_becomes_period():
    assert clean("está quase pronto, né? Acesse o site") == "Está quase pronto. Acesse o site."


def test_empty_and_only_fillers():
    assert clean("") == ""
    assert clean("hum... éé... hã") == ""


def test_extra_steps_are_applied_last():
    assert clean("oi mundo", extra_steps=[str.upper]) == "OI MUNDO."


def test_default_fillers_exported():
    assert "hum" in DEFAULT_FILLERS
