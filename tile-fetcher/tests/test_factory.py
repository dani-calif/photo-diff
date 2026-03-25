from __future__ import annotations

import unittest

from tile_fetcher.services.service import TileFetchService
from tile_fetcher.services.factory import build_tile_fetch_service
from tile_fetcher.settings import TileFetcherSettings


class TileFetcherFactoryTests(unittest.TestCase):
    def test_build_tile_fetch_service_uses_internal_adapters(self) -> None:
        service = build_tile_fetch_service(TileFetcherSettings())
        self.assertIsInstance(service, TileFetchService)
