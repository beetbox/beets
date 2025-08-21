"""
We found that using the beets library models can sometimes be frustrating because of
missing typehints for the model attributes and methods.

This script does the following in order:
- generates or overwrite the current models.pyi stub files.
- injects type hints for the __getitem__ method depending on the defined fields
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Union, get_args, get_origin

from beets.dbcore.types import get_type_parameters
from beets.library import Album, Item, LibModel

log = logging.getLogger(__name__)


def overload_template(key: str, return_type: type) -> list[str]:
    """Generate an overload for __getitem__ with a specific key and return type."""
    type_str = type2str(return_type)
    return [
        "@overload",
        f"def __getitem__(self, key: {key}) -> {type_str}: ...",
    ]


def type2str(tp: type) -> str:
    """Convert a Python type into a PEP 604 style string for stubs."""
    # Handle NoneType first since it doesn't have __name__
    if tp is None or tp is type(None):
        return "None"
    if tp is object:
        return "Any"

    origin = get_origin(tp)
    if origin is None:
        # It's a simple type
        return tp.__name__
    elif hasattr(origin, "__name__"):
        # It's a regular generic type like list, dict, etc.
        args = get_args(tp)
        if args:
            args_str = ", ".join(type2str(arg) for arg in args)
            return f"{origin.__name__}[{args_str}]"
        else:
            return origin.__name__
    else:
        # Handle special forms like Union, Optional, etc.
        args = get_args(tp)
        if origin is Union:
            return " | ".join(type2str(arg) for arg in args)
        else:
            # For other special forms, fall back to string representation
            return str(tp)


def generate_overloads(model: type[LibModel]) -> list[str]:
    """Generate overloads for __getitem__ based on Item._fields."""
    lines: list[str] = []
    count = 0
    for name, field_type in model._fields.items():
        return_type, null_type = get_type_parameters(field_type)
        lines.extend(
            overload_template(
                f"Literal['{name}']", Union[return_type, null_type]
            )
        )
        count += 1

    # Default str
    lines.extend(overload_template("str", object))

    log.info(f"Generated {count} overloads for {model.__name__}")
    return lines


def inject_overloads(stub_path: Path, model: type[LibModel]) -> None:
    """Insert generated overloads into the class definition in a .pyi file."""
    text = stub_path.read_text()

    class_name = model.__name__
    log.info(f"Injecting overloads for {class_name} into {stub_path}")

    # Find the class definition
    class_pattern = rf"^(class {class_name}\(.*\):)"
    match = re.search(class_pattern, text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"Class {class_name} not found in {stub_path}")

    # Where to insert
    insert_pos = match.end()

    # Prepare overload block and indent
    overloads = generate_overloads(model)
    overload_text = "\n".join(f"    {line}" for line in overloads)

    # Insert after class line
    new_text = text[:insert_pos] + "\n" + overload_text + text[insert_pos:]

    # Write result
    stub_path.write_text(new_text)
    log.info(f"Injected overloads into {stub_path}")


def run_stubgen(module: str, out_dir: Path) -> Path:
    """Run stubgen for a module and return the generated pyi path."""
    subprocess.run(
        ["stubgen", "-m", module, "--include-private", "-o", str(out_dir)],
        check=True,
    )
    # Figure out the generated file path
    pyi_path = out_dir / Path(module.replace(".", "/") + ".pyi")
    if not pyi_path.exists():
        raise FileNotFoundError(f"Stubgen did not generate {pyi_path}")
    return pyi_path


def format_file(stub_path: Path) -> None:
    """Run ruff fix on the generated stub file."""
    subprocess.run(
        [
            "ruff",
            "check",
            str(stub_path),
            "--fix",
            "--unsafe-fixes",
            "--silent",
        ],
        check=True,
    )


def ensure_imports(stub_path: Path) -> None:
    """Ensure multiple imports are present in the generated stub file."""
    text = stub_path.read_text()

    if "from typing import Literal" not in text:
        insert_pos = text.find(
            "from typing"
        )  # Attempt to find the first typing import
        if insert_pos == -1:
            # No existing import, add at the top of the file
            insert_pos = 0
        else:
            # Otherwise, find the position after the first import line
            insert_pos = text.find("\n", insert_pos) + 1

        # Add Literal import
        new_text = (
            text[:insert_pos]
            + "from typing import Literal, Any, overload\n"
            + text[insert_pos:]
        )
        stub_path.write_text(new_text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out_dir = Path(__file__).parent.parent
    file = run_stubgen("beets.library.models", out_dir)
    ensure_imports(file)
    inject_overloads(file, Item)
    inject_overloads(file, Album)
