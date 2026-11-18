import pytest
import json
from Web.server import SDNRequestHandler

def test_tcam_profiler_nominal():
    """Verify handle_studio_tcam_profiler under nominal traffic conditions."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"load_level": "nominal", "eviction_strategy": "priority_eviction"}).encode('utf-8')
    handler.handle_studio_tcam_profiler(body)

    assert len(sent_payloads) == 1
    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    assert "tcam_telemetry" in data
    tcam = data["tcam_telemetry"]
    assert tcam["total_tcam_capacity_entries"] == 6144
    assert tcam["load_level"] == "nominal"
    assert tcam["active_insertion_latency_us"] == 2.4
    assert tcam["status"] == "TCAM_NOMINAL_HEADROOM_HEALTHY"
    assert tcam["vip_qos_rules_protected_pct"] == 100.0

def test_tcam_profiler_heavy_microflows():
    """Verify handle_studio_tcam_profiler under heavy microflows with priority eviction."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"load_level": "heavy_microflows", "eviction_strategy": "priority_eviction"}).encode('utf-8')
    handler.handle_studio_tcam_profiler(body)

    code, data = sent_payloads[0]
    assert code == 200
    tcam = data["tcam_telemetry"]
    assert tcam["freed_entries"] == 1800
    assert tcam["post_eviction_occupancy"] < 4915
    assert tcam["active_insertion_latency_us"] == 2.4
    assert tcam["status"] == "TCAM_FLOW_SPACE_OPTIMIZED"

def test_tcam_profiler_exhaustion_crisis():
    """Verify handle_studio_tcam_profiler under exhaustion crisis across strategies."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)

    # Without priority eviction, exhaustion should trigger slowpath
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
    body = json.dumps({"load_level": "tcam_exhaustion_crisis", "eviction_strategy": "idle_timeout_pruning"}).encode('utf-8')
    handler.handle_studio_tcam_profiler(body)

    code, data = sent_payloads[0]
    assert code == 200
    tcam = data["tcam_telemetry"]
    assert tcam["status"] == "TCAM_EXHAUSTION_SLOWPATH_CRISIS"
    assert tcam["active_insertion_latency_us"] == 184000.0  # 184 ms slow-path trap

    # With priority eviction, exhaustion is prevented
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
    body = json.dumps({"load_level": "tcam_exhaustion_crisis", "eviction_strategy": "priority_eviction"}).encode('utf-8')
    handler.handle_studio_tcam_profiler(body)

    code, data = sent_payloads[0]
    tcam = data["tcam_telemetry"]
    assert tcam["status"] == "TCAM_CRISIS_RESOLVED_BY_PRIORITY"
    assert tcam["active_insertion_latency_us"] == 3.1
    assert tcam["freed_entries"] == 2800

def test_tcam_profiler_eviction_strategies():
    """Verify handle_studio_tcam_profiler all eviction strategies."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    strategies = ["priority_eviction", "lru_eviction", "idle_timeout_pruning", "wildcard_aggregation"]

    for strat in strategies:
        sent_payloads = []
        handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
        body = json.dumps({"load_level": "heavy_microflows", "eviction_strategy": strat}).encode('utf-8')
        handler.handle_studio_tcam_profiler(body)

        code, data = sent_payloads[0]
        assert code == 200
        tcam = data["tcam_telemetry"]
        assert tcam["eviction_strategy"] == strat
        assert tcam["freed_entries"] > 0

def test_attestation_valid():
    """Verify handle_studio_attestation for valid cryptographic flow signature."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"mode": "valid_attestation"}).encode('utf-8')
    handler.handle_studio_attestation(body)

    code, data = sent_payloads[0]
    assert code == 200
    assert data["success"] is True
    rec = data["attestation_record"]
    assert rec["verification_status"] == "VERIFIED_AUTHENTIC"
    assert rec["switch_action"] == "APPLY_FLOW_MOD"
    assert rec["verification_overhead_us"] == 38.4
    assert rec["signature_algorithm"] == "HMAC-SHA256"
    assert len(rec["attestation_hmac_sha256"]) == 64

def test_attestation_tampered():
    """Verify handle_studio_attestation vetoes tampered mirror port hijacking."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"mode": "tampered_action_tampering"}).encode('utf-8')
    handler.handle_studio_attestation(body)

    code, data = sent_payloads[0]
    assert code == 200
    rec = data["attestation_record"]
    assert rec["verification_status"] == "TAMPERING_DETECTED_DISCARD"
    assert rec["switch_action"] == "DISCARD_AND_LOG_ALERT"
    assert "MISMATCH" in rec["explanation"]

def test_attestation_replay():
    """Verify handle_studio_attestation rejects replay attacks with reused nonce."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    body = json.dumps({"mode": "replay_attack_nonce_reused"}).encode('utf-8')
    handler.handle_studio_attestation(body)

    code, data = sent_payloads[0]
    assert code == 200
    rec = data["attestation_record"]
    assert rec["verification_status"] == "REPLAY_ATTACK_DETECTED_DISCARD"
    assert rec["switch_action"] == "DISCARD_AND_LOG_ALERT"
    assert "Replay" in rec["explanation"] or "nonce" in rec["explanation"]

def test_drr_scheduler_ports():
    """Verify handle_studio_drr_scheduler for egress ports 2 and 3."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)

    for port in ["port_2", "port_3"]:
        sent_payloads = []
        handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
        body = json.dumps({"egress_port": port}).encode('utf-8')
        handler.handle_studio_drr_scheduler(body)

        code, data = sent_payloads[0]
        assert code == 200
        assert data["success"] is True
        drr = data["drr_telemetry"]
        assert drr["egress_port"] == port
        assert drr["scheduling_discipline"] == "Deficit Round Robin (DRR)"
        assert drr["jains_fairness_index"] == 0.994
        assert len(drr["queues"]) == 4

def test_drr_scheduler_fairness_and_starvation():
    """Verify handle_studio_drr_scheduler maintains starvation-free guarantees."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    sent_payloads = []
    handler.send_json = lambda sc, d: sent_payloads.append((sc, d))

    handler.handle_studio_drr_scheduler(b"")

    code, data = sent_payloads[0]
    assert code == 200
    drr = data["drr_telemetry"]
    for q in drr["queues"]:
        assert q["starvation_free"] is True
        assert q["quantum_bytes"] > 0
        assert q["bytes_serviced_current_round"] > 0

def test_asian_flow_mod_synthesizer_all_intents():
    """Verify handle_asian_models_flow_mod_synthesizer across all operator intents."""
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    intents = ["reroute_elephants", "quarantine_dos", "prioritize_vip_ef46", "ecmp_split"]

    for intent in intents:
        sent_payloads = []
        handler.send_json = lambda sc, d: sent_payloads.append((sc, d))
        body = json.dumps({"intent": intent}).encode('utf-8')
        handler.handle_asian_models_flow_mod_synthesizer(body)

        code, data = sent_payloads[0]
        assert code == 200
        assert data["success"] is True
        synth = data["synthesized_flow_mod"]
        assert synth["wire_spec_verified"] is True
        assert synth["safety_barrier_status"] == "PASSED"
        assert synth["compilation_latency_ms"] <= 50.0
        assert "flow_mod" in synth

        fm = synth["flow_mod"]
        assert fm["command"] == "OFPFC_ADD"
        assert "instructions" in fm
        assert "match" in fm
        assert fm["priority"] >= 40000
