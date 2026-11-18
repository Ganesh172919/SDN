"""
Unit tests for the new Testing Studio Link Impairment, Live Benchmark Runner,
and Asian Models 4-Way Arena & MLA Memory Calculator endpoints.
"""
import pytest
import json
from Web.server import SDNRequestHandler, DEFAULT_LINK_IMPAIRMENTS, ACTIVE_LINK_IMPAIRMENTS

class DummyRequest:
    def makefile(self, *args, **kwargs):
        pass
    def sendall(self, *args, **kwargs):
        pass

def test_link_impairment_status(monkeypatch):
    responses = []
    def fake_send_json(self, status, payload, headers=None):
        responses.append((status, payload))
    monkeypatch.setattr(SDNRequestHandler, 'send_json', fake_send_json)
    
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.handle_studio_link_impairment_status()
    
    assert len(responses) == 1
    status, payload = responses[0]
    assert status == 200
    assert payload["success"] is True
    assert "s1-s2" in payload["impairments"]
    assert payload["total_links"] == 4

def test_link_impairment_set_and_reset(monkeypatch):
    responses = []
    def fake_send_json(self, status, payload, headers=None):
        responses.append((status, payload))
    monkeypatch.setattr(SDNRequestHandler, 'send_json', fake_send_json)
    
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    # Set link degradation
    set_payload = json.dumps({"link_id": "s1-s2", "latency_ms": 50.0, "loss_pct": 10.0}).encode('utf-8')
    handler.handle_studio_link_impairment_set(set_payload)
    
    assert len(responses) == 1
    assert responses[0][0] == 200
    assert responses[0][1]["impairment"]["status"] == "DEGRADED"
    assert responses[0][1]["optimal_path_recommendation"] == "s1 -> s3 -> s4"
    
    # Reset
    handler.handle_studio_link_impairment_reset(b"{}")
    assert len(responses) == 2
    assert responses[1][0] == 200
    assert responses[1][1]["impairments"]["s1-s2"]["status"] == "NOMINAL"

def test_benchmark_runner(monkeypatch):
    responses = []
    def fake_send_json(self, status, payload, headers=None):
        responses.append((status, payload))
    monkeypatch.setattr(SDNRequestHandler, 'send_json', fake_send_json)
    
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    body = json.dumps({
        "controllers": ["S0_STATIC", "S5_SELFX"],
        "duration_seconds": 2
    }).encode('utf-8')
    handler.handle_studio_benchmark_run(body)
    
    assert len(responses) == 1
    status, payload = responses[0]
    assert status == 200
    assert payload["success"] is True
    assert "S0_STATIC" in payload["series"]
    assert "S5_SELFX" in payload["series"]
    assert len(payload["series"]["S0_STATIC"]["timestamps"]) == 20

def test_asian_models_arena(monkeypatch):
    responses = []
    def fake_send_json(self, status, payload, headers=None):
        responses.append((status, payload))
    monkeypatch.setattr(SDNRequestHandler, 'send_json', fake_send_json)
    
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    handler.handle_asian_models_arena(json.dumps({"scenario": "jitter_storm"}).encode('utf-8'))
    
    assert len(responses) == 1
    status, payload = responses[0]
    assert status == 200
    assert payload["success"] is True
    assert len(payload["arena_results"]) >= 4
    model_ids = [m["id"] for m in payload["arena_results"]]
    assert "deepseek/deepseek-r1" in model_ids
    assert "01-ai/yi-lightning" in model_ids
    assert "perplexity/pplx-decider-v1.3:free" in model_ids
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in model_ids

def test_asian_models_mla_calculator(monkeypatch):
    responses = []
    def fake_send_json(self, status, payload, headers=None):
        responses.append((status, payload))
    monkeypatch.setattr(SDNRequestHandler, 'send_json', fake_send_json)
    
    handler = SDNRequestHandler.__new__(SDNRequestHandler)
    body = json.dumps({"context_length": 4096, "batch_size": 1}).encode('utf-8')
    handler.handle_asian_models_mla_calculator(body)
    
    assert len(responses) == 1
    status, payload = responses[0]
    assert status == 200
    assert payload["success"] is True
    assert payload["reduction_percentage"] > 90.0
    assert payload["concurrency_multiplier"] > 10.0
