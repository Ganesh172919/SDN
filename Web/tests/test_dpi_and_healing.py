import pytest
import json
from Web.server import SDNRequestHandler

class MockServer:
    pass

def test_dpi_inspection_get():
    """Verify GET /api/studio/dpi-inspection returns valid packet frames and summary metrics."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []

    def mock_send_json(status_code, data):
        sent_payloads.append((status_code, data))

    handler.send_json = mock_send_json
    handler.handle_studio_dpi_inspection(b"")

    assert len(sent_payloads) == 1
    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    assert "frames" in data
    assert len(data["frames"]) > 0
    assert "summary_metrics" in data
    assert data["summary_metrics"]["active_meters_engaged"] == 4
    assert data["summary_metrics"]["volume_conservation_error_pct"] == 0.0

def test_dpi_inspection_filtered_post():
    """Verify POST /api/studio/dpi-inspection filters frames by DPID and flow category."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []

    def mock_send_json(status_code, data):
        sent_payloads.append((status_code, data))

    handler.send_json = mock_send_json
    body = json.dumps({"dpid": "s1", "flow_type": "elephant", "limit": 4}).encode('utf-8')
    handler.handle_studio_dpi_inspection(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    for frame in data["frames"]:
        assert frame["dpid"] == "s1"
        assert frame["flow_category"] == "elephant"
        assert frame["bit_conservation_verified"] is True
        assert "openflow_match_pipeline" in frame

def test_autonomous_healing_microburst():
    """Verify POST /api/studio/autonomous-healing resolves microburst wave with zero frame drop."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []

    def mock_send_json(status_code, data):
        sent_payloads.append((status_code, data))

    handler.send_json = mock_send_json
    body = json.dumps({"anomaly_type": "microburst_synchronization"}).encode('utf-8')
    handler.handle_studio_autonomous_healing(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    healing = data["healing"]
    assert healing["status"] == "AUTONOMOUS_HEALING_SUCCESS"
    assert healing["anomaly_type"] == "microburst_synchronization"
    telemetry = healing["telemetry_verification"]
    assert telemetry["mttr_ms"] < 5.0
    assert telemetry["packets_dropped"] == 0
    assert telemetry["post_backlog_mbit"] < telemetry["pre_backlog_mbit"]
    assert telemetry["stability_invariant_restored"] is True

def test_autonomous_healing_buffer_leak_and_tcam():
    """Verify POST /api/studio/autonomous-healing across buffer leak and TCAM thrashing anomalies."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)

    for anomaly in ["silent_buffer_leak", "tcam_hash_collision"]:
        sent_payloads = []
        handler.send_json = lambda code, data: sent_payloads.append((code, data))

        body = json.dumps({"anomaly_type": anomaly}).encode('utf-8')
        handler.handle_studio_autonomous_healing(body)

        code, data = sent_payloads[0]
        assert code == 200
        assert data["success"] is True
        assert data["healing"]["anomaly_type"] == anomaly
        assert len(data["healing"]["remediation_actions"]) >= 4

def test_asian_models_reasoning_trace():
    """Verify POST /api/asian-models/reasoning-trace provides multi-step CoT mathematical derivations."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []

    def mock_send_json(status_code, data):
        sent_payloads.append((status_code, data))

    handler.send_json = mock_send_json
    body = json.dumps({"model": "deepseek/deepseek-r1", "scenario": "core_trunk_saturation"}).encode('utf-8')
    handler.handle_asian_models_reasoning_trace(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    trace = data["reasoning_trace"]
    assert trace["model"] == "deepseek/deepseek-r1"
    assert len(trace["chain_of_thought_steps"]) == 4
    assert "synthesized_delta" in trace
    assert trace["synthesized_delta"]["delta_V"] == -2.5
    assert trace["performance"]["reasoning_tokens"] > 0
    assert trace["performance"]["token_cost_usd"] < 0.01
