import pytest

from services.study_executor import StudyExecutor


def test_build_cache_params_includes_required_fields():
    """Test that _build_cache_params includes capability_id, provider, engine_version, etc."""
    executor = StudyExecutor()

    # We'll call the private method with mock data and check the returned dict.
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
        standards=standards
    )

    # Check that the cache params include the required fields
    assert cache_params['capability_id'] == capability_id
    assert cache_params['capability_version'] == capability_version
    assert cache_params['executor_kind'] == executor_kind
    assert cache_params['provider'] == provider
    assert cache_params['solver'] == solver
    assert cache_params['engine_version'] == engine_version
    assert cache_params['system_snapshot_hash'] == system_snapshot_hash
    assert cache_params['input_hash'] == input_hash
    assert cache_params['parameters_hash'] == parameters_hash
    assert cache_params['standards'] == standards
