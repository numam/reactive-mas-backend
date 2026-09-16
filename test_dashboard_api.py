from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_dashboard_tiers_endpoint_returns_five_tiers():
    response = client.get("/dashboard/tiers")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total_tiers"] == 5
    assert len(payload["tiers"]) == 5

    tier_names = [tier["tier"] for tier in payload["tiers"]]
    assert tier_names == [
        "supplier",
        "farm",
        "slaughterhouse",
        "wholesaler",
        "retail",
    ]

    first = payload["tiers"][0]
    assert "description" in first["meta"]
    assert "rule" in first
    assert "threshold_ratio" in first["rule"]
    assert "reorder_qty_ratio" in first["rule"]
    assert "explanation" in first["rule"]
