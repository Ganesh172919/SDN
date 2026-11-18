import pytest
import json
from Web.server import SDNRequestHandler

def test_aqm_profiler_default():
    """Verify default execution of handle_studio_aqm_profiler (ECN/DCTCP coupled marking)."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []

    def mock_send_json(status_code, data):
        sent_payloads.append((status_code, data))

    handler.send_json = mock_send_json
    handler.handle_studio_aqm_profiler(b"")

    assert len(sent_payloads) == 1
    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    assert "aqm_profiler" in data
    prof = data["aqm_profiler"]
    assert prof["algorithm"] == "ecn_dctcp"
    assert prof["status"] == "OPTIMAL_COUPLED_MARKING"
    assert prof["metrics"]["packet_drop_rate_pct"] == 0.00
    assert prof["metrics"]["median_sojourn_ms"] <= 2.0
    assert prof["metrics"]["jains_fairness_index"] >= 0.99

def test_aqm_profiler_algorithms():
    """Verify handle_studio_aqm_profiler across CoDel, PIE, and RED algorithms."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)

    for algo, expected_status in [
        ("codel", "CONTROLLED_DELAY_STABLE"),
        ("pie", "PROPORTIONAL_INTEGRAL_ACTIVE"),
        ("red_baseline", "UNCOUPLED_RANDOM_EARLY_DETECTION")
    ]:
        sent_payloads = []
        handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
        body = json.dumps({"algorithm": algo, "ecn_threshold_kb": 40.0, "traffic_load_mbps": 50.0}).encode('utf-8')
        handler.handle_studio_aqm_profiler(body)

        code, data = sent_payloads[0]
        assert code == 200
        assert data["aqm_profiler"]["algorithm"] == algo
        assert data["aqm_profiler"]["status"] == expected_status
        assert len(data["aqm_profiler"]["time_series"]) == 10

def test_int_telemetry_primary_path():
    """Verify handle_studio_int_telemetry on primary core trunk (s1 -> s2 -> s4)."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"path": "s1_s2_s4"}).encode('utf-8')
    handler.handle_studio_int_telemetry(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    int_data = data["int_telemetry"]
    assert int_data["path_key"] == "s1_s2_s4"
    assert int_data["hop_count"] == 3
    assert int_data["total_path_latency_us"] == 50.0
    assert "Switch s2" in int_data["bottleneck_hop"]
    assert int_data["int_header_overhead_bytes"] == 48
    assert int_data["hops"][1]["switch_id"] == "s2"
    assert int_data["hops"][1]["port_tx_utilization_pct"] > 90.0

def test_int_telemetry_detour_path():
    """Verify handle_studio_int_telemetry on detour path (s1 -> s3 -> s4)."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"path": "s1_s3_s4"}).encode('utf-8')
    handler.handle_studio_int_telemetry(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    int_data = data["int_telemetry"]
    assert int_data["path_key"] == "s1_s3_s4"
    assert int_data["total_path_latency_us"] == 41.0
    assert int_data["hops"][1]["switch_id"] == "s3"
    assert int_data["hops"][1]["port_tx_utilization_pct"] < 65.0

def test_asian_multi_agent_debate():
    """Verify handle_asian_models_multi_agent_debate generates 2-round dialectic and referee consensus."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"scenario": "conflicting_qos_demands"}).encode('utf-8')
    handler.handle_asian_models_multi_agent_debate(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    debate = data["debate"]
    assert len(debate["rounds"]) == 2
    assert debate["rounds"][0]["round_number"] == 1
    assert debate["rounds"][1]["round_number"] == 2
    
    # Check agents participating
    dialogue_r1 = debate["rounds"][0]["dialogue"]
    agents = [d["agent"] for d in dialogue_r1]
    assert "DeepSeek-R1" in agents
    assert "Qwen 2.5 72B Instruct" in agents

    # Check adjudication
    adj = debate["adjudication"]
    assert adj["referee"] == "DeepSeek-V3"
    assert adj["consensus_reached"] is True
    assert adj["consensus_score"] >= 99.0
    assert adj["synthesized_delta"]["adjusted_V"] == -2.0
    assert adj["synthesized_delta"]["sla_compliance_score"] >= 99.5
