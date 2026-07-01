"""
Supabase Integration for AhmedETAP
Provides PostgreSQL database access, authentication, and real-time subscriptions.

Usage:
    from integrations.supabase_integration import supabase_client, get_supabase_db

    # Direct client usage
    result = supabase_client.table('projects').select('*').execute()

    # Or via database helper
    db = get_supabase_db()
    projects = db.get_projects()
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Supabase SDK (optional dependency) ─────────────────────────────────────
try:
    from supabase import create_client, Client

    SUPABASE_AVAILABLE = True
    logger.debug("Supabase SDK loaded successfully")
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase SDK not installed. Run: pip install supabase")


class SupabaseClient:
    """
    Central Supabase client wrapper for AhmedETAP.
    Provides PostgreSQL database access, auth, and real-time features.
    """

    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        self.secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        self.enabled = bool(self.url and self.publishable_key and SUPABASE_AVAILABLE)

        if self.enabled:
            self.client: Client = create_client(
                self.url,
                self.publishable_key,
            )
            logger.info(f"✅ Supabase initialized — URL: {self.url}")
        else:
            self.client = None
            if not self.url:
                logger.info("Supabase disabled: SUPABASE_URL not set")
            elif not self.publishable_key:
                logger.info("Supabase disabled: SUPABASE_PUBLISHABLE_KEY not set")
            elif not SUPABASE_AVAILABLE:
                logger.info("Supabase disabled: SDK not installed")

    def get_table(self, table_name: str) -> Any:
        """Get a Supabase table reference."""
        if not self.enabled or not self.client:
            raise RuntimeError("Supabase is not enabled")
        return self.client.table(table_name)

    def insert(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a row into a table."""
        if not self.enabled or not self.client:
            return {"error": "Supabase is not enabled", "data": None}
        try:
            result = self.client.table(table_name).insert(data).execute()
            return {"success": True, "data": result.data, "error": None}
        except Exception as e:
            logger.error(f"Supabase insert error: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def select(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Select rows from a table with optional filters."""
        if not self.enabled or not self.client:
            return {"error": "Supabase is not enabled", "data": []}
        try:
            query = self.client.table(table_name).select("*")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.execute()
            return {"success": True, "data": result.data, "error": None}
        except Exception as e:
            logger.error(f"Supabase select error: {e}")
            return {"success": False, "data": [], "error": str(e)}

    def update(self, table_name: str, data: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Update rows in a table."""
        if not self.enabled or not self.client:
            return {"error": "Supabase is not enabled", "data": None}
        try:
            query = self.client.table(table_name).update(data)
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            return {"success": True, "data": result.data, "error": None}
        except Exception as e:
            logger.error(f"Supabase update error: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def delete(self, table_name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Delete rows from a table."""
        if not self.enabled or not self.client:
            return {"error": "Supabase is not enabled", "data": None}
        try:
            query = self.client.table(table_name).delete()
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.execute()
            return {"success": True, "data": result.data, "error": None}
        except Exception as e:
            logger.error(f"Supabase delete error: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def health_check(self) -> Dict[str, Any]:
        """Return Supabase integration status."""
        return {
            "enabled": self.enabled,
            "url": self.url,
            "sdk_available": SUPABASE_AVAILABLE,
            "client_initialized": self.client is not None,
        }


# ─── Module-level singleton ───────────────────────────────────────────────────
supabase_client = SupabaseClient()


def get_supabase_db() -> SupabaseClient:
    """Get the Supabase client instance."""
    return supabase_client


# ─── Database helpers for common operations ──────────────────────────────────

class SupabaseDB:
    """High-level database operations for AhmedETAP."""

    def __init__(self, client: SupabaseClient):
        self.client = client

    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        result = self.client.select("projects")
        return result.get("data", [])

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project by ID."""
        result = self.client.select("projects", {"id": project_id})
        data = result.get("data", [])
        return data[0] if data else None

    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project."""
        return self.client.insert("projects", project_data)

    def get_studies(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all studies, optionally filtered by project."""
        filters = {"project_id": project_id} if project_id else None
        result = self.client.select("studies", filters)
        return result.get("data", [])

    def create_study(self, study_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new study."""
        return self.client.insert("studies", study_data)

    def get_agents(self) -> List[Dict[str, Any]]:
        """Get all agents."""
        result = self.client.select("agents")
        return result.get("data", [])

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent by ID."""
        result = self.client.select("agents", {"id": agent_id})
        data = result.get("data", [])
        return data[0] if data else None


def get_supabase_db_helper() -> SupabaseDB:
    """Get a SupabaseDB helper instance."""
    return SupabaseDB(supabase_client)