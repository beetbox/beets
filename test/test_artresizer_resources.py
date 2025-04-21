#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Resource leak tests for artresizer backends."""

import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

# Adjust Python path to find beets modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from beets.test.helper import TestHelper
from beets.util import syspath
from beets.util.artresizer import IMBackend, PILBackend

class ResourceLeakTestBase(TestHelper):
    """Base class for resource leak tests."""
    
    def setup_method(self, method):
        self.setup_beets()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="beets_test_"))
        
        # Create test image file (minimal JPEG)
        self.test_image = self.temp_dir / 'test.jpg'
        with open(self.test_image, 'wb') as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01' +
                    b'\x00\x01\x00\x00' + b'A' * 1000)

    def teardown_method(self, method):
        self._force_clean_temp_files()  # Cleanup before teardown
        self.teardown_beets()

    def _force_clean_temp_files(self):
        """Remove all temporary files from the artresizer directory."""
        temp_dir = Path(tempfile.gettempdir()) / 'beets' / 'util_artresizer'
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                try:
                    file.unlink()
                except (PermissionError, OSError):
                    pass  # Skip locked files (e.g., on Windows)

    def _get_resource_counts(self):
        """Get current resource counts with retries for filesystem delays."""
        temp_dir = Path(tempfile.gettempdir()) / 'beets' / 'util_artresizer'
        if not temp_dir.exists():
            return {'temp_files': 0}
        
        # Retry to account for filesystem latency
        for _ in range(3):
            count = len(list(temp_dir.iterdir()))
            if count == 0:
                break
            time.sleep(0.1)
        return {'temp_files': count}

    def assert_no_leaks(self, initial_counts):
        """Assert no leaks with tolerance for delayed cleanup."""
        current = self._get_resource_counts()
        assert current['temp_files'] <= initial_counts['temp_files'], (
            f"Temporary file leak detected: {current['temp_files']} files remain"
        )

@pytest.mark.skipif(not PILBackend.available(), reason="Pillow not installed")
class TestPILResourceLeak(ResourceLeakTestBase):
    def setup_method(self, method):
        super().setup_method(method)
        self.backend = PILBackend()
        self._force_clean_temp_files()  # Start with a clean slate
        self.initial_counts = self._get_resource_counts()

    def test_resize_handle_leak(self):
        try:
            out_path = self.backend.resize(100, syspath(self.test_image))
            assert os.path.exists(out_path)
        finally:
            self.assert_no_leaks(self.initial_counts)

@pytest.mark.skipif(not IMBackend.available(), reason="ImageMagick not installed")
class TestIMResourceLeak(ResourceLeakTestBase):
    def setup_method(self, method):
        super().setup_method(method)
        self.backend = IMBackend()
        self._force_clean_temp_files()  # Start with a clean slate
        self.initial_counts = self._get_resource_counts()

    def test_resize_subprocess_cleanup(self):
        try:
            out_path = self.backend.resize(100, syspath(self.test_image))
            assert os.path.exists(out_path)
        finally:
            self.assert_no_leaks(self.initial_counts)
