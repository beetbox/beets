import os
import yaml

from beets import ui
from beets import config

import _common
from _common import unittest


class ConfigCommandTest(_common.TestCase):

    def setUp(self):
        super(ConfigCommandTest, self).setUp()
        self.io.install()

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
        super(ConfigCommandTest, self).tearDown()
        self.execlp_restore()

    def test_show_user_config(self):
        ui._raw_main(['config'])
        output = yaml.load(self.io.getoutput())
        self.assertEqual(output['option'], 'value')

    def test_show_user_config_with_defaults(self):
        ui._raw_main(['config', '-d'])
        output = yaml.load(self.io.getoutput())
        self.assertEqual(output['option'], 'value')
        self.assertEqual(output['library'], 'lib')
        self.assertEqual(output['import']['timid'], False)

    def test_show_user_config_with_cli(self):
        ui._raw_main(['--config', self.cli_config_path, 'config'])
        output = yaml.load(self.io.getoutput())
        self.assertEqual(output['library'], 'lib')
        self.assertEqual(output['option'], 'cli overwrite')

    def test_config_paths(self):
        ui._raw_main(['config', '-p'])
        paths = self.io.getoutput().split('\n')
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0], self.config_path)

    def test_config_paths_with_cli(self):
        ui._raw_main(['--config', self.cli_config_path, 'config', '-p'])
        paths = self.io.getoutput().split('\n')
        self.assertEqual(len(paths), 3)
        self.assertEqual(paths[0], self.cli_config_path)

    def test_edit_config_with_editor_env(self):
        self.execlp_stub()
        os.environ['EDITOR'] = 'myeditor'

        ui._raw_main(['config', '-e'])
        self.assertEqual(self._execlp_call, ['myeditor', self.config_path])

    def test_edit_config_with_open(self):
        self.execlp_stub()

        with _common.system_mock('Darwin'):
            ui._raw_main(['config', '-e'])
        self.assertEqual(self._execlp_call, ['open', '-n', self.config_path])


    def test_edit_config_with_xdg_open(self):
        self.execlp_stub()

        with _common.system_mock('Linux'):
            ui._raw_main(['config', '-e'])
        self.assertEqual(self._execlp_call, ['xdg-open', self.config_path])

    def test_edit_config_with_windows_exec(self):
        self.execlp_stub()

        with _common.system_mock('Windows'):
            ui._raw_main(['config', '-e'])
        self.assertEqual(self._execlp_call, [self.config_path])

    def test_config_editor_not_found(self):
        def raise_os_error(*args):
            raise OSError
        os.execlp = raise_os_error
        with self.assertRaises(ui.UserError) as user_error:
            ui._raw_main(['config', '-e'])
        self.assertIn('Could not edit configuration',
                      str(user_error.exception.args[0]))


    def execlp_stub(self):
        self._execlp_call = None
        def _execlp_stub(file, *args):
            self._execlp_call = [file] + list(args[1:])

        self._orig_execlp = os.execlp
        os.execlp = _execlp_stub

    def execlp_restore(self):
        if hasattr(self, '_orig_execlp'):
            os.execlp = self._orig_execlp


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
