"""
test_consensus_and_sla.py - Tests for Multi-Agent Consensus Protocol & SLA Audit Endpoints
"""

import json
import pytest
from Web.server import SDNRequestHandler


class DummyServer:
    def __init__(self):
        self.server_name = "127.0.0.1"
        self.server_port = 5000


def test_sla_audit_get(monkeypatch):
    sent_response = {}

    def mock_send_json(self, status, payload, headers=None):
        sent_response["status"] = status
        sent_response["payload"] = payload

    monkeypatch.setattr(SDNRequestHandler, "send_json", mock_send_json)

    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.path = "/api/studio/sla-audit"
    handler.handle_studio_sla_audit(b"")

    assert sent_response["status"] == 200
    assert sent_response["payload"]["success"] is True
    data = sent_response["payload"]["data"]
    assert data["composite_sla_score"] >= 99.0
    assert data["overall_verdict"] == "ENTERPRISE_GRADE_CERTIFIED"
    assert len(data["criteria"]) >= 6
    metrics = [c["metric"] for c in data["criteria"]]
    assert "Packet Delay (Mean)" in metrics
    assert "Packet Loss Rate" in metrics
    assert "Ingress Invariant Discard Cap" in metrics


def test_sla_audit_post(monkeypatch):
    sent_response = {}

    def mock_send_json(self, status, payload, headers=None):
        sent_response["status"] = status
        sent_response["payload"] = payload

    monkeypatch.setattr(SDNRequestHandler, "send_json", mock_send_json)

    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.path = "/api/studio/sla-audit"
    body = json.dumps({"profile": "financial_ultra_low_latency"}).encode("utf-8")
    handler.handle_studio_sla_audit(body)

    assert sent_response["status"] == 200
    assert sent_response["payload"]["data"]["profile"] == "financial_ultra_low_latency"


def test_asian_models_consensus_scenarios(monkeypatch):
    sent_response = {}

    def mock_send_json(self, status, payload, headers=None):
        sent_response["status"] = status
        sent_response["payload"] = payload

    monkeypatch.setattr(SDNRequestHandler, "send_json", mock_send_json)

    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.path = "/api/asian-models/consensus"

    for scenario in ["core_trunk_congestion", "microburst_cascade", "link_failure"]:
        body = json.dumps({"scenario": scenario}).encode("utf-8")
        handler.handle_asian_models_consensus(body)

        assert sent_response["status"] == 200
        proto = sent_response["payload"]["consensus_protocol"]
        assert "agent_1_queue" in proto
        assert "agent_2_te" in proto
        assert "agent_3_safety" in proto
        assert "consensus_verdict" in proto
        assert proto["consensus_verdict"]["consensus_score_pct"] >= 95.0
        assert "deepseek" in proto["agent_1_queue"]["model"].lower()
        assert "qwen" in proto["agent_2_te"]["model"].lower()


def test_flow_mod_flush_and_delete(monkeypatch):
    sent_response = {}

    def mock_send_json(self, status, payload, headers=None):
        sent_response["status"] = status
        sent_response["payload"] = payload

    monkeypatch.setattr(SDNRequestHandler, "send_json", mock_send_json)

    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.path = "/api/studio/flow-mod/flush"
    handler.handle_studio_flow_mod_flush(b"")

    assert sent_response["status"] == 200
    assert sent_response["payload"]["success"] is True

    handler.path = "/api/studio/flow-mod/delete"
    body = json.dumps({"rule_id": "nonexistent_rule"}).encode("utf-8")
    handler.handle_studio_flow_mod_delete(body)

    assert sent_response["status"] == 200
    assert sent_response["payload"]["success"] is False
