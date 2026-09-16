"""Calculate acoustic information and submit to AcousticBrainz."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING, Protocol

import requests

from beets import plugins, ui, util
from beets.exceptions import UserError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.library import Item, Library

    from ._typing import JSONDict


class ABSubmitCLIOpts(Protocol):
    force_refetch: bool
    pretend_fetch: bool


# We use this field to check whether AcousticBrainz info is present.
PROBE_FIELD = "mood_acoustic"


class ABSubmitError(Exception):
    """Raised when failing to analyse file with extractor."""


def call(args: Sequence[str]) -> bytes:
    """Execute the command and return its output.

    Raise a AnalysisABSubmitError on failure.
    """
    try:
        return util.command_output(args).stdout
    except subprocess.CalledProcessError as e:
        raise ABSubmitError(f"{args[0]} exited with status {e.returncode}")


class AcousticBrainzSubmitPlugin(plugins.BeetsPlugin):
    extractor: str

    def __init__(self) -> None:
        super().__init__()

        self._log.warning("This plugin is deprecated.")

        self.config.add(
            {"extractor": "", "force": False, "pretend": False, "base_url": ""}
        )

        if extractor := self.config["extractor"].as_str():
            extractor = os.fsdecode(util.normpath(extractor))
            # Explicit path to extractor
            if not os.path.isfile(extractor):
                raise UserError(
                    f"Extractor command does not exist: {extractor}."
                )
        else:
            # Implicit path to extractor, search for it in path
            extractor = "streaming_extractor_music"
            try:
                call([extractor])
            except OSError:
                raise UserError(
                    "No extractor command found: please install the extractor"
                    " binary from https://essentia.upf.edu/"
                )
            except ABSubmitError:
                # Extractor found, will exit with an error if not called with
                # the correct amount of arguments.
                pass

            # Get the executable location on the system, which we need
            # to calculate the SHA-1 hash.
            if extractor_cmd_path := shutil.which(extractor):
                extractor = extractor_cmd_path
            else:
                raise UserError(
                    f"Path to extractor command {extractor} not found"
                )

        self.extractor = extractor

        # Calculate extractor hash.
        extractor_sha = hashlib.sha1()
        if extractor:
            with open(extractor, "rb") as f:
                extractor_sha.update(f.read())
        self.extractor_sha = extractor_sha.hexdigest()

        self.url = ""
        base_url = self.config["base_url"].as_str()
        if base_url:
            if not base_url.startswith("http"):
                raise UserError(
                    "AcousticBrainz server base URL must start "
                    "with an HTTP scheme"
                )
            if base_url[-1] != "/":
                base_url = f"{base_url}/"
            self.url = f"{base_url}{{mbid}}/low-level"

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand(
            "absubmit", help="calculate and submit AcousticBrainz analysis"
        )
        cmd.parser.add_option(
            "-f",
            "--force",
            dest="force_refetch",
            action="store_true",
            default=False,
            help="re-download data when already present",
        )
        cmd.parser.add_option(
            "-p",
            "--pretend",
            dest="pretend_fetch",
            action="store_true",
            default=False,
            help=(
                "pretend to perform action, but show only files which would be"
                " processed"
            ),
        )
        cmd.func = self.command
        return [cmd]

    def command(
        self, lib: Library, opts: ABSubmitCLIOpts, args: list[str]
    ) -> None:
        if not self.url:
            raise UserError(
                "This plugin is deprecated since AcousticBrainz no longer "
                "accepts new submissions. See the base_url configuration "
                "option."
            )
        # Get items from arguments
        items = lib.items(args)
        self.opts = opts
        util.par_map(self.analyze_submit, items)

    def analyze_submit(self, item: Item) -> None:
        analysis = self._get_analysis(item)
        if analysis:
            self._submit_data(item, analysis)

    def _get_analysis(self, item: Item) -> JSONDict | None:
        mbid = item["mb_trackid"]

        # Avoid re-analyzing files that already have AB data.
        if not self.opts.force_refetch and not self.config["force"]:
            if item.get(PROBE_FIELD):
                return None

        # If file has no MBID, skip it.
        if not mbid:
            self._log.info(
                "Not analysing {}, missing musicbrainz track id.", item
            )
            return None

        if self.opts.pretend_fetch or self.config["pretend"]:
            self._log.info("pretend action - extract item: {}", item)
            return None

        # Temporary file to save extractor output to, extractor only works
        # if an output file is given. Here we use a temporary file to copy
        # the data into a python object and then remove the file from the
        # system.
        tmp_file, filename = tempfile.mkstemp(suffix=".json")
        try:
            # Close the file, so the extractor can overwrite it.
            os.close(tmp_file)
            try:
                call([self.extractor, util.syspath(item.path), filename])
            except ABSubmitError as e:
                self._log.warning(
                    "Failed to analyse {} for AcousticBrainz: {}", item, e
                )
                return None
            with open(filename) as f:
                analysis = json.load(f)
            # Add the hash to the output.
            analysis["metadata"]["version"]["essentia_build_sha"] = (
                self.extractor_sha
            )
            return analysis
        finally:
            try:
                os.remove(filename)
            except OSError as e:
                # ENOENT means file does not exist, just ignore this error.
                if e.errno != errno.ENOENT:
                    raise

    def _submit_data(self, item: Item, data: JSONDict) -> None:
        mbid = item["mb_trackid"]
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            self.url.format(mbid=mbid), json=data, headers=headers, timeout=10
        )
        # Test that request was successful and raise an error on failure.
        if response.status_code != 200:
            try:
                message = response.json()["message"]
            except (ValueError, KeyError) as e:
                message = f"unable to get error message: {e}"
            self._log.error(
                "Failed to submit AcousticBrainz analysis for {}: {}.",
                item,
                message,
            )
        else:
            self._log.debug(
                "Successfully submitted AcousticBrainz analysis for {}.", item
            )
