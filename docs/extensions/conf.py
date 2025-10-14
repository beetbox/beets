"""Sphinx extension for simple configuration value documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from docutils.nodes import Element
    from docutils.parsers.rst.states import Inliner
    from sphinx.addnodes import desc_signature, pending_xref
    from sphinx.application import Sphinx
    from sphinx.builders import Builder
    from sphinx.environment import BuildEnvironment
    from sphinx.util.typing import ExtensionMetadata, OptionSpec


class Conf(ObjectDescription[str]):
    """Directive for documenting a single configuration value."""

    option_spec: ClassVar[OptionSpec] = {
        "default": directives.unchanged,
    }

    def handle_signature(self, sig: str, signode: desc_signature) -> str:
        """Process the directive signature (the config name)."""
        signode += addnodes.desc_name(sig, sig)

        # Add default value if provided
        if "default" in self.options:
            signode += nodes.Text(" ")
            default_container = nodes.inline("", "")
            default_container += nodes.Text("(default: ")
            default_container += nodes.literal("", self.options["default"])
            default_container += nodes.Text(")")
            signode += default_container

        return sig

    def add_target_and_index(
        self, name: str, sig: str, signode: desc_signature
    ) -> None:
        """Add cross-reference target and index entry."""
        target = f"conf-{name}"
        if target not in self.state.document.ids:
            signode["ids"].append(target)
            self.state.document.note_explicit_target(signode)

            # A unique full name which includes the document name
            index_name = f"{self.env.docname.replace('/', '.')}:{name}"
            # Register with the conf domain
            domain = self.env.get_domain("conf")
            domain.data["objects"][index_name] = (self.env.docname, target)

            # Add to index
            self.indexnode["entries"].append(
                ("single", f"{name} (configuration value)", target, "", None)
            )


class ConfDomain(Domain):
    """Domain for simple configuration values."""

    name = "conf"
    label = "Simple Configuration"
    object_types = {"conf": ObjType("conf", "conf")}
    directives = {"conf": Conf}
    roles = {"conf": XRefRole()}
    initial_data: dict[str, Any] = {"objects": {}}

    def get_objects(self) -> Iterable[tuple[str, str, str, str, str, int]]:
        """Return an iterable of object tuples for the inventory."""
        for name, (docname, targetname) in self.data["objects"].items():
            # Remove the document name prefix for display
            display_name = name.split(":")[-1]
            yield (name, display_name, "conf", docname, targetname, 1)

    def resolve_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        typ: str,
        target: str,
        node: pending_xref,
        contnode: Element,
    ) -> Element | None:
        if entry := self.data["objects"].get(target):
            docname, targetid = entry
            return make_refnode(
                builder, fromdocname, docname, targetid, contnode
            )

        return None


# sphinx.util.typing.RoleFunction
def conf_role(
    name: str,
    rawtext: str,
    text: str,
    lineno: int,
    inliner: Inliner,
    /,
    options: dict[str, Any] | None = None,
    content: Sequence[str] = (),
) -> tuple[list[nodes.Node], list[nodes.system_message]]:
    """Role for referencing configuration values."""
    node = addnodes.pending_xref(
        "",
        refdomain="conf",
        reftype="conf",
        reftarget=text,
        refwarn=True,
        **(options or {}),
    )
    node += nodes.literal(text, text.split(":")[-1])
    return [node], []


def setup(app: Sphinx) -> ExtensionMetadata:
    app.add_domain(ConfDomain)

    # register a top-level directive so users can use ".. conf:: ..."
    app.add_directive("conf", Conf)

    # Register role with short name
    app.add_role("conf", conf_role)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
