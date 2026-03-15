from engine.sentence_generator import SentenceGenerator


def test_sentence_validation_requires_word() -> None:
    generator = SentenceGenerator()
    assert generator.validate_sentence("Ich sehe ein Haus.", ["Haus"])
    assert not generator.validate_sentence("Ich sehe ein Auto.", ["Haus"])
