from typing import List

MULTI_TAG_SEPARATOR: str = '\0'


def multi_to_str(multi: List[str]) -> str:
    return MULTI_TAG_SEPARATOR.join(multi)

