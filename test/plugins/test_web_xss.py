"""Tests for XSS vulnerability in the web plugin templates.

This test verifies that the Underscore.js templates in index.html use
the escaping syntax (<%- %) instead of the non-escaping syntax (<%= %).

In Underscore.js 1.2.2 (used by beets):
- <%= variable %> does NOT escape HTML (vulnerable to XSS)
- <%- variable %> DOES escape HTML (safe)

The test checks the index.html template file served by Flask to ensure
all user data interpolations in the Underscore.js templates use the escaping
syntax.

Generated using mistral vibe, verified by Pieter Lenaerts <plenae@disroot.org>
"""

import re

from beets.test.helper import ItemInDBTestCase
from beetsplug import web


class WebXSSTest(ItemInDBTestCase):
    def setUp(self):
        super().setUp()
        web.app.config["TESTING"] = True
        web.app.config["lib"] = self.lib
        web.app.config["INCLUDE_PATHS"] = False
        web.app.config["READONLY"] = True
        self.client = web.app.test_client()

    def test_templates_use_escaping_syntax(self):
        """Verify that all Underscore.js templates use <%- %> for escaping.

        This test requests the index.html page and checks that all
        user data interpolations in the Underscore.js templates use
        the escaping syntax (<%- %) rather than the non-escaping syntax (<%= %).

        Before the fix (with <%= %>), this test will fail.
        After the fix (with <%- %>), this test will pass.
        """
        # Request the index.html page
        response = self.client.get("/")
        html = response.data.decode("utf-8")

        # Extract the template scripts from the HTML
        # The templates are in <script type="text/template"> blocks
        template_pattern = r'<script type="text/template"[^>]*>(.*?)</script>'
        templates = re.findall(template_pattern, html, re.DOTALL)

        # Combine all template content for checking
        all_template_content = "\n".join(templates)

        # Check that no <%= %> (non-escaping) tags exist for user data
        # We look for <%= followed by a variable name (word characters)
        non_escaping_pattern = r'<%=\s*(\w+)\s*%>'
        non_escaping_matches = re.findall(non_escaping_pattern, all_template_content)

        # List of fields that should be escaped (user-controlled data)
        user_data_fields = [
            'title', 'artist', 'album', 'year', 'track', 'tracktotal',
            'disc', 'disctotal', 'length', 'format', 'bitrate',
            'mb_trackid', 'id', 'lyrics', 'comments'
        ]

        # Check if any user data fields are using non-escaping <%= %>
        vulnerable_fields = [field for field in non_escaping_matches if field in user_data_fields]

        # If we found any user data fields using <%= %>, the templates are vulnerable
        assert len(vulnerable_fields) == 0, (
            f"Found non-escaping <%= %> tags for user data fields: {vulnerable_fields}. "
            f"These should use <%- %> for HTML escaping to prevent XSS."
        )

        # Also verify that escaping tags (<%- %>) are present for user data
        escaping_pattern = r'<%-\s*(\w+)\s*%>'
        escaping_matches = re.findall(escaping_pattern, all_template_content)

        # At least some user data fields should use escaping
        safe_fields = [field for field in escaping_matches if field in user_data_fields]
        assert len(safe_fields) > 0, (
            "No escaping <%- %> tags found for user data fields. "
            "Templates should use <%- %> for HTML escaping."
        )
