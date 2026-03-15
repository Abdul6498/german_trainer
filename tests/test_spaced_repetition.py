from engine.spaced_repetition import SpacedRepetitionEngine


def test_wrong_answer_is_due_immediately() -> None:
    engine = SpacedRepetitionEngine(difficulty="medium")
    updated = engine.update({"correct_count": 3, "wrong_count": 0}, is_correct=False)
    assert updated["wrong_count"] == 1
    assert isinstance(updated["next_review"], str)


def test_due_when_missing_next_review() -> None:
    engine = SpacedRepetitionEngine()
    assert engine.is_due({}) is True
