"""
Revit Connector Package
=======================
Provides the Revit API integration layer for the Engineering Copilot.

Architecture:
  Python service (FastAPI) ↔ C# Revit Plugin (via REST API)
  The C# plugin runs inside Revit, exposing BIM operations via HTTP.
  The Python service orchestrates calls and translates to the Unified Model.
"""

from autodesk_connector.revit.connector import (
    RevitConnector,
    RevitElementType,
    RevitPluginClient,
)
