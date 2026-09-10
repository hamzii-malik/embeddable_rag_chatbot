import unittest
from unittest.mock import Mock, patch

import requests

from app.scanner import safe_get


class SafeGetSslTests(unittest.TestCase):
    @patch("app.scanner.requests.get")
    def test_safe_get_retries_without_verification_for_ssl_errors(self, mock_get):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b"<xml></xml>"
        mock_response.headers = {"content-type": "application/xml"}

        mock_get.side_effect = [
            requests.exceptions.SSLError("UNEXPECTED_EOF_WHILE_READING"),
            mock_response,
        ]

        response = safe_get("https://example.com/sitemap.xml", timeout=10)

        self.assertIs(response, mock_response)
        self.assertEqual(mock_get.call_count, 2)
        self.assertFalse(mock_get.call_args_list[1].kwargs["verify"])


if __name__ == "__main__":
    unittest.main()
