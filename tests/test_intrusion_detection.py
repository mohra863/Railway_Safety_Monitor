import unittest
from src.intrusion_detection import IntrusionDetector
from src.detector import Detection
from src.tracker import IoUTracker
from src.alert_manager import AlertManager

class IntrusionTests(unittest.TestCase):
    def test_only_inside_generates_entry_transition(self):
        zone = IntrusionDetector([(0,0),(1,0),(1,1),(0,1)])
        self.assertEqual(zone.update(1, (50,50), (100,100)), (True, True))
        self.assertEqual(zone.update(1, (51,51), (100,100)), (False, True))

    def test_outside_is_not_intrusion_and_reentry_is(self):
        zone = IntrusionDetector([(0.4,0.4),(0.8,0.4),(0.8,0.8),(0.4,0.8)])
        self.assertEqual(zone.update(8, (10,10), (100,100)), (False, False))
        self.assertEqual(zone.update(8, (50,50), (100,100)), (True, True))
        self.assertEqual(zone.update(8, (10,10), (100,100)), (False, False))
        self.assertEqual(zone.update(8, (50,50), (100,100)), (True, True))

    def test_tracker_associates_same_person(self):
        tracker = IoUTracker()
        first = tracker.update([Detection((0,0,20,40), .8)])[0].track_id
        second = tracker.update([Detection((1,0,21,40), .7)])[0].track_id
        self.assertEqual(first, second)

    def test_alert_cooldown(self):
        manager = AlertManager(10)
        self.assertIsNotNone(manager.create(2,.8,"cam","0s",0))
        self.assertIsNone(manager.create(2,.8,"cam","2s",2))
        self.assertIsNotNone(manager.create(2,.8,"cam","11s",11))

if __name__ == "__main__": unittest.main()
