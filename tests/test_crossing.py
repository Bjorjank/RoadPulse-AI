import pytest

from roadpulse.analytics.crossing import LineCounter
from roadpulse.jobs.schemas import StartRequest


@pytest.mark.parametrize(
    "line,first,last",
    [
        ([[0, 0.5], [1, 0.5]], (50, 20), (50, 80)),
        ([[0.5, 1], [0.5, 0]], (20, 50), (80, 50)),
        ([[0, 0], [1, 1]], (70, 30), (30, 70)),
    ],
)
def test_orientations(line, first, last):
    counter = LineCounter(line, 100, 100)
    assert counter.update(1, "car", first, 0, 10) is None
    event = counter.update(1, "car", last, 10, 10)
    assert event["direction"] == "A_TO_B"
    assert event["video_seconds"] == 1
    assert counter.counts["car"] == 1


def test_duplicate_hysteresis_and_return():
    c = LineCounter([[0, 0.5], [1, 0.5]], 100, 100)
    for frame, y in enumerate([20, 49, 51, 48, 52]):
        assert c.update(9, "truck", (50, y), frame, 30) is None
    assert c.update(9, "truck", (50, 80), 6, 30)["direction"] == "A_TO_B"
    assert c.update(9, "truck", (50, 20), 7, 30)["direction"] == "B_TO_A"
    assert c.update(9, "truck", (50, 80), 8, 30) is None
    assert c.counts["truck"] == 2


def test_segment_limits():
    c = LineCounter([[0.3, 0.5], [0.7, 0.5]], 100, 100)
    c.update(1, "bus", (90, 20), 0, 30)
    assert c.update(1, "bus", (90, 80), 1, 30) is None


def test_independent_classes():
    c = LineCounter([[0, 0.5], [1, 0.5]], 100, 100)
    for track, name in enumerate(["car", "motorcycle", "bus", "truck"]):
        c.update(track, name, (20, 20), 0, 30)
        c.update(track, name, (20, 80), 1, 30)
    assert list(c.counts.values()) == [1, 1, 1, 1]


def test_normalized_mapping():
    c = LineCounter([[0.2, 0.3], [0.8, 0.7]], 1000, 500)
    assert c.a == (200, 150)
    assert c.b == (800, 350)


@pytest.mark.parametrize(
    "line",
    [
        [{"x": -1, "y": 0}, {"x": 1, "y": 1}],
        [{"x": 0, "y": 0}, {"x": 0, "y": 0}],
        [{"x": float("nan"), "y": 0}, {"x": 1, "y": 1}],
    ],
)
def test_invalid(line):
    with pytest.raises(ValueError):
        StartRequest(line=line)
