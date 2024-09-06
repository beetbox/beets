from ..stages.fetch_data_stage import FetchPlatformData
# from ..stages.generate_items_stage import GenerateBeetsItemsStage
# from ..stages.sync_platforms_stage import SyncPlatformsStage
# from ..stages.download_audiofile_stage import DownloadAudioStage
# from ..stages.analyze_audiofile_stage import AnalyzeAudioStage


class CustomImportSession:
    def __init__(self, lib, sync_enabled=False, parallel_download=False, parallel_analyze=False):
        self.lib = lib
        self.sync_enabled = sync_enabled
        self.parallel_download = parallel_download
        self.parallel_analyze = parallel_analyze

    def run(self):
        # Stage 1: Fetch data from platforms
        fetch_stage = FetchPlatformData()
        platform_data = fetch_stage(self.lib)

        # # Stage 2: Generate list of Beets items
        # generate_items_stage = GenerateBeetsItemsStage(self.lib)
        # items = generate_items_stage(platform_data)

        # # Stage 3: Sync platforms (optional)
        # sync_stage = SyncPlatformsStage(enabled=self.sync_enabled)
        # sync_stage(platform_data)

        # # Stage 4: Download audio (parallel if needed)
        # download_stage = DownloadAudioStage(self.lib, parallel=self.parallel_download)
        # download_stage(items)

        # # Stage 5: Analyze audio (parallel if needed)
        # analyze_stage = AnalyzeAudioStage(self.lib, parallel=self.parallel_analyze)
        # analyze_stage(items)
