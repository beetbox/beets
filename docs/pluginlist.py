import os
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive, directives


class PluginListDirective(Directive):
    """Directive to list all .rst files in a given folder.

    Along with their top-level header, with optional extra user-defined entries.

    Usage:
        .. filelist::
           :path: path/to/folder
           :exclude: file1.rst, file2.rst
           :extra:
                overview.rst  # file link with implicit title from filename
                Overview: overview.rst  # file link with custom title
                :ref:`user-guide`  # arbitrary reST reference
    """

    has_content = False
    required_arguments = 0
    optional_arguments = 0

    option_spec = {
        "path": directives.unchanged_required,
        "exclude": directives.unchanged,
        "extra": directives.unchanged,
    }

    def _extract_title(self, path: Path):
        """Extract the first section title from an rst file."""
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f]
        for idx, line in enumerate(lines):
            if not line:
                continue
            # Check for underline-style title
            if idx + 1 < len(lines) and set(lines[idx + 1]) <= set(
                "= - `:'~^_*+#<>"
            ):
                underline = lines[idx + 1]
                if len(underline) >= len(line):
                    return line
            # Or overline/underline style
            if idx >= 1 and set(lines[idx - 1]) <= set("= - `:'~^_*+#<>"):
                overline = lines[idx - 1]
                if len(overline) >= len(line):
                    return line
        # Fallback: filename without extension
        return os.path.splitext(os.path.basename(path))[0]

    def _get_current_src(self) -> Path:
        """Get the current source file path."""
        current_doc = self.state.document.current_source
        if not current_doc:
            raise ValueError("Current document source could not be determined.")
        return Path(current_doc).resolve()

    def run(self):
        folder_option = self.options.get("path")
        if not folder_option:
            error = self.state_machine.reporter.error(
                'The "path" option is required for the pluginlist directive.',
                nodes.literal_block(self.block_text, self.block_text),
                line=self.lineno,
            )
            return [error]

        # Resolve folder path relative to current doc file
        cur_path = self._get_current_src()
        target_folder = cur_path.joinpath(folder_option).resolve().parent

        if not os.path.isdir(target_folder):
            error = self.state_machine.reporter.error(
                f'Path "{folder_option}" resolved to "{target_folder}". '
                "Could not found or is not a directory.",
                nodes.literal_block(self.block_text, self.block_text),
                line=self.lineno,
            )
            return [error]

        excludes_raw = self.options.get("exclude", "")
        excludes = [x.strip() for x in excludes_raw.split(",") if x.strip()]

        # Find .rst files, excluding specified
        files = [
            f
            for f in os.listdir(target_folder)
            if f.endswith(".rst") and f not in excludes
        ]

        refs = []
        for filename in files:
            # Reference to the rst file
            refuri = (
                os.path.splitext(os.path.join(folder_option, filename))[
                    0
                ].replace(os.sep, "/")
                + ".html"
            )
            # Title for the link
            title = self._extract_title(target_folder.joinpath(filename))

            ref = nodes.reference("", title, internal=True, refuri=refuri)
            refs.append(ref)

        # Extra entries into refs
        extra_option = self.options.get("extra", "")
        if extra_option:
            from docutils.statemachine import ViewList

            for line in extra_option.splitlines():
                entry = line.strip()
                if not entry:
                    continue

                para = nodes.paragraph()

                # If entry is pure reST (contains role/backticks and no file .rst)
                if (
                    "`" in entry or entry.strip().startswith(":ref")
                ) and ".rst" not in entry:
                    vl = ViewList()
                    vl.append(entry, self.block_text)
                    self.state.nested_parse(vl, self.content_offset, para)
                else:
                    # file link: either 'file.rst' or 'Title: file.rst'
                    if ":" in entry:
                        title, target = [p.strip() for p in entry.split(":", 1)]
                    else:
                        target = entry
                        title = Path(entry).stem
                    if target.endswith(".rst"):
                        title = self._extract_title(
                            target_folder.joinpath(target)
                        )
                        rel = Path(self.options["path"]) / target
                        refuri = str(rel.with_suffix(".html")).replace(
                            os.sep, "/"
                        )
                        ref = nodes.reference(
                            "", title, internal=True, refuri=refuri
                        )
                        para += ref
                    else:
                        # fallback parse
                        vl = ViewList()
                        vl.append(entry, self.block_text)
                        self.state.nested_parse(vl, self.content_offset, para)

                refs.append(para)

        # Sort refs
        refs.sort(key=lambda x: x.astext().lower())

        # Build bullet list of links
        bullet_list = nodes.bullet_list()
        for ref in refs:
            item = nodes.list_item()
            para = nodes.paragraph()
            para += ref
            item += para
            bullet_list += item

        return [bullet_list]
