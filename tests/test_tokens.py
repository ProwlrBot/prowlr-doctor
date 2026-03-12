from prowlr_doctor.tokens import count, display


def test_count_empty():
    assert count("") == 0


def test_count_nonempty():
    # Just verify it returns a positive int for real text
    assert count("Hello world") > 0


def test_display_zero():
    assert display(0) == "~0"


def test_display_small():
    result = display(300)
    assert result.startswith("~")


def test_display_thousands():
    result = display(133533)
    assert "k" in result
    assert "~" in result


def test_display_rounding():
    # 1200 → rounds to 1000 → ~1k
    assert display(1200) == "~1k"
    # 1300 → rounds to 1500 → ~2k? No: 1300/500=2.6 → round=3 → 1500 → ~2k
    result = display(133533)
    # 133533/500 = 267.066 → round = 267 → 133500 → ~134k
    assert "133" in result or "134" in result
