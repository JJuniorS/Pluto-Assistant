from pluto.snippets import expand

SNIPPETS = {
    "meu linkedin": "https://www.linkedin.com/in/fulano/",
    "meu email": "fulano@exemplo.com",
}


def test_whole_text_snippet_replaces_everything_including_punctuation():
    assert expand("Meu LinkedIn.", SNIPPETS) == "https://www.linkedin.com/in/fulano/"


def test_inline_snippet_is_replaced_case_insensitively():
    assert expand("Acesse meu linkedin para saber mais.", SNIPPETS) == (
        "Acesse https://www.linkedin.com/in/fulano/ para saber mais."
    )


def test_does_not_match_inside_other_words():
    assert expand("meu emailzão", SNIPPETS) == "meu emailzão"


def test_multiple_snippets():
    out = expand("Contato: meu email ou meu linkedin", SNIPPETS)
    assert out == "Contato: fulano@exemplo.com ou https://www.linkedin.com/in/fulano/"


def test_no_snippets():
    assert expand("texto normal", {}) == "texto normal"
