"""The favicon resolves for signed-out visitors and pages outside base.html."""

from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse


class FaviconTests(TestCase):
    def test_icon_files_exist(self):
        for name in ("img/favicon.svg", "img/favicon-32.png", "img/apple-touch-icon.png"):
            with self.subTest(name=name):
                self.assertIsNotNone(finders.find(name))

    def test_favicon_ico_redirects_without_login(self):
        response = self.client.get("/favicon.ico")
        self.assertRedirects(
            response, static("img/favicon-32.png"), status_code=301, fetch_redirect_response=False
        )

    def test_pages_link_the_icon(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, f'<link rel="icon" href="{static("img/favicon.svg")}"')
        self.assertContains(
            response, f'<link rel="apple-touch-icon" href="{static("img/apple-touch-icon.png")}"'
        )
