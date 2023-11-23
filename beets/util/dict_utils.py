"""Utility functions for working with dictionaries."""


def merge_list_dicts(source, target):
    """Merges the value or list from the source dict into target dict list.

    If a list already exists for a given key in the target dict,
    the new item is appended or the two lists are merged.
    """
    for key, value in source.items():
        value_list = value if isinstance(value, list) else [value]
        if key in target:
            target[key] = target[key] + value_list
        else:
            target[key] = value_list
