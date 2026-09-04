from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from pydantic import BaseModel, ConfigDict

from ai_qa_engineering.api_testing import APIClient
from ai_qa_engineering.navigation import navigate_or_incomplete


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Product(ContractModel):
    id: str
    name: str
    available: bool


class CatalogResponse(ContractModel):
    products: list[Product]


class OrderResponse(ContractModel):
    id: str
    product_id: str
    quantity: int
    status: str


class ErrorDetail(ContractModel):
    code: str
    message: str


class ErrorResponse(ContractModel):
    error: ErrorDetail


@pytest.mark.full
def test_api_contracts_status_latency_and_negative_cases(api_client: APIClient) -> None:
    catalog = api_client.check(
        "Catalog contract",
        "GET",
        "/api/catalog",
        expected_status=200,
        response_model=CatalogResponse,
        latency_budget_ms=500,
    )
    assert catalog.json_body["products"][0]["available"] is True

    api_client.check(
        "Missing authentication is rejected",
        "GET",
        "/api/catalog",
        expected_status=401,
        response_model=ErrorResponse,
        include_auth=False,
    )
    api_client.check(
        "Invalid authentication is rejected",
        "GET",
        "/api/catalog",
        expected_status=401,
        response_model=ErrorResponse,
        include_auth=False,
        headers={"Authorization": "Bearer invalid-synthetic-token"},
    )
    api_client.check(
        "Invalid order input is rejected",
        "POST",
        "/api/orders",
        expected_status=422,
        response_model=ErrorResponse,
        json_body={"product_id": "UNKNOWN", "quantity": 0, "password": "must-not-persist"},
    )
    api_client.check(
        "Unknown order is not found",
        "GET",
        "/api/orders/ORDER-999",
        expected_status=404,
        response_model=ErrorResponse,
    )


@pytest.mark.full
@pytest.mark.smoke
def test_order_lifecycle_crosses_api_and_browser(api_client: APIClient, qa_page: Page) -> None:
    created = api_client.check(
        "Create order through API",
        "POST",
        "/api/orders",
        expected_status=201,
        response_model=OrderResponse,
        json_body={"product_id": "SKU-001", "quantity": 2},
    )
    order_id = created.json_body["id"]

    navigate_or_incomplete(qa_page, f"http://127.0.0.1:8771/orders/{order_id}")
    expect(qa_page.get_by_role("heading", name=f"Order {order_id}")).to_be_visible()
    expect(qa_page.locator("#order-status")).to_have_text("pending")

    qa_page.get_by_role("button", name="Approve order").click()
    expect(qa_page.locator("#order-status")).to_have_text("approved")
    api_client.check(
        "Browser approval is visible through API",
        "GET",
        f"/api/orders/{order_id}",
        expected_status=200,
        response_model=OrderResponse,
    )

    api_client.check(
        "Fulfill approved order through API",
        "POST",
        f"/api/orders/{order_id}/fulfill",
        expected_status=200,
        response_model=OrderResponse,
    )
    qa_page.reload()
    expect(qa_page.locator("#order-status")).to_have_text("fulfilled")
