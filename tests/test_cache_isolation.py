import pytest

from api.semantic_cache import SemanticCache
from services.study_executor import StudyExecutor


def test_build_cache_params_includes_required_fields():
    """Test that _build_cache_params includes capability_id, provider, engine_version, etc."""
    executor = StudyExecutor()

    capability_id = "load_flow"
    capability_version = "1.0.0"
    executor_kind = "native"
    provider = "native"
    solver = "newton_raphson"
    engine_version = "2.1.0"
    system_snapshot_hash = "hash_system"
    input_hash = "hash_input"
    parameters_hash = "hash_params"
    standards = {"standard": "value"}

    cache_params = executor._build_cache_params(
        capability_id=capability_id,
        capability_version=capability_version,
        executor_kind=executor_kind,
        provider=provider,
        solver=solver,
        engine_version=engine_version,
        system_snapshot_hash=system_snapshot_hash,
        input_hash=input_hash,
        parameters_hash=parameters_hash,
        standards=standards,
    )

    assert cache_params["capability_id"] == capability_id
    assert cache_params["capability_version"] == capability_version
    assert cache_params["executor_kind"] == executor_kind
    assert cache_params["provider"] == provider
    assert cache_params["solver"] == solver
    assert cache_params["engine_version"] == engine_version
    assert cache_params["system_snapshot_hash"] == system_snapshot_hash
    assert cache_params["input_hash"] == input_hash
    assert cache_params["parameters_hash"] == parameters_hash
    assert cache_params["standards"] == standards


@pytest.mark.asyncio
async def test_semantic_cache_tenant_isolation():
    """Test L1 — Cache stored under Tenant A cannot be retrieved by Tenant B."""
    cache = SemanticCache()

    system_data = {"base_mva": 100, "buses": [{"id": 1, "type": "slack"}]}
    parameters = {"tolerance": 1e-4}
    result_data = {"converged": True, "tenant": "tenant_A"}

    # Store under tenant_A
    await cache.store(
        system_data=system_data,
        parameters=parameters,
        agent_handle="load_flow",
        result=result_data,
        tenant_id="tenant_A",
        provider="native",
    )

    # Lookup under tenant_B -> Must MISS (None)
    miss = await cache.lookup(
        system_data=system_data,
        parameters=parameters,
        agent_handle="load_flow",
        tenant_id="tenant_B",
        provider="native",
    )
    assert miss is None, "Tenant B must not access Tenant A's cached study results"

    # Lookup under tenant_A -> Must HIT
    hit = await cache.lookup(
        system_data=system_data,
        parameters=parameters,
        agent_handle="load_flow",
        tenant_id="tenant_A",
        provider="native",
    )
    assert hit is not None
    assert hit.result["tenant"] == "tenant_A"


@pytest.mark.asyncio
async def test_semantic_cache_provider_isolation():
    """Test L2 — Native study result cannot be returned for ETAP provider request."""
    cache = SemanticCache()

    system_data = {"base_mva": 100, "buses": [{"id": 1}]}
    parameters = {"method": "nr"}
    native_result = {"converged": True, "provider": "native", "voltages": [1.0]}

    # Store Native study result
    await cache.store(
        system_data=system_data,
        parameters=parameters,
        agent_handle="load_flow",
        result=native_result,
        tenant_id="tenant_common",
        provider="native",
    )

    # Request ETAP provider calculation with same parameters -> Must MISS
    etap_miss = await cache.lookup(
        system_data=system_data,
        parameters=parameters,
        agent_handle="load_flow",
        tenant_id="tenant_common",
        provider="etap",
    )
    assert etap_miss is None, "ETAP study request must not hit native solver cached result"
