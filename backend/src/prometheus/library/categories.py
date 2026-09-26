"""Category persistence (PLAN 7.1)."""


def list_categories(data_dir):
    raise NotImplementedError


def create_category(data_dir, name):
    raise NotImplementedError


def rename_category(data_dir, category_id, name):
    raise NotImplementedError


def delete_category(data_dir, category_id):
    raise NotImplementedError


def merge_category(data_dir, category_id, into_id):
    raise NotImplementedError


def ensure_category(data_dir, name):
    raise NotImplementedError
