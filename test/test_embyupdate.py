# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

from test._common import unittest
from test.helper import TestHelper
from beetsplug import embyupdate
import responses


class EmbyUpdateTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('embyupdate')

        self.config['emby'] = {
            u'host': u'localhost',
            u'port': 8096,
            u'username': u'username',
            u'password': u'password'
        }

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_api_url(self):
        self.assertEqual(
            embyupdate.api_url(self.config['emby']['host'].get(),
                               self.config['emby']['port'].get(),
                               '/Library/Refresh'),
            'http://localhost:8096/Library/Refresh?format=json'
        )

    def test_password_data(self):
        self.assertEqual(
            embyupdate.password_data(self.config['emby']['username'].get(),
                                     self.config['emby']['password'].get()),
            {
                'username': 'username',
                'password': '5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8',
                'passwordMd5': '5f4dcc3b5aa765d61d8327deb882cf99'
            }
        )

    def test_create_header_no_token(self):
        self.assertEqual(
            embyupdate.create_headers('e8837bc1-ad67-520e-8cd2-f629e3155721'),
            {
                'Authorization': 'MediaBrowser',
                'UserId': 'e8837bc1-ad67-520e-8cd2-f629e3155721',
                'Client': 'other',
                'Device': 'empy',
                'DeviceId': 'beets',
                'Version': '0.0.0'
            }
        )

    def test_create_header_with_token(self):
        self.assertEqual(
            embyupdate.create_headers('e8837bc1-ad67-520e-8cd2-f629e3155721',
                                      token='abc123'),
            {
                'Authorization': 'MediaBrowser',
                'UserId': 'e8837bc1-ad67-520e-8cd2-f629e3155721',
                'Client': 'other',
                'Device': 'empy',
                'DeviceId': 'beets',
                'Version': '0.0.0',
                'X-MediaBrowser-Token': 'abc123'
            }
        )

    @responses.activate
    def test_get_token(self):
        body = ('{"User":{"Name":"username", '
                '"ServerId":"1efa5077976bfa92bc71652404f646ec",'
                '"Id":"2ec276a2642e54a19b612b9418a8bd3b","HasPassword":true,'
                '"HasConfiguredPassword":true,'
                '"HasConfiguredEasyPassword":false,'
                '"LastLoginDate":"2015-11-09T08:35:03.6357440Z",'
                '"LastActivityDate":"2015-11-09T08:35:03.6665060Z",'
                '"Configuration":{"AudioLanguagePreference":"",'
                '"PlayDefaultAudioTrack":true,"SubtitleLanguagePreference":"",'
                '"DisplayMissingEpisodes":false,'
                '"DisplayUnairedEpisodes":false,'
                '"GroupMoviesIntoBoxSets":false,'
                '"DisplayChannelsWithinViews":[],'
                '"ExcludeFoldersFromGrouping":[],"GroupedFolders":[],'
                '"SubtitleMode":"Default","DisplayCollectionsView":true,'
                '"DisplayFoldersView":false,"EnableLocalPassword":false,'
                '"OrderedViews":[],"IncludeTrailersInSuggestions":true,'
                '"EnableCinemaMode":true,"LatestItemsExcludes":[],'
                '"PlainFolderViews":[],"HidePlayedInLatest":true,'
                '"DisplayChannelsInline":false},'
                '"Policy":{"IsAdministrator":true,"IsHidden":false,'
                '"IsDisabled":false,"BlockedTags":[],'
                '"EnableUserPreferenceAccess":true,"AccessSchedules":[],'
                '"BlockUnratedItems":[],'
                '"EnableRemoteControlOfOtherUsers":false,'
                '"EnableSharedDeviceControl":true,'
                '"EnableLiveTvManagement":true,"EnableLiveTvAccess":true,'
                '"EnableMediaPlayback":true,'
                '"EnableAudioPlaybackTranscoding":true,'
                '"EnableVideoPlaybackTranscoding":true,'
                '"EnableContentDeletion":false,'
                '"EnableContentDownloading":true,"EnableSync":true,'
                '"EnableSyncTranscoding":true,"EnabledDevices":[],'
                '"EnableAllDevices":true,"EnabledChannels":[],'
                '"EnableAllChannels":true,"EnabledFolders":[],'
                '"EnableAllFolders":true,"InvalidLoginAttemptCount":0,'
                '"EnablePublicSharing":true}},'
                '"SessionInfo":{"SupportedCommands":[],'
                '"QueueableMediaTypes":[],"PlayableMediaTypes":[],'
                '"Id":"89f3b33f8b3a56af22088733ad1d76b3",'
                '"UserId":"2ec276a2642e54a19b612b9418a8bd3b",'
                '"UserName":"username","AdditionalUsers":[],'
                '"ApplicationVersion":"Unknown version",'
                '"Client":"Unknown app",'
                '"LastActivityDate":"2015-11-09T08:35:03.6665060Z",'
                '"DeviceName":"Unknown device","DeviceId":"Unknown device id",'
                '"SupportsRemoteControl":false,"PlayState":{"CanSeek":false,'
                '"IsPaused":false,"IsMuted":false,"RepeatMode":"RepeatNone"}},'
                '"AccessToken":"4b19180cf02748f7b95c7e8e76562fc8",'
                '"ServerId":"1efa5077976bfa92bc71652404f646ec"}')

        responses.add(responses.POST,
                      ('http://localhost:8096'
                       '/Users/AuthenticateByName'),
                      body=body,
                      status=200,
                      content_type='application/json')

        headers = {
            'Authorization': 'MediaBrowser',
            'UserId': 'e8837bc1-ad67-520e-8cd2-f629e3155721',
            'Client': 'other',
            'Device': 'empy',
            'DeviceId': 'beets',
            'Version': '0.0.0'
        }

        auth_data = {
            'username': 'username',
            'password': '5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8',
            'passwordMd5': '5f4dcc3b5aa765d61d8327deb882cf99'
        }

        self.assertEqual(
            embyupdate.get_token('localhost', 8096, headers, auth_data),
            '4b19180cf02748f7b95c7e8e76562fc8')

    @responses.activate
    def test_get_user(self):
        body = ('[{"Name":"username",'
                '"ServerId":"1efa5077976bfa92bc71652404f646ec",'
                '"Id":"2ec276a2642e54a19b612b9418a8bd3b","HasPassword":true,'
                '"HasConfiguredPassword":true,'
                '"HasConfiguredEasyPassword":false,'
                '"LastLoginDate":"2015-11-09T08:35:03.6357440Z",'
                '"LastActivityDate":"2015-11-09T08:42:39.3693220Z",'
                '"Configuration":{"AudioLanguagePreference":"",'
                '"PlayDefaultAudioTrack":true,"SubtitleLanguagePreference":"",'
                '"DisplayMissingEpisodes":false,'
                '"DisplayUnairedEpisodes":false,'
                '"GroupMoviesIntoBoxSets":false,'
                '"DisplayChannelsWithinViews":[],'
                '"ExcludeFoldersFromGrouping":[],"GroupedFolders":[],'
                '"SubtitleMode":"Default","DisplayCollectionsView":true,'
                '"DisplayFoldersView":false,"EnableLocalPassword":false,'
                '"OrderedViews":[],"IncludeTrailersInSuggestions":true,'
                '"EnableCinemaMode":true,"LatestItemsExcludes":[],'
                '"PlainFolderViews":[],"HidePlayedInLatest":true,'
                '"DisplayChannelsInline":false},'
                '"Policy":{"IsAdministrator":true,"IsHidden":false,'
                '"IsDisabled":false,"BlockedTags":[],'
                '"EnableUserPreferenceAccess":true,"AccessSchedules":[],'
                '"BlockUnratedItems":[],'
                '"EnableRemoteControlOfOtherUsers":false,'
                '"EnableSharedDeviceControl":true,'
                '"EnableLiveTvManagement":true,"EnableLiveTvAccess":true,'
                '"EnableMediaPlayback":true,'
                '"EnableAudioPlaybackTranscoding":true,'
                '"EnableVideoPlaybackTranscoding":true,'
                '"EnableContentDeletion":false,'
                '"EnableContentDownloading":true,'
                '"EnableSync":true,"EnableSyncTranscoding":true,'
                '"EnabledDevices":[],"EnableAllDevices":true,'
                '"EnabledChannels":[],"EnableAllChannels":true,'
                '"EnabledFolders":[],"EnableAllFolders":true,'
                '"InvalidLoginAttemptCount":0,"EnablePublicSharing":true}}]')

        responses.add(responses.GET,
                      'http://localhost:8096/Users/Public',
                      body=body,
                      status=200,
                      content_type='application/json')

        response = embyupdate.get_user('localhost', 8096, 'username')

        self.assertEqual(response[0]['Id'],
                         '2ec276a2642e54a19b612b9418a8bd3b')

        self.assertEqual(response[0]['Name'],
                         'username')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
