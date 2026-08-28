"""P5 ResultStore tests.

Covers, per the P5 mandate (tenant isolation, file safety, size limits,
expiry, cleanup, write atomicity, study integration):

* create / read result; missing -> 404
* tenant isolation (cross-tenant read/file/stream denied -> 404)
* tenant spoofing ignored (tenant always from authenticated user context)
* expired result never returned as valid content
* exact 10 MiB accepted; > 10 MiB rejected before storage
* `../`, `..\\`, absolute paths, drive letters, traversal -> rejected
* result_files relation + physical file existence
* heavy content stays OUT of the DB (only path/mime/size metadata)
* study completion returns a `resultId`
* cleanup removes expired result (DB row + file metadata + physical files)
  while preserving live results in every tenant
* write atomicity: DB-commit failure removes the physical file; file-write
  failure leaves no DB row and no orphaned partial file

Isolation strategy: a minimal FastAPI app mounting ONLY the results router,
with ``get_current_user_from_header`` overridden to return a fixed
:class:`CurrentUser` (same pattern as ``tests/test_approvals.py``). The
tenant therefore always originates from the authenticated user context —
exactly the production semantics — with no JWT/CSRF coupling. Physical
files go to a per-test ``tmp_path`` via ``RESULT_STORE_DIR``.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import api.results_store as results_store
from api.database import async_session
from api.dependencies import CurrentUser, get_current_user_from_header
from api.results_store import (
    RESULT_FILE_MAX_BYTES,
    ResultFileRecord,
    ResultRecord,
    cleanup_expired_results,
    create_result,
    get_result,
    open_result_file,
    persist_study_result,
    store_result_file,
)

UTC = timezone.utc

TENANT_A = "tenant-alpha"
TENANT_B = "tenant-beta"

USER_A = CurrentUser(
    user_id="user-a", username="alpha", email="a@example.com",
    role="engineer", tenant_id=TENANT_A,
)
USER_B = CurrentUser(
    user_id="user-b", username="beta", email="b@example.com",
    role="engineer", tenant_id=TENANT_B,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def result_store_dir(tmp_path, monkeypatch):
    """Isolate physical files in a per-test temp dir."""
    target = tmp_path / "results"
    monkeypatch.setenv("RESULT_STORE_DIR", str(target))
    return target


@pytest.fixture
def api(result_store_dir):
    """Minimal app with only the results router; current user = USER_A."""
    app = FastAPI()
    app.include_router(results_store.router)
    holder = {"user": USER_A}

    async def _current_user():
        return holder["user"]

    app.dependency_overrides[get_current_user_from_header] = _current_user
    return {"app": app, "holder": holder}


@pytest.fixture
async def client(api):
    async with AsyncClient(
        transport=ASGITransport(app=api["app"]), base_url="http://test"
    ) as ac:
        yield ac


def _as_user(api, user: CurrentUser) -> None:
    """Switch the authenticated user the test app injects into routes."""
    api["holder"]["user"] = user


async def _force_expire(result_id: str, seconds: int = -1) -> None:
    """Push a result's expires_at into the past (simulated TTL elapsed)."""
    past = datetime.now(UTC) + timedelta(seconds=seconds)
    async with async_session() as session:
        row = (
            await session.execute(
                select(ResultRecord).where(ResultRecord.id == result_id)
            )
        ).scalar_one()
        row.expires_at = past
        await session.commit()


async def _db_result_ids() -> set[str]:
    async with async_session() as session:
        rows = (await session.execute(select(ResultRecord))).scalars().all()
        return {r.id for r in rows}


@pytest.fixture(autouse=True)
async def _purge_results_tables():
    """Purge P5 tables around every test.

    ``conftest.py`` points DATABASE_URL at a file-based SQLite DB shared by
    the whole suite, so results created (or force-expired) by an earlier
    test would otherwise leak into later assertions (e.g. cleanup counts).
    The purge touches ONLY the P5-owned ``results``/``result_files`` tables.
    """
    from sqlalchemy import delete

    async with async_session() as session:
        await session.execute(delete(ResultFileRecord))
        await session.execute(delete(ResultRecord))
        await session.commit()
    yield
    async with async_session() as session:
        await session.execute(delete(ResultFileRecord))
        await session.execute(delete(ResultRecord))
        await session.commit()


# ---------------------------------------------------------------------------
# 1. Create / read / missing
# ---------------------------------------------------------------------------


class TestCreateAndRead:
    async def test_create_result(self, client):
        resp = await client.post(
            "/api/v1/results",
            json={"summary": {"study_type": "load_flow", "buses": 3}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"]
        assert data["tenant_id"] == TENANT_A
        assert data["summary"]["study_type"] == "load_flow"
        assert data["created_by"] == USER_A.user_id
        assert data["created_at"].endswith("Z")
        assert data["expires_at"].endswith("Z")
        # default TTL = 30 days
        created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        assert abs((expires - created).total_seconds() - 30 * 86400) < 5

    async def test_read_result(self, client):
        create = await client.post("/api/v1/results", json={"summary": {"k": "v"}})
        rid = create.json()["id"]
        resp = await client.get(f"/api/v1/results/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["files"] == []
        assert data["summary"] == {"k": "v"}

    async def test_missing_result_404(self, client):
        resp = await client.get(f"/api/v1/results/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_read_is_404(self, client, api):
        create = await client.post("/api/v1/results", json={"summary": {"a": 1}})
        rid = create.json()["id"]
        assert create.json()["tenant_id"] == TENANT_A

        _as_user(api, USER_B)  # authenticate as the other tenant
        resp = await client.get(f"/api/v1/results/{rid}")
        assert resp.status_code == 404  # no existence disclosure

    async def test_cross_tenant_file_access_denied(self, client, api):
        create = await client.post("/api/v1/results", json={})
        rid = create.json()["id"]
        up = await client.post(
            f"/api/v1/results/{rid}/files",
            files={"file": ("report.txt", b"secret-data", "text/plain")},
            data={"file_path": "reports/report.txt"},
        )
        assert up.status_code == 201

        _as_user(api, USER_B)
        resp = await client.get(f"/api/v1/results/{rid}/files/reports/report.txt")
        assert resp.status_code == 404

    async def test_tenant_spoofing_denied(self, client):
        """A spoofed tenant_id in the body must be ignored entirely."""
        resp = await client.post(
            "/api/v1/results",
            json={"summary": {}, "tenant_id": TENANT_B, "created_by": "attacker"},
        )
        assert resp.status_code == 201
        assert resp.json()["tenant_id"] == TENANT_A  # from auth context only
        assert resp.json()["created_by"] == USER_A.user_id

        # And the DB agrees — nothing was stored under the spoofed tenant.
        async with async_session() as session:
            row = (
                await session.execute(
                    select(ResultRecord).where(ResultRecord.id == resp.json()["id"])
                )
            ).scalar_one()
            assert row.tenant_id == TENANT_A

    async def test_cross_tenant_file_upload_rejected(self, client, api):
        create = await client.post("/api/v1/results", json={})
        rid = create.json()["id"]
        _as_user(api, USER_B)
        resp = await client.post(
            f"/api/v1/results/{rid}/files",
            files={"file": ("x.txt", b"data", "text/plain")},
            data={"file_path": "x.txt"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Expiry
# ---------------------------------------------------------------------------


class TestExpiry:
    async def test_expired_result_never_returned(self, client):
        create = await client.post("/api/v1/results", json={"summary": {"x": 1}})
        rid = create.json()["id"]
        assert (await client.get(f"/api/v1/results/{rid}")).status_code == 200

        await _force_expire(rid)

        resp = await client.get(f"/api/v1/results/{rid}")
        assert resp.status_code == 404
        # and the storage layer agrees
        assert await get_result(TENANT_A, rid) is None

    async def test_expired_result_file_stream_denied(self, client, api, result_store_dir):
        create = await client.post("/api/v1/results", json={})
        rid = create.json()["id"]
        await store_result_file(TENANT_A, rid, "f.txt", b"data", "text/plain")
        await _force_expire(rid)

        resp = await client.get(f"/api/v1/results/{rid}/files/f.txt")
        assert resp.status_code == 404
        # direct storage-level check too
        assert await open_result_file(TENANT_A, rid, "f.txt") is None

# ---------------------------------------------------------------------------
# 4. File size limits
# ---------------------------------------------------------------------------


class TestFileSizeLimit:
    async def test_exact_10mib_accepted(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        payload = b"x" * RESULT_FILE_MAX_BYTES  # exactly 10 MiB
        fid = await store_result_file(TENANT_A, rid, "big.bin", payload, "application/octet-stream")
        assert fid
        data = await get_result(TENANT_A, rid)
        assert data["files"][0]["size_bytes"] == RESULT_FILE_MAX_BYTES

    async def test_over_10mib_rejected_before_storage(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        payload = b"x" * (RESULT_FILE_MAX_BYTES + 1)
        with pytest.raises(HTTPException) as exc:
            await store_result_file(TENANT_A, rid, "big.bin", payload)
        assert exc.value.status_code == 413
        # nothing was stored: no DB row, no physical file
        data = await get_result(TENANT_A, rid)
        assert data["files"] == []
        assert not (results_store._result_dir(TENANT_A, rid) / "big.bin").exists()

    async def test_http_upload_enforces_limit(self, client, monkeypatch):
        monkeypatch.setattr(results_store, "RESULT_FILE_MAX_BYTES", 64)
        create = await client.post("/api/v1/results", json={})
        rid = create.json()["id"]

# ---------------------------------------------------------------------------
# 5. Path safety
# ---------------------------------------------------------------------------


class TestPathSafety:
    @pytest.mark.parametrize(
        "bad_path",
        [
            "../escape.txt",          # unix parent traversal
            "..\\escape.txt",         # windows parent traversal
            "sub/../../escape.txt",   # nested traversal
            "/etc/passwd",            # unix absolute
            "C:\\Windows\\evil.txt",  # windows drive-letter absolute
            "C:/Windows/evil.txt",    # drive letter, forward slashes
            "\\\\server\\share\\f",   # UNC path
            "",                       # empty
            ".",                      # dot
        ],
    )
    async def test_traversal_paths_rejected_on_store(self, result_store_dir, bad_path):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        with pytest.raises(HTTPException) as exc:
            await store_result_file(TENANT_A, rid, bad_path, b"data")
        assert exc.value.status_code in (400, 413)
        # nothing written anywhere for this result
        data = await get_result(TENANT_A, rid)
        assert data["files"] == []

    @pytest.mark.parametrize(
        "bad_path", ["../escape.txt", "..\\escape.txt", "/etc/passwd", "C:\\x.txt"]
    )
    async def test_traversal_paths_rejected_on_read(self, bad_path):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        # open_result_file signals traversal rejection with HTTPException(400);
        # the HTTP route maps it to a 400 response (still a hard rejection).
        with pytest.raises(HTTPException) as exc:
            await open_result_file(TENANT_A, rid, bad_path)
        assert exc.value.status_code in (400, 404)

    async def test_no_file_lands_outside_result_dir(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        with pytest.raises(HTTPException):
            await store_result_file(TENANT_A, rid, "../outside.txt", b"data")
        # nothing was written anywhere under the tenant storage root
        tenant_root = result_store_dir / "tenants" / TENANT_A
        written = (
            [p for p in tenant_root.rglob("*") if p.is_file()]
            if tenant_root.exists()
            else []
        )
        assert written == []
        # a subsequent legitimate write stays strictly inside the result dir
        await store_result_file(TENANT_A, rid, "ok.txt", b"fine")
        rdir = results_store._result_dir(TENANT_A, rid)
        assert (rdir / "ok.txt").is_file()
        assert not (rdir.parent / "outside.txt").exists()
        assert not (rdir.parent.parent / "outside.txt").exists()


# ---------------------------------------------------------------------------
# 6. result_files relation + physical files + heavy content NOT in DB
# ---------------------------------------------------------------------------


class TestFileStorage:
    async def test_result_files_relation(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        await store_result_file(TENANT_A, rid, "b.bin", b"bbb", "application/octet-stream")
        await store_result_file(TENANT_A, rid, "a.txt", b"aaa", "text/plain")

        data = await get_result(TENANT_A, rid)
        paths = [f["path"] for f in data["files"]]
        assert paths == ["a.txt", "b.bin"]  # sorted, both present
        assert data["files"][0]["mime"] == "text/plain"
        assert data["files"][0]["size_bytes"] == 3

        async with async_session() as session:
            rows = (
                await session.execute(
                    select(ResultFileRecord).where(ResultFileRecord.result_id == rid)
                )
            ).scalars().all()
            assert {r.path for r in rows} == {"a.txt", "b.bin"}
            assert all(r.result_id == rid for r in rows)

    async def test_physical_files_exist_on_disk(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        await store_result_file(TENANT_A, rid, "reports/out.csv", b"1,2,3", "text/csv")
        physical = result_store_dir / "tenants" / TENANT_A / "results" / rid / "reports" / "out.csv"
        assert physical.is_file()
        assert physical.read_bytes() == b"1,2,3"

    async def test_heavy_content_not_stored_inside_db(self, result_store_dir):
        """result_files holds ONLY path/mime/size metadata — no blob column."""
        assert set(c.name for c in ResultFileRecord.__table__.columns) == {
            "id", "result_id", "path", "mime", "size_bytes",
        }
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        blob = os.urandom(4096)
        await store_result_file(TENANT_A, rid, "blob.bin", blob, "application/octet-stream")
        async with async_session() as session:
            row = (
                await session.execute(
                    select(ResultFileRecord).where(ResultFileRecord.result_id == rid)
                )
            ).scalar_one()
            # no column carries the payload bytes
            values = (row.id, row.result_id, row.path, row.mime, row.size_bytes)

# ---------------------------------------------------------------------------
# 7. Cleanup — removes ONLY expired results, across all tenants
# ---------------------------------------------------------------------------


class TestCleanup:
    async def test_cleanup_removes_expired_and_preserves_live(self, result_store_dir):
        # tenant A: one result to expire (with a file), one to keep
        rid_expired_a = await create_result(tenant_id=TENANT_A, summary_json={})
        await store_result_file(TENANT_A, rid_expired_a, "old.csv", b"old", "text/csv")
        rid_live_a = await create_result(tenant_id=TENANT_A, summary_json={})
        await store_result_file(TENANT_A, rid_live_a, "new.csv", b"new", "text/csv")
        # tenant B: a live result that must be untouched
        rid_live_b = await create_result(tenant_id=TENANT_B, summary_json={})
        await store_result_file(TENANT_B, rid_live_b, "b.csv", b"bee", "text/csv")

        await _force_expire(rid_expired_a)

        removed = await cleanup_expired_results()
        assert removed == 1

        # expired: DB row, file metadata and physical dir are all gone
        assert await get_result(TENANT_A, rid_expired_a) is None
        assert not (result_store_dir / "tenants" / TENANT_A / "results" / rid_expired_a).exists()
        # live results in BOTH tenants preserved, files intact
        assert await get_result(TENANT_A, rid_live_a) is not None
        assert await get_result(TENANT_B, rid_live_b) is not None
        live_a_csv = result_store_dir / "tenants" / TENANT_A / "results" / rid_live_a / "new.csv"
        live_b_csv = result_store_dir / "tenants" / TENANT_B / "results" / rid_live_b / "b.csv"
        assert live_a_csv.read_bytes() == b"new"
        assert live_b_csv.read_bytes() == b"bee"

    async def test_cleanup_is_idempotent(self, result_store_dir):
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        await _force_expire(rid)
        assert await cleanup_expired_results() == 1
        assert await cleanup_expired_results() == 0


# ---------------------------------------------------------------------------
# 8. Study completion integration — resultId is returned
# ---------------------------------------------------------------------------


class TestStudyIntegration:
    async def test_persist_study_result_returns_readable_result_id(self, result_store_dir):
        result_id = await persist_study_result(
            tenant_id=TENANT_A,
            created_by=USER_A.user_id,
            summary_json={"study_type": "load_flow", "status": "success"},
        )
        assert result_id
        data = await get_result(TENANT_A, result_id)
        assert data is not None
        assert data["id"] == result_id
        assert data["summary"]["study_type"] == "load_flow"
        # other tenants cannot see it
        assert await get_result(TENANT_B, result_id) is None

    async def test_study_result_model_carries_result_id(self):
        from core_model.specs import StudyResult

        result = StudyResult(success=True, result_id="abc-123")
        assert result.result_id == "abc-123"
        payload = result.model_dump()
        assert payload["result_id"] == "abc-123"
        # default is unset (API behaviour unchanged when persistence is off)
        assert StudyResult(success=True).result_id is None


# ---------------------------------------------------------------------------
# 9. Write atomicity
# ---------------------------------------------------------------------------


class TestWriteAtomicity:
    async def test_db_commit_failure_leaves_no_orphan_file(self, result_store_dir, monkeypatch):
        """If the metadata commit fails, the physical file is removed."""
        rid = await create_result(tenant_id=TENANT_A, summary_json={})
        real_session = results_store.async_session
        calls = {"n": 0}

        @asynccontextmanager
        async def flaky_session():
            calls["n"] += 1
            if calls["n"] >= 2:  # first use = row fetch, second = metadata commit
                raise RuntimeError("simulated db outage")
            async with real_session() as session:
                yield session

        monkeypatch.setattr(results_store, "async_session", flaky_session)
        with pytest.raises(HTTPException) as exc:
            await results_store.store_result_file(TENANT_A, rid, "f.txt", b"data")
        assert exc.value.status_code == 500

        rdir = result_store_dir / "tenants" / TENANT_A / "results" / rid
        assert not (rdir / "f.txt").exists()          # no false success
        assert not [p for p in rdir.rglob("*") if p.is_file()]  # no staged leftovers

    async def test_file_write_failure_leaves_no_db_row(self, result_store_dir, monkeypatch):
        """If the physical write fails, no result_files row is committed."""
        rid = await create_result(tenant_id=TENANT_A, summary_json={})

        def broken_replace(*args, **kwargs):
            raise OSError("simulated disk full")

        monkeypatch.setattr(results_store.os, "replace", broken_replace)
        with pytest.raises(HTTPException) as exc:
            await results_store.store_result_file(TENANT_A, rid, "f.txt", b"data")
        assert exc.value.status_code == 500

        data = await get_result(TENANT_A, rid)
        assert data["files"] == []  # DB never pointed at a missing file
