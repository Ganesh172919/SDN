"""
SELF-X Models Subsystem - Frontier Foundation Models & Asian LLM Engine
"""
from .openrouter_asian import (
    ASIAN_MODEL_CATALOG,
    BENCHMARK_COMPARISONS,
    OpenRouterAsianClient,
    query_asian_model,
    parse_policy_delta,
    get_model_catalog,
    get_benchmark_data,
)

__all__ = [
    "ASIAN_MODEL_CATALOG",
    "BENCHMARK_COMPARISONS",
    "OpenRouterAsianClient",
    "query_asian_model",
    "parse_policy_delta",
    "get_model_catalog",
    "get_benchmark_data",
]
