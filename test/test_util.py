from test._common import unittest
from test import _common

from beets import util


class UtilTest(unittest.TestCase):
    def test_open_anything(self):
        with _common.system_mock('Windows'):
            self.assertEqual(util.open_anything(), 'start')

        with _common.system_mock('Darwin'):
            self.assertEqual(util.open_anything(), 'open')

        with _common.system_mock('Tagada'):
            self.assertEqual(util.open_anything(), 'xdg-open')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
