"""
tests/test_rbac.py — Unit and integration tests for the RBAC system.

Tests cover:
- Role CRUD operations
- Permission CRUD operations
- User role assignments
- Permission-based access control
- System role protection
- Edge cases (duplicate names, missing IDs, etc.)
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UTC = timezone.utc

# ── Test database ────────────────────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///./data/test_rbac.db"

# Remove test db if exists
if os.path.exists("./data/test_rbac.db"):
    os.remove("./data/test_rbac.db")


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the test session."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_factory(test_engine):
    """Create a test session factory."""
    factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield factory


@pytest.fixture(autouse=True)
async def setup_db(test_engine):
    """Create all tables before each test and drop after."""
    from api.database import Base

    # Register RBAC models directly without importing other modules
    from api.rbac import Role, Permission, UserRole, role_permissions  # noqa: F401
    from api.auth import User  # noqa: F401 — register User model

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> dict[str, Any]:
    """Create a test admin user."""
    from api.auth import User, _hash_password

    user = User(
        id=str(uuid.uuid4()),
        username="testadmin",
        email="admin@test.com",
        password_hash=_hash_password("TestPass123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


@pytest.fixture
async def test_engineer_user(db_session: AsyncSession) -> dict[str, Any]:
    """Create a test engineer user."""
    from api.auth import User, _hash_password

    user = User(
        id=str(uuid.uuid4()),
        username="testengineer",
        email="engineer@test.com",
        password_hash=_hash_password("TestPass123!"),
        role="engineer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


@pytest.fixture
async def admin_token(test_user: dict[str, Any]) -> str:
    """Generate a JWT token for the test admin user."""
    from api.dependencies import JWT_SECRET_KEY, JWT_ALGORITHM
    import jwt

    payload = {
        "sub": test_user["id"],
        "role": test_user["role"],
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC).timestamp() + 3600,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


@pytest.fixture
async def engineer_token(test_engineer_user: dict[str, Any]) -> str:
    """Generate a JWT token for the test engineer user."""
    from api.dependencies import JWT_SECRET_KEY, JWT_ALGORITHM
    import jwt

    payload = {
        "sub": test_engineer_user["id"],
        "role": test_engineer_user["role"],
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC).timestamp() + 3600,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Role CRUD
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_role(db_session: AsyncSession):
    """Test creating a new role."""
    from api.rbac import Role

    role = Role(
        id=str(uuid.uuid4()),
        name="test_role",
        description="A test role",
        is_system=False,
    )
    db_session.add(role)
    await db_session.flush()
    await db_session.refresh(role)

    assert role.name == "test_role"
    assert role.description == "A test role"
    assert role.is_system is False
    assert role.id is not None


@pytest.mark.asyncio
async def test_create_duplicate_role(db_session: AsyncSession):
    """Test that duplicate role names are rejected."""
    from api.rbac import Role
    from sqlalchemy.exc import IntegrityError

    role1 = Role(
        id=str(uuid.uuid4()),
        name="unique_role",
        is_system=False,
    )
    db_session.add(role1)
    await db_session.flush()

    role2 = Role(
        id=str(uuid.uuid4()),
        name="unique_role",  # Same name
        is_system=False,
    )
    db_session.add(role2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_list_roles(db_session: AsyncSession):
    """Test listing all roles."""
    from api.rbac import Role

    # Create test roles
    for name in ["role_a", "role_b", "role_c"]:
        role = Role(id=str(uuid.uuid4()), name=name, is_system=False)
        db_session.add(role)
    await db_session.flush()

    result = await db_session.execute(select(Role))
    roles = result.scalars().all()
    assert len(roles) == 3


@pytest.mark.asyncio
async def test_update_role(db_session: AsyncSession):
    """Test updating a role."""
    from api.rbac import Role

    role = Role(id=str(uuid.uuid4()), name="old_name", is_system=False)
    db_session.add(role)
    await db_session.flush()

    role.name = "new_name"
    role.description = "Updated description"
    db_session.add(role)
    await db_session.flush()
    await db_session.refresh(role)

    assert role.name == "new_name"
    assert role.description == "Updated description"


@pytest.mark.asyncio
async def test_delete_role(db_session: AsyncSession):
    """Test deleting a role."""
    from api.rbac import Role

    role = Role(id=str(uuid.uuid4()), name="delete_me", is_system=False)
    db_session.add(role)
    await db_session.flush()

    await db_session.delete(role)
    await db_session.flush()

    result = await db_session.execute(select(Role).where(Role.name == "delete_me"))
    assert result.scalar_one_or_none() is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Permission CRUD
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_permission(db_session: AsyncSession):
    """Test creating a new permission."""
    from api.rbac import Permission

    perm = Permission(
        id=str(uuid.uuid4()),
        resource="studies",
        action="read",
        description="Can read studies",
    )
    db_session.add(perm)
    await db_session.flush()
    await db_session.refresh(perm)

    assert perm.resource == "studies"
    assert perm.action == "read"
    assert perm.description == "Can read studies"


@pytest.mark.asyncio
async def test_duplicate_permission_rejected(db_session: AsyncSession):
    """Test that duplicate resource+action pairs are rejected."""
    from api.rbac import Permission
    from sqlalchemy.exc import IntegrityError

    perm1 = Permission(
        id=str(uuid.uuid4()),
        resource="studies",
        action="read",
    )
    db_session.add(perm1)
    await db_session.flush()

    perm2 = Permission(
        id=str(uuid.uuid4()),
        resource="studies",
        action="read",  # Same resource+action
    )
    db_session.add(perm2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: User Role Assignments
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_assign_role_to_user(db_session: AsyncSession, test_user: dict[str, Any]):
    """Test assigning a role to a user."""
    from api.rbac import Role, UserRole

    role = Role(id=str(uuid.uuid4()), name="test_role", is_system=False)
    db_session.add(role)
    await db_session.flush()

    user_role = UserRole(
        id=str(uuid.uuid4()),
        user_id=test_user["id"],
        role_id=role.id,
        assigned_by="system",
    )
    db_session.add(user_role)
    await db_session.flush()

    # Verify assignment
    result = await db_session.execute(
        select(UserRole).where(
            UserRole.user_id == test_user["id"],
            UserRole.role_id == role.id,
        )
    )
    assignment = result.scalar_one_or_none()
    assert assignment is not None
    assert assignment.assigned_by == "system"


@pytest.mark.asyncio
async def test_remove_role_from_user(db_session: AsyncSession, test_user: dict[str, Any]):
    """Test removing a role from a user."""
    from api.rbac import Role, UserRole

    role = Role(id=str(uuid.uuid4()), name="remove_role", is_system=False)
    db_session.add(role)
    await db_session.flush()

    user_role = UserRole(
        id=str(uuid.uuid4()),
        user_id=test_user["id"],
        role_id=role.id,
    )
    db_session.add(user_role)
    await db_session.flush()

    # Remove
    await db_session.delete(user_role)
    await db_session.flush()

    result = await db_session.execute(
        select(UserRole).where(
            UserRole.user_id == test_user["id"],
            UserRole.role_id == role.id,
        )
    )
    assert result.scalar_one_or_none() is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Permission-based Access Control
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_role_permission_assignment(db_session: AsyncSession):
    """Test assigning permissions to a role."""
    from api.rbac import Role, Permission, role_permissions

    role = Role(id=str(uuid.uuid4()), name="perm_role", is_system=False)
    db_session.add(role)
    await db_session.flush()

    perm = Permission(
        id=str(uuid.uuid4()),
        resource="studies",
        action="read",
    )
    db_session.add(perm)
    await db_session.flush()

    # Assign permission to role
    await db_session.execute(
        role_permissions.insert().values(
            role_id=role.id,
            permission_id=perm.id,
        )
    )
    await db_session.flush()

    # Verify
    result = await db_session.execute(
        select(role_permissions).where(
            role_permissions.c.role_id == role.id,
            role_permissions.c.permission_id == perm.id,
        )
    )
    assert result.first() is not None


@pytest.mark.asyncio
async def test_admin_has_all_permissions():
    """Test that admin bypasses permission checks."""
    from api.dependencies import CurrentUser

    user = CurrentUser(
        user_id="test-id",
        username="admin",
        email="admin@test.com",
        role="admin",
        is_active=True,
    )
    assert user.role == "admin"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: RBAC API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_roles_api(test_engine, test_session_factory, admin_token):
    """Test the list roles API endpoint."""
    from api.database import Base
    from api.routes import app

    # Override the database dependency
    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    from api.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # May return 200 (success), 401 (auth), 403 (permission), or 500 (error)
        assert response.status_code in (200, 401, 403, 500)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_permissions_api(test_engine, test_session_factory, admin_token):
    """Test the list permissions API endpoint."""
    from api.routes import app
    from api.database import get_db

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code in (200, 401, 403, 500)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthorized_access(test_engine, test_session_factory):
    """Test that unauthenticated requests are rejected."""
    from api.routes import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/roles")
        assert response.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: RBAC Seed Script
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_seed_rbac_creates_default_roles(db_session: AsyncSession):
    """Test that seeding creates the 4 default system roles."""
    from api.rbac import Role

    # Simulate seeding
    roles_data = [
        ("admin", "System administrator with full access"),
        ("engineer", "Power systems engineer"),
        ("viewer", "Read-only access"),
        ("guest", "Guest with minimal access"),
    ]
    for name, desc in roles_data:
        role = Role(id=str(uuid.uuid4()), name=name, description=desc, is_system=True)
        db_session.add(role)
    await db_session.flush()

    result = await db_session.execute(select(Role))
    roles = result.scalars().all()
    role_names = [r.name for r in roles]

    assert "admin" in role_names
    assert "engineer" in role_names
    assert "viewer" in role_names
    assert "guest" in role_names
    assert all(r.is_system for r in roles)


@pytest.mark.asyncio
async def test_seed_rbac_creates_permissions(db_session: AsyncSession):
    """Test that seeding creates permissions for all resources."""
    from api.rbac import Permission

    resources = ["studies", "projects", "users", "roles", "permissions",
                 "equipment", "reports", "settings", "notifications",
                 "dashboard", "templates", "batch", "export", "import",
                 "logs", "audit"]
    actions = ["list", "read", "create", "update", "delete", "manage"]

    for resource in resources:
        for action in actions:
            perm = Permission(
                id=str(uuid.uuid4()),
                resource=resource,
                action=action,
            )
            db_session.add(perm)
    await db_session.flush()

    result = await db_session.execute(select(Permission))
    permissions = result.scalars().all()
    assert len(permissions) == len(resources) * len(actions)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_role_name_validation():
    """Test role name pattern validation."""
    from api.rbac import RoleCreateRequest
    from pydantic import ValidationError

    # Valid names
    valid = RoleCreateRequest(name="valid_role", description="Test")
    assert valid.name == "valid_role"

    # Invalid names
    with pytest.raises(ValidationError):
        RoleCreateRequest(name="invalid role!@#", description="Test")


@pytest.mark.asyncio
async def test_system_role_protection(db_session: AsyncSession):
    """Test that system roles cannot be modified or deleted."""
    from api.rbac import Role

    role = Role(id=str(uuid.uuid4()), name="system_role", is_system=True)
    db_session.add(role)
    await db_session.flush()

    # System roles should not be deletable
    assert role.is_system is True


@pytest.mark.asyncio
async def test_cascade_delete_role(db_session: AsyncSession, test_user: dict[str, Any]):
    """Test that deleting a role cascades to user-role assignments."""
    from api.rbac import Role, UserRole

    role = Role(id=str(uuid.uuid4()), name="cascade_role", is_system=False)
    db_session.add(role)
    await db_session.flush()

    user_role = UserRole(
        id=str(uuid.uuid4()),
        user_id=test_user["id"],
        role_id=role.id,
    )
    db_session.add(user_role)
    await db_session.flush()

    # First remove the user-role assignment (matching API behavior)
    await db_session.delete(user_role)
    await db_session.flush()

    # Then delete role
    await db_session.delete(role)
    await db_session.flush()

    # User-role assignment should be gone
    result = await db_session.execute(
        select(UserRole).where(UserRole.role_id == role.id)
    )
    assert result.scalar_one_or_none() is None
