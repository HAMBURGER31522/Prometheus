"""Item persistence (PLAN 7.1)."""


def create_item(data_dir, *, platform, video_id, source_url, figures=0, status="queued"):
    raise NotImplementedError


def get_item(data_dir, item_id):
    raise NotImplementedError


def list_items(data_dir, status=None, category_id=None):
    raise NotImplementedError


def update_item(data_dir, item_id, **fields):
    raise NotImplementedError


def delete_item(data_dir, item_id):
    raise NotImplementedError
