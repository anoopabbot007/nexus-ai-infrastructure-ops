from fastapi.testclient import TestClient

from agent_service.main import app

client = TestClient(app)

def test_health_reports_mock_provider():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["llmProvider"] == "mock"

def test_investigate_returns_structured_report():
    response = client.post("/investigate", json={
        "incidentId": "INC-API-1", "serviceName": "payment-service", "environment": "production",
        "alertType": "HIGH_CPU", "cpuUtilization": 94, "threshold": 80,
        "severity": "CRITICAL", "description": "CPU utilization exceeded 80% for 10 minutes",
    })
    assert response.status_code == 200
    report = response.json()
    assert report["executionStatus"] == "COMPLETED"
    assert report["llmProvider"] == "mock"
    assert len(report["executionTrace"]) == 4
    assert report["probableRootCause"]

def test_invalid_severity_is_rejected_at_request_boundary():
    response = client.post("/investigate", json={
        "incidentId": "INC-API-2", "serviceName": "payment-service", "environment": "production",
        "alertType": "HIGH_CPU", "severity": "URGENT", "description": "CPU utilization exceeded threshold",
    })
    assert response.status_code == 422
