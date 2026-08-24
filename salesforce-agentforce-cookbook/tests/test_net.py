"""Behavior specs for cross-host redirect credential stripping."""

from __future__ import annotations

import unittest
import urllib.request

from net import StripAuthOnHostChangeRedirect


class StripAuthOnHostChangeRedirectTest(unittest.TestCase):
    def test_same_host_keeps_authorization(self) -> None:
        handler = StripAuthOnHostChangeRedirect()
        req = urllib.request.Request(
            "https://api.example.com/v1/traces",
            headers={"Authorization": "Bearer secret"},
            method="POST",
        )
        redirected = handler.redirect_request(
            req,
            None,
            302,
            "Found",
            {},
            "https://api.example.com/v2/traces",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        self.assertEqual(redirected.get_header("Authorization"), "Bearer secret")

    def test_host_change_drops_authorization(self) -> None:
        handler = StripAuthOnHostChangeRedirect()
        req = urllib.request.Request(
            "https://api.example.com/v1/traces",
            headers={"Authorization": "Bearer secret"},
            method="POST",
        )
        redirected = handler.redirect_request(
            req,
            None,
            302,
            "Found",
            {},
            "https://evil.example.net/v1/traces",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        self.assertIsNone(redirected.get_header("Authorization"))
