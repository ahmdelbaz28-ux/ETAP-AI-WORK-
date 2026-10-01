from unittest.mock import MagicMock, patch

import pytest

from api.r2_storage import download, generate_key, list_objects, presign, public_url


def test_r2_presign_tenant_isolation():
    key = "reports/tenant_a/report.pdf"

    # Tenant B cannot presign Tenant A's key
    with pytest.raises(ValueError, match="does not belong to tenant"):
        presign(key, tenant_id="tenant_b")

    # Tenant A can presign with mock client
    with patch("api.r2_storage.R2_ENABLED", True), \
         patch("api.r2_storage._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://r2.example.com/presigned"
        mock_get_client.return_value = mock_client

        url = presign(key, tenant_id="tenant_a")
        assert url == "https://r2.example.com/presigned"
        mock_client.generate_presigned_url.assert_called_once()


@pytest.mark.asyncio
async def test_r2_download_tenant_isolation():
    key = "reports/tenant_a/report.pdf"

    # Tenant B cannot download Tenant A's key
    with pytest.raises(ValueError, match="does not belong to tenant"):
        await download(key, tenant_id="tenant_b")

    # Tenant A download succeeds
    with patch("api.r2_storage.R2_ENABLED", True), \
         patch("api.r2_storage._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"report content")}
        mock_get_client.return_value = mock_client

        content = await download(key, tenant_id="tenant_a")
        assert content == b"report content"


def test_r2_generate_key_tenant_scoping():
    key = generate_key(prefix="reports", extension="pdf", tenant_id="tenant_a", user_id="user_1")
    assert key.startswith("tenant_a/reports/user_1/")
    assert key.endswith(".pdf")
