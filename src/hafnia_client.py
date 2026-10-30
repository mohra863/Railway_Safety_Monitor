"""Optional Hafnia VLM integration boundary; deliberately disabled until official API details exist."""
class HafniaClient:
    def __init__(self, enabled=False, **_):
        if enabled:
            raise RuntimeError("Hafnia integration is not configured: provide the official Gateway documentation and credentials before enabling it.")
        self.enabled = False

    def describe_event(self, image_path):
        raise RuntimeError("Hafnia VLM integration is disabled; no endpoint or request format is assumed.")
