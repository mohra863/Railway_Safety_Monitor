"""Small IoU-based tracker for associating detections across adjacent frames."""
from dataclasses import dataclass

def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2-x1) * max(0, y2-y1)
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    return inter / (area_a + area_b - inter) if area_a + area_b > inter else 0.0

@dataclass
class Track:
    track_id: int
    box: tuple[int, int, int, int]
    confidence: float
    missed: int = 0

class IoUTracker:
    def __init__(self, max_missed=12, iou_threshold=0.25):
        self.max_missed, self.iou_threshold = max_missed, iou_threshold
        self.tracks: dict[int, Track] = {}
        self.next_id = 1

    def update(self, detections):
        pairs = sorted(((iou(t.box, d.box), tid, di) for tid, t in self.tracks.items() for di, d in enumerate(detections)), reverse=True)
        used_tracks, used_dets = set(), set()
        for score, tid, di in pairs:
            if score < self.iou_threshold: break
            if tid in used_tracks or di in used_dets: continue
            det = detections[di]
            self.tracks[tid] = Track(tid, det.box, det.confidence)
            used_tracks.add(tid); used_dets.add(di)
        for tid in list(self.tracks):
            if tid not in used_tracks:
                self.tracks[tid].missed += 1
                if self.tracks[tid].missed > self.max_missed:
                    del self.tracks[tid]
        for di, det in enumerate(detections):
            if di not in used_dets:
                tid = self.next_id; self.next_id += 1
                self.tracks[tid] = Track(tid, det.box, det.confidence)
        return [t for t in self.tracks.values() if t.missed == 0]
