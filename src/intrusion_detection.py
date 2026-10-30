"""Danger-zone geometry and per-track entry transition detection."""
class IntrusionDetector:
    def __init__(self, polygon):
        if len(polygon) < 3:
            raise ValueError("Danger zone requires at least three points")
        self.polygon = [(float(x), float(y)) for x, y in polygon]
        self._inside: dict[int, bool] = {}

    def contains(self, point):
        x, y = point
        inside = False
        points = self.polygon
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            if ((yi > y) != (yj > y)) and x < (xj-xi) * (y-yi) / ((yj-yi) or 1e-12) + xi:
                inside = not inside
            j = i
        return inside

    def update(self, track_id: int, foot_point_px, frame_size):
        width, height = frame_size
        point = (foot_point_px[0] / width, foot_point_px[1] / height)
        inside = self.contains(point)
        entered = inside and not self._inside.get(track_id, False)
        self._inside[track_id] = inside
        return entered, inside
