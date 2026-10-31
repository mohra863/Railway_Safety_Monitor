import unittest

from src.crossing_detection import (
    STATUS_CONFIRMED,
    STATUS_NEGATIVE,
    STATUS_UNCERTAIN,
    classify_track_crossing,
    extract_evidence_frame,
    is_track_crossing_event,
)

CONFIRMED_SUMMARY = (
    "A person in a red jacket and black pants walks along the platform, "
    "approaches the yellow tactile paving, and steps onto the tracks. "
    "The person crosses the rails from the near platform to the far platform, "
    "then returns to the near platform and sits on the tactile paving. "
    "The crossing is visible and involves stepping onto and crossing the rails."
)

PLATFORM_SUMMARY = (
    "A person in a coat walks along the platform, approaches the yellow "
    "tactile paving, and remains on the platform for the entire clip. "
    "The railway tracks are visible beside the platform."
)

NO_CROSSING_SUMMARY = (
    "A person walks on the platform near the tracks. No crossing occurred "
    "and the person did not step onto the rails."
)

AMBIGUOUS_SUMMARY = (
    "A person is visible near the railway tracks at the station. "
    "The view includes the platform and the tracks."
)


class TestCrossingDetection(unittest.TestCase):
    def test_confirmed_crossing(self):
        result = classify_track_crossing(CONFIRMED_SUMMARY)
        self.assertTrue(result.is_crossing)
        self.assertEqual(result.status, STATUS_CONFIRMED)
        self.assertTrue(is_track_crossing_event(CONFIRMED_SUMMARY))
        self.assertIn("steps onto the tracks", result.description.lower())

    def test_person_remaining_on_platform(self):
        result = classify_track_crossing(PLATFORM_SUMMARY)
        self.assertFalse(result.is_crossing)
        self.assertEqual(result.status, STATUS_NEGATIVE)
        self.assertFalse(is_track_crossing_event(PLATFORM_SUMMARY))

    def test_summary_explicitly_stating_no_crossing(self):
        result = classify_track_crossing(NO_CROSSING_SUMMARY)
        self.assertFalse(result.is_crossing)
        self.assertEqual(result.status, STATUS_NEGATIVE)
        self.assertFalse(is_track_crossing_event(NO_CROSSING_SUMMARY))

    def test_ambiguous_summary_is_not_a_confirmed_crossing(self):
        result = classify_track_crossing(AMBIGUOUS_SUMMARY)
        self.assertFalse(result.is_crossing)
        self.assertEqual(result.status, STATUS_UNCERTAIN)
        self.assertFalse(is_track_crossing_event(AMBIGUOUS_SUMMARY))

    def test_hedged_crossing_language_is_uncertain(self):
        summary = (
            "It is unclear whether the person stepped onto the tracks. "
            "The person might have crossed the rails."
        )
        result = classify_track_crossing(summary)
        self.assertFalse(result.is_crossing)
        self.assertEqual(result.status, STATUS_UNCERTAIN)

    def test_empty_summary_is_uncertain(self):
        result = classify_track_crossing("")
        self.assertFalse(result.is_crossing)
        self.assertEqual(result.status, STATUS_UNCERTAIN)


class TestEvidenceFrameExtraction(unittest.TestCase):
    def test_text_only_gateway_payload_has_no_evidence_frame(self):
        payload = {
            "Id": "summary-1",
            "Progress": "Completed",
            "Response": CONFIRMED_SUMMARY,
            "Request": {
                "Prompt": "Describe what happens in this video.",
                "VideoUris": ["xprotect://localhost/cameras/CAM?StartTime=2026-10-31T10:00:00Z"],
            },
        }
        self.assertIsNone(extract_evidence_frame(payload))

    def test_http_image_url_is_returned_when_present(self):
        payload = {"ImageUrl": "https://example.invalid/frame.jpg", "Response": CONFIRMED_SUMMARY}
        self.assertEqual(extract_evidence_frame(payload), "https://example.invalid/frame.jpg")


if __name__ == "__main__":
    unittest.main()
