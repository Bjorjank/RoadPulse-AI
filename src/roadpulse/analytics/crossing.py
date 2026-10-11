from collections import Counter
from math import hypot


class LineCounter:
    """Bottom-center anchors, pixel hysteresis, finite segment, once per track/direction."""

    def __init__(self, line, width, height, hysteresis=4.0):
        self.a = (line[0][0] * width, line[0][1] * height)
        self.b = (line[1][0] * width, line[1][1] * height)
        self.dx, self.dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        self.length = hypot(self.dx, self.dy)
        if self.length < 1:
            raise ValueError("Counting line must have distinct endpoints")
        self.hysteresis = hysteresis
        self.history = {}
        self.counts = Counter()
        self.directions = Counter()

    def update(self, track_id, category, point, frame, fps):
        x, y = point
        distance = (self.dx * (y - self.a[1]) - self.dy * (x - self.a[0])) / self.length
        state = self.history.setdefault(track_id, {"point": None, "side": 0, "seen": set(), "last": frame})
        state["last"] = frame
        if abs(distance) <= self.hysteresis:
            return None
        side = 1 if distance > 0 else -1
        previous, old_side = state["point"], state["side"]
        state["point"], state["side"] = point, side
        if not old_side or side == old_side:
            return None
        old_distance = (
            self.dx * (previous[1] - self.a[1]) - self.dy * (previous[0] - self.a[0])
        ) / self.length
        fraction = old_distance / (old_distance - distance)
        intersection = (
            previous[0] + fraction * (x - previous[0]),
            previous[1] + fraction * (y - previous[1]),
        )
        projection = (
            (intersection[0] - self.a[0]) * self.dx + (intersection[1] - self.a[1]) * self.dy
        ) / self.length**2
        direction = "A_TO_B" if old_side < side else "B_TO_A"
        if not 0 <= projection <= 1 or direction in state["seen"]:
            return None
        state["seen"].add(direction)
        self.counts[category] += 1
        self.directions[direction] += 1
        return {
            "track_id": int(track_id),
            "category": category,
            "direction": direction,
            "frame": frame,
            "video_seconds": frame / fps,
        }

    def prune(self, frame, max_gap=300):
        for key in list(self.history):
            if frame - self.history[key]["last"] > max_gap:
                del self.history[key]
