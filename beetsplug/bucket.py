"""Provides the %bucket{} function for path formatting."""

from __future__ import annotations

import re
import string
from datetime import datetime
from itertools import tee
from typing import TYPE_CHECKING, TypedDict, TypeVar

from beets import plugins
from beets.exceptions import UserError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

ASCII_DIGITS = string.digits + string.ascii_lowercase
T = TypeVar("T")
YearSpan = TypedDict(
    "YearSpan", {"from": int, "to": int, "str": str}, total=False
)


class SpanFormat(TypedDict):
    fromnchars: int
    tonchars: int
    fmt: str


class BucketError(Exception):
    pass


def pairwise(iterable: Iterable[T]) -> Iterator[tuple[T, T]]:
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def span_from_str(span_str: str) -> YearSpan:
    """Build a span dict from the span string representation."""

    def normalize_year(d: int, yearfrom: int) -> int:
        """Convert string to a 4 digits year"""
        if yearfrom < 100:
            raise BucketError(f"{yearfrom} must be expressed on 4 digits")

        # if two digits only, pick closest year that ends by these two
        # digits starting from yearfrom
        if d < 100:
            if (d % 100) < (yearfrom % 100):
                d = (yearfrom - yearfrom % 100) + 100 + d
            else:
                d = (yearfrom - yearfrom % 100) + d
        return d

    years = [int(x) for x in re.findall(r"\d+", span_str)]
    if not years:
        raise UserError(
            f"invalid range defined for year bucket {span_str!r}: no year found"
        )
    try:
        years = [normalize_year(x, years[0]) for x in years]
    except BucketError as exc:
        raise UserError(
            f"invalid range defined for year bucket {span_str!r}: {exc}"
        )

    res: YearSpan = {"from": years[0], "str": span_str}
    if len(years) > 1:
        res["to"] = years[-1]
    return res


def complete_year_spans(spans: list[YearSpan]) -> None:
    """Set the `to` value of spans if empty and sort them chronologically."""
    spans.sort(key=lambda x: x["from"])
    for x, y in pairwise(spans):
        if "to" not in x:
            x["to"] = y["from"] - 1
    if spans and "to" not in spans[-1]:
        spans[-1]["to"] = datetime.now().year


def extend_year_spans(
    spans: list[YearSpan], spanlen: int, start: int = 1900, end: int = 2014
) -> list[YearSpan]:
    """Add new spans to given spans list so that every year of [start,end]
    belongs to a span.
    """
    extended_spans = spans[:]
    for x, y in pairwise(spans):
        # if a gap between two spans, fill the gap with as much spans of
        # spanlen length as necessary
        for span_from in range(x["to"] + 1, y["from"], spanlen):
            extended_spans.append({"from": span_from})
    # Create spans prior to declared ones
    for span_from in range(spans[0]["from"] - spanlen, start, -spanlen):
        extended_spans.append({"from": span_from})
    # Create spans after the declared ones
    for span_from in range(spans[-1]["to"] + 1, end, spanlen):
        extended_spans.append({"from": span_from})

    complete_year_spans(extended_spans)
    return extended_spans


def build_year_spans(year_spans_str: Iterable[str]) -> list[YearSpan]:
    """Build a chronologically ordered list of spans dict from unordered spans
    stringlist.
    """
    spans = []
    for elem in year_spans_str:
        spans.append(span_from_str(elem))
    complete_year_spans(spans)
    return spans


def str2fmt(s: str) -> SpanFormat:
    """Deduces formatting syntax from a span string."""
    regex = re.compile(
        r"(?P<bef>\D*)(?P<fromyear>\d+)(?P<sep>\D*)"
        r"(?P<toyear>\d*)(?P<after>\D*)"
    )
    m = re.match(regex, s)

    if m:
        fromnchars = len(m.group("fromyear"))
        tonchars = len(m.group("toyear"))
        fmt = f"{m['bef']}{{}}{m['sep']}{'{}' if tonchars else ''}{m['after']}"
    else:
        fromnchars = tonchars = 0
        fmt = "{}"

    return {"fromnchars": fromnchars, "tonchars": tonchars, "fmt": fmt}


def format_span(
    fmt: str, yearfrom: int, yearto: int, fromnchars: int, tonchars: int
) -> str:
    """Return a span string representation."""
    args = [str(yearfrom)[-fromnchars:]]
    if tonchars:
        args.append(str(yearto)[-tonchars:])

    return fmt.format(*args)


def extract_modes(spans: Iterable[YearSpan]) -> tuple[int, SpanFormat]:
    """Extract the most common spans lengths and representation formats"""
    rangelen = sorted([x["to"] - x["from"] + 1 for x in spans])
    deflen = sorted(rangelen, key=rangelen.count)[-1]
    reprs = [str2fmt(x["str"]) for x in spans]
    deffmt = sorted(reprs, key=reprs.count)[-1]
    return deflen, deffmt


def build_alpha_spans(
    alpha_spans_str: Iterable[str], alpha_regexs: dict[str, str]
) -> list[re.Pattern[str]]:
    """Extract alphanumerics from string and return sorted list of chars
    [from...to]
    """
    spans = []

    for elem in alpha_spans_str:
        if elem in alpha_regexs:
            spans.append(re.compile(alpha_regexs[elem]))
        else:
            bucket = sorted([x for x in elem.lower() if x.isalnum()])
            if bucket:
                begin_index = ASCII_DIGITS.index(bucket[0])
                end_index = ASCII_DIGITS.index(bucket[-1])
            else:
                raise UserError(
                    "invalid range defined for alpha bucket "
                    f"'{elem}': no alphanumeric character found"
                )
            spans.append(
                re.compile(
                    rf"^[{ASCII_DIGITS[begin_index : end_index + 1]}]",
                    re.IGNORECASE,
                )
            )
    return spans


class BucketPlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.template_funcs["bucket"] = self._tmpl_bucket

        self.config.add(
            {
                "bucket_year": [],
                "bucket_alpha": [],
                "bucket_alpha_regex": {},
                "extrapolate": False,
            }
        )
        self.setup()

    def setup(self) -> None:
        """Setup plugin from config options"""
        self.year_spans = build_year_spans(self.config["bucket_year"].get())
        if self.year_spans and self.config["extrapolate"]:
            [self.ys_len_mode, self.ys_repr_mode] = extract_modes(
                self.year_spans
            )
            self.year_spans = extend_year_spans(
                self.year_spans, self.ys_len_mode
            )

        self.alpha_spans = build_alpha_spans(
            self.config["bucket_alpha"].get(),
            self.config["bucket_alpha_regex"].get(),
        )

    def find_bucket_year(self, year: str) -> str:
        """Return  bucket that matches given year or return the year
        if no matching bucket.
        """
        for ys in self.year_spans:
            if ys["from"] <= int(year) <= ys["to"]:
                if "str" in ys:
                    return ys["str"]
                return format_span(
                    self.ys_repr_mode["fmt"],
                    ys["from"],
                    ys["to"],
                    self.ys_repr_mode["fromnchars"],
                    self.ys_repr_mode["tonchars"],
                )
        return year

    def find_bucket_alpha(self, s: str) -> str:
        """Return alpha-range bucket that matches given string or return the
        string initial if no matching bucket.
        """
        for i, span in enumerate(self.alpha_spans):
            if span.match(s):
                return self.config["bucket_alpha"].get()[i]
        return s[0].upper()

    def _tmpl_bucket(self, text: str, field: str | None = None) -> str:
        if not field and len(text) == 4 and text.isdigit():
            field = "year"

        func: Callable[[str], str]
        if field == "year":
            func = self.find_bucket_year
        else:
            func = self.find_bucket_alpha
        return func(text)
