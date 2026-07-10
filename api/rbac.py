"""
api/rbac.py — Role-Based Access Control (RBAC) system.

Provides:
- Role & Permission ORM models
- UserRole many-to-many association
- Permission-based access control dependency
- CRUD endpoints for roles and permissions
- Audit logging for all RBAC changes

Exposes endpoints under the ``/api/v1/auth`` prefix:
* ``GET    /roles``              — List all roles (admin only)
* ``POST   /roles``              — Create a new role (admin only)
* ``PUT    /roles/{role_id}``    — Update a role (admin only)
* ``DELETE /roles/{role_id}``    — Delete a role (admin only)
* ``GET    /permissions``        — List all permissions (admin only)
* ``POST   /permissions``        — Create a permission (admin only)
* ``GET    /users/{user_id}/roles``  — Get user roles (admin only)
* ``POST   /users/{user_id}/roles``  — Assign roles to user (admin only)
* ``DELETE /users/{user_id}/roles/{role_id}`` — Remove role from user (admin only)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

UTC = UTC

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base, get_db
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_current_user_from_header,
    pagination_params,
)

# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class Role(Base):
    """A named role (e.g. admin, engineer, viewer, guest)."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    users = relationship("UserRole", back_populates="role")


class Permission(Base):
    """A granular permission (resource + action)."""

    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    # Relationships
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


# Association table: Role <-> Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class UserRole(Base):
    """Many-to-many association between users and roles."""

    __tablename__ = "user_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    # Relationships
    role = relationship("Role", back_populates="users")


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------


class RoleCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/roles``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    permission_ids: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/auth/roles/{role_id}``."""

    model_config = ConfigDict(strict=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    permission_ids: Optional[list[str]] = None


class RoleResponse(BaseModel):
    """Public role representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    permission_ids: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RoleListResponse(BaseModel):
    """Paginated role list response."""

    model_config = ConfigDict(from_attributes=True)

    roles: list[RoleResponse]
    total: int
    page: int
    page_size: int


class PermissionCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/permissions``."""

    model_config = ConfigDict(strict=False)

    resource: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)


class PermissionResponse(BaseModel):
    """Public permission representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    resource: str
    action: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class PermissionListResponse(BaseModel):
    """Paginated permission list response."""

    model_config = ConfigDict(from_attributes=True)

    permissions: list[PermissionResponse]
    total: int
    page: int
    page_size: int


class UserRoleAssignRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/users/{user_id}/roles``."""

    model_config = ConfigDict(strict=False)

    role_ids: list[str] = Field(min_length=1)


class UserRoleResponse(BaseModel):
    """User role assignment response."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    roles: list[RoleResponse]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/auth", tags=["RBAC"])


# ---------------------------------------------------------------------------
# Permission-based access control dependency
# ---------------------------------------------------------------------------


def require_permission(resource: str, action: str):
    """Dependency factory that checks if the user has a specific permission.

    Usage::

        @router.get("/projects", dependencies=[Depends(require_permission("projects", "read"))])
        async def list_projects(...):
            ...

    Returns a dependency callable suitable for ``Depends()``.
    """

    async def _check_permission(
        user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
        db: AsyncSession = Depends(get_db),  # noqa: B008
    ) -> CurrentUser:
        # Admin has all permissions
        if user.role == "admin":
            return user

        # Check if user has the required permission through their roles
        from sqlalchemy import select as _select

        # Get all role IDs for this user
        role_stmt = _select(UserRole.role_id).where(UserRole.user_id == user.user_id)
        role_result = await db.execute(role_stmt)
        role_ids = [row[0] for row in role_result.fetchall()]

        if not role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {resource}:{action}",
            )

        # Check if any of the user's roles have the required permission
        perm_stmt = _select(role_permissions).where(
            role_permissions.c.role_id.in_(role_ids),
            role_permissions.c.permission_id.in_(
                _select(Permission.id).where(
                    Permission.resource == resource,
                    Permission.action == action,
                )
            ),
        )
        perm_result = await db.execute(perm_stmt)
        if perm_result.first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {resource}:{action}",
            )

        return user

    return _check_permission


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def _get_role_by_id(db: AsyncSession, role_id: str) -> Role:
    """Fetch a role by ID or raise 404."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role not found: {role_id}",
        )
    return role


async def _get_permission_by_id(db: AsyncSession, permission_id: str) -> Permission:
    """Fetch a permission by ID or raise 404."""
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    permission = result.scalar_one_or_none()
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission not found: {permission_id}",
        )
    return permission


async def _sync_role_permissions(db: AsyncSession, role: Role, permission_ids: list[str]) -> None:
    """Synchronize the permissions assigned to a role."""
    # Clear existing permissions
    await db.execute(role_permissions.delete().where(role_permissions.c.role_id == role.id))

    # Add new permissions
    for perm_id in permission_ids:
        perm = await _get_permission_by_id(db, perm_id)
        await db.execute(
            role_permissions.insert().values(role_id=role.id, permission_id=perm.id)
        )


async def _build_role_response(db: AsyncSession, role: Role) -> RoleResponse:
    """Build a RoleResponse with permission IDs."""
    result = await db.execute(
        select(role_permissions.c.permission_id).where(
            role_permissions.c.role_id == role.id
        )
    )
    permission_ids = [row[0] for row in result.fetchall()]
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permission_ids=permission_ids,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints — Roles
# ---------------------------------------------------------------------------


@router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="List all roles (admin only)",
)
async def list_roles(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("roles", "list")),  # noqa: B008
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
) -> Any:
    """Return a paginated list of all roles. Requires the ``admin`` role."""
    # Total count
    count_result = await db.execute(select(func.count()).select_from(Role))
    total = count_result.scalar_one()

    # Paginated query
    result = await db.execute(
        select(Role)
        .order_by(Role.name.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    roles = result.scalars().all()

    role_responses = []
    for role in roles:
        role_responses.append(await _build_role_response(db, role))

    return RoleListResponse(
        roles=role_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role (admin only)",
)
async def create_role(
    body: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("roles", "create")),  # noqa: B008
) -> Any:
    """Create a new role with optional permission assignments."""
    # Check name uniqueness
    existing = await db.execute(select(Role).where(Role.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role already exists: {body.name}",
        )

    role = Role(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        is_system=False,
    )
    db.add(role)
    await db.flush()

    # Assign permissions
    if body.permission_ids:
        await _sync_role_permissions(db, role, body.permission_ids)

    await db.refresh(role)
    return await _build_role_response(db, role)


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update a role (admin only)",
)
async def update_role(
    role_id: str,
    body: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("roles", "update")),  # noqa: B008
) -> Any:
    """Update a role's name, description, and/or permissions."""
    role = await _get_role_by_id(db, role_id)

    # Prevent modifying system roles
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be modified",
        )

    if body.name is not None:
        # Check name uniqueness
        existing = await db.execute(
            select(Role).where(Role.name == body.name, Role.id != role_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role already exists: {body.name}",
            )
        role.name = body.name

    if body.description is not None:
        role.description = body.description

    role.updated_at = datetime.now(UTC)
    db.add(role)
    await db.flush()

    # Sync permissions if provided
    if body.permission_ids is not None:
        await _sync_role_permissions(db, role, body.permission_ids)

    await db.refresh(role)
    return await _build_role_response(db, role)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a role (admin only)",
)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("roles", "delete")),  # noqa: B008
) -> dict[str, str]:
    """Delete a role. System roles cannot be deleted."""
    role = await _get_role_by_id(db, role_id)

    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System roles cannot be deleted",
        )

    # Remove all user-role associations
    await db.execute(
        UserRole.__table__.delete().where(UserRole.role_id == role_id)
    )

    # Remove all role-permission associations
    await db.execute(
        role_permissions.delete().where(role_permissions.c.role_id == role_id)
    )

    await db.delete(role)
    await db.flush()

    return {"message": f"Role '{role.name}' has been deleted"}


# ---------------------------------------------------------------------------
# Endpoints — Permissions
# ---------------------------------------------------------------------------


@router.get(
    "/permissions",
    response_model=PermissionListResponse,
    summary="List all permissions (admin only)",
)
async def list_permissions(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("permissions", "list")),  # noqa: B008
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
) -> Any:
    """Return a paginated list of all permissions."""
    # Total count
    count_result = await db.execute(select(func.count()).select_from(Permission))
    total = count_result.scalar_one()

    # Paginated query
    result = await db.execute(
        select(Permission)
        .order_by(Permission.resource.asc(), Permission.action.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size),
    )
    permissions = result.scalars().all()

    return PermissionListResponse(
        permissions=[
            PermissionResponse(
                id=str(p.id),
                resource=p.resource,
                action=p.action,
                description=p.description,
                created_at=p.created_at,
            )
            for p in permissions
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new permission (admin only)",
)
async def create_permission(
    body: PermissionCreateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("permissions", "create")),  # noqa: B008
) -> Any:
    """Create a new permission (resource + action pair)."""
    # Check uniqueness
    existing = await db.execute(
        select(Permission).where(
            Permission.resource == body.resource,
            Permission.action == body.action,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Permission already exists: {body.resource}:{body.action}",
        )

    permission = Permission(
        id=str(uuid.uuid4()),
        resource=body.resource,
        action=body.action,
        description=body.description,
    )
    db.add(permission)
    await db.flush()
    await db.refresh(permission)

    return PermissionResponse(
        id=str(permission.id),
        resource=permission.resource,
        action=permission.action,
        description=permission.description,
        created_at=permission.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints — User Role Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    summary="Get user roles (admin only)",
)
async def get_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("users", "read")),  # noqa: B008
) -> Any:
    """Get all roles assigned to a specific user."""
    from api.auth import User

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    db_user = user_result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get user's role assignments
    role_stmt = select(UserRole).where(UserRole.user_id == user_id)
    role_result = await db.execute(role_stmt)
    user_roles = role_result.scalars().all()

    role_responses = []
    for ur in user_roles:
        role = await _get_role_by_id(db, ur.role_id)
        role_responses.append(await _build_role_response(db, role))

    return UserRoleResponse(
        user_id=user_id,
        roles=role_responses,
    )


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign roles to a user (admin only)",
)
async def assign_user_roles(
    user_id: str,
    body: UserRoleAssignRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("users", "manage")),  # noqa: B008
) -> Any:
    """Assign one or more roles to a user."""
    from api.auth import User

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    db_user = user_result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify all roles exist
    for role_id in body.role_ids:
        await _get_role_by_id(db, role_id)

    # Remove existing role assignments
    await db.execute(
        UserRole.__table__.delete().where(UserRole.user_id == user_id)
    )

    # Assign new roles
    for role_id in body.role_ids:
        user_role = UserRole(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role_id=role_id,
            assigned_by=user.user_id,
        )
        db.add(user_role)

    await db.flush()

    # Return updated roles
    return await get_user_roles(user_id, db, user)


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a role from a user (admin only)",
)
async def remove_user_role(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    user: CurrentUser = Depends(require_permission("users", "manage")),  # noqa: B008
) -> dict[str, str]:
    """Remove a specific role from a user."""
    from api.auth import User

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    db_user = user_result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify role exists
    await _get_role_by_id(db, role_id)

    # Remove the assignment
    result = await db.execute(
        UserRole.__table__.delete().where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    await db.flush()
    return {"message": "Role removed from user successfully"}
