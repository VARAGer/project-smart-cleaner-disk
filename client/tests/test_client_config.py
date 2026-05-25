import os
import tempfile
import unittest
from unittest.mock import patch

from client.config import (
    DEFAULT_BACKEND_URL,
    get_data_dir,
    resolve_backend_url,
    resolve_backend_urls,
)


class ClientConfigTestCase(unittest.TestCase):
    def test_backend_url_defaults_to_localhost(self):
        with patch.dict(os.environ, {"SMARTCLEANER_BACKEND": ""}, clear=False):
            self.assertEqual(resolve_backend_url(data_dir="Z:/missing"), DEFAULT_BACKEND_URL)

    def test_backend_url_reads_user_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backend_url.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("https://demo.trycloudflare.com/\n")

            with patch.dict(os.environ, {"SMARTCLEANER_BACKEND": ""}, clear=False):
                self.assertEqual(
                    resolve_backend_url(data_dir=tmp),
                    "https://demo.trycloudflare.com",
                )

    def test_backend_url_ignores_utf8_bom_from_installer_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backend_url.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\ufeffhttps://demo.trycloudflare.com\n")

            with patch.dict(os.environ, {"SMARTCLEANER_BACKEND": ""}, clear=False):
                self.assertEqual(
                    resolve_backend_url(data_dir=tmp),
                    "https://demo.trycloudflare.com",
                )

    def test_backend_urls_support_multiple_file_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backend_url.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "https://public.trycloudflare.com/\n"
                    "http://localhost:8000; https://backup.example"
                )

            with patch.dict(os.environ, {"SMARTCLEANER_BACKEND": ""}, clear=False):
                self.assertEqual(
                    resolve_backend_urls(data_dir=tmp),
                    [
                        "https://public.trycloudflare.com",
                        "http://localhost:8000",
                        "https://backup.example",
                    ],
                )

    def test_backend_url_env_overrides_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backend_url.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("https://file.example")

            with patch.dict(
                os.environ,
                {"SMARTCLEANER_BACKEND": "https://env.example/"},
                clear=False,
            ):
                self.assertEqual(
                    resolve_backend_url(data_dir=tmp),
                    "https://env.example",
                )

    def test_backend_urls_env_supports_multiple_entries(self):
        with patch.dict(
            os.environ,
            {"SMARTCLEANER_BACKEND": "https://one.example, http://localhost:8000/"},
            clear=False,
        ):
            self.assertEqual(
                resolve_backend_urls(data_dir="Z:/missing"),
                ["https://one.example", "http://localhost:8000"],
            )

    def test_windows_data_dir_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("client.config.os.name", "nt"):
                with patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=False):
                    self.assertEqual(get_data_dir(), os.path.join(tmp, "SmartCleaner"))


if __name__ == "__main__":
    unittest.main()
