"""
AutoCAD Connector Package
=========================
Provides the AutoCAD .NET API integration layer for the Engineering Copilot.

Architecture:
  Python service (FastAPI) ↔ C# AutoCAD Plugin (via named pipes / REST)
  The C# plugin runs inside AutoCAD, exposing operations via HTTP.
  The Python service orchestrates calls and translates to the Unified Model.
"""

from autodesk_connector.autocad.connector import (
    AutoCADConnector,
    AutoCADDrawingOperation,
    AutoCADEntityType,
    AutoCADPluginClient,
)
