"""Proxy module to expose integration handler for tests.

This file re-exports the IntegrationHandler defined in the ACP test suite
so that test modules expecting `tests.integration_handlers` can import it.
"""

from acp_runtime.acp_tests.integration_handlers import IntegrationHandler
