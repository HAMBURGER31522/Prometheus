class FakeModelApi:
    def __init__(self):
        self.requests = []
        self.keys = []
        self.url = "http://127.0.0.1:9"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
