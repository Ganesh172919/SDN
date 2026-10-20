"""Transparent numeric state embedding; no trained weights or external service."""
import math


def embed_state(state: dict) -> list[float]:
    if "embedding_features" in state:
        values = state["embedding_features"]
    else:
        values = [state.get("latency_ms", 0) / 50,
                  state.get("throughput_kbps", 0) / 10000,
                  state.get("loss_pct", 0) / 20]
    vector = [float(v) for v in values] + [0.1]
    if not all(math.isfinite(v) for v in vector):
        raise ValueError("embedding features must be finite")
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) if len(a) == len(b) else 0.0
