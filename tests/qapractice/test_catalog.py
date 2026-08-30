from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from tests.qapractice.support import QAStoreApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
@pytest.mark.smoke
def test_catalog_loads_with_expected_controls(store: QAStoreApp) -> None:
    store.open_catalog()
    store.reveal_search()

    expect(store.page).to_have_title(re.compile(r"Dummy E-commerce"))
    expect(store.by_test_id("ecom-result-count")).to_have_text("20 products")
    expect(store.by_test_id("ecom-search")).to_be_visible()
    expect(store.by_test_id("ecom-cart-button")).to_be_visible()
    expect(store.page.locator('[data-testid^="product-card-"]')).to_have_count(8)


@pytest.mark.full
def test_search_filters_products(store: QAStoreApp) -> None:
    store.open_catalog()

    store.by_test_id("ecom-search").fill("mouse")

    expect(store.by_test_id("ecom-result-count")).to_have_text("1 product")
    expect(store.by_test_id("product-card-2")).to_contain_text("Wireless Mouse")
    expect(store.page.locator('[data-testid^="product-card-"]')).to_have_count(1)


@pytest.mark.full
def test_sort_and_product_detail(store: QAStoreApp) -> None:
    store.open_catalog()

    store.by_test_id("ecom-sort").select_option("price-asc")
    visible_cards = store.page.locator('[data-testid^="product-card-"]')
    expect(visible_cards.first).to_contain_text("Coca Cola 250ml")

    store.by_test_id("view-product-2").click()
    expect(store.by_test_id("ecom-product-detail")).to_be_visible()
    expect(store.by_test_id("ecom-product-detail")).to_contain_text("Wireless Mouse")
    expect(store.by_test_id("ecom-back-to-products")).to_be_visible()


@pytest.mark.full
def test_pagination_moves_to_next_product_set(store: QAStoreApp) -> None:
    store.open_catalog()

    store.by_test_id("ecom-page-2").click()

    expect(store.by_test_id("ecom-page-prev")).to_be_enabled()
    expect(store.by_test_id("product-card-9")).to_be_visible()
    expect(store.by_test_id("product-card-1")).to_have_count(0)
