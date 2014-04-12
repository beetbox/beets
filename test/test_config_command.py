import os
import yaml
from mock import patch
from tempfile import mkdtemp
from shutil import rmtree

from beets import ui
from beets import config

import _common
from _common import unittest
from helper import TestHelper, capture_stdout


class ConfigCommandTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.temp_dir = mkdtemp()
        if 'EDITOR' in os.environ:
            del os.environ['EDITOR']

        os.environ['BEETSDIR'] = self.temp_dir
        self.config_path = os.path.join(self.temp_dir, 'config.yaml')
        with open(self.config_path, 'w') as file:
            file.write('library: lib\n')
            file.write('option: value')

        self.cli_config_path = os.path.join(self.temp_dir, 'cli_config.yaml')
        with open(self.cli_config_path, 'w') as file:
            file.write('option: cli overwrite')

        config.clear()
        config._materialized = False

    def tearDown(self):
        rmtree(self.temp_dir)

    def test_show_user_config(self):
        with capture_stdout() as output:
            self.run_command('config')
        output = yaml.load(output.getvalue())
        self.assertEqual(output['option'], 'value')

    def test_show_user_config_with_defaults(self):
        with capture_stdout() as output:
            self.run_command('config', '-d')
        output = yaml.load(output.getvalue())
        self.assertEqual(output['option'], 'value')
        self.assertEqual(output['library'], 'lib')
        self.assertEqual(output['import']['timid'], False)

    def test_show_user_config_with_cli(self):
        with capture_stdout() as output:
            self.run_command('--config', self.cli_config_path, 'config')
        output = yaml.load(output.getvalue())
        self.assertEqual(output['library'], 'lib')
        self.assertEqual(output['option'], 'cli overwrite')

    def test_config_paths(self):
        with capture_stdout() as output:
            self.run_command('config', '-p')
        paths = output.getvalue().split('\n')
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0], self.config_path)

    def test_config_paths_with_cli(self):
        with capture_stdout() as output:
            self.run_command('--config', self.cli_config_path, 'config', '-p')
        paths = output.getvalue().split('\n')
        self.assertEqual(len(paths), 3)
        self.assertEqual(paths[0], self.cli_config_path)

    def test_edit_config_with_editor_env(self):
        os.environ['EDITOR'] = 'myeditor'
        with patch('os.execlp') as execlp:
            self.run_command('config', '-e')
        execlp.assert_called_once_with(
            'myeditor', 'myeditor', self.config_path)

    def test_edit_config_with_open(self):
        with _common.system_mock('Darwin'):
            with patch('os.execlp') as execlp:
                self.run_command('config', '-e')
        execlp.assert_called_once_with(
            'open', 'open', '-n', self.config_path)

    def test_edit_config_with_xdg_open(self):
        with _common.system_mock('Linux'):
            with patch('os.execlp') as execlp:
                self.run_command('config', '-e')
        execlp.assert_called_once_with(
            'xdg-open', 'xdg-open', self.config_path)

    def test_edit_config_with_windows_exec(self):
        with _common.system_mock('Windows'):
            with patch('os.execlp') as execlp:
                self.run_command('config', '-e')
        execlp.assert_called_once_with(self.config_path, self.config_path)

    def test_config_editor_not_found(self):
        with self.assertRaises(ui.UserError) as user_error:
            with patch('os.execlp') as execlp:
                execlp.side_effect = OSError()
                self.run_command('config', '-e')
        self.assertIn('Could not edit configuration',
                      str(user_error.exception.args[0]))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
