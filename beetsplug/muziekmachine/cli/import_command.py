from beets.ui import Subcommand
from ..pipeline.custom_pipeline import CustomImportSession

# Define the CLI subcommand
def custom_import_pipeline(lib, opts, args):
    # Parse the CLI options/flags
    sync_enabled = opts.sync
    parallel_download = opts.parallel_download
    parallel_analyze = opts.parallel_analyze

    # Create and run the custom import session
    session = CustomImportSession(lib, sync_enabled, parallel_download, parallel_analyze)
    session.run()

# Register the subcommand with beets
custom_import_cmd = Subcommand('customimport', help='Run custom import pipeline')
custom_import_cmd.func = custom_import_pipeline
custom_import_cmd.parser.add_option('--sync', action='store_true', help='Enable platform synchronization')
custom_import_cmd.parser.add_option('--parallel-download', action='store_true', help='Enable parallel downloading')
custom_import_cmd.parser.add_option('--parallel-analyze', action='store_true', help='Enable parallel audio analysis')
