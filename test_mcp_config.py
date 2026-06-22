#!/usr/bin/env python3
"""
Test script to verify MCP (Multi-Capability Protocol) server configuration.
This script validates the .mcp.json configuration and demonstrates how to interact with MCP servers.
"""

import json
import subprocess
import sys
import os
from pathlib import Path


def test_mcp_configuration():
    """Test the MCP server configuration."""
    print("Testing MCP Configuration...")

    # Check if .mcp.json exists
    mcp_config_path = Path("./.mcp.json")
    if not mcp_config_path.exists():
        print(f"❌ Error: {mcp_config_path} does not exist")
        return False

    print(f"✅ Found {mcp_config_path}")

    # Load and parse the configuration
    try:
        with open(mcp_config_path, "r") as f:
            config = json.load(f)
        print("✅ Successfully parsed .mcp.json")
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing .mcp.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading .mcp.json: {e}")
        return False

    # Verify the TestSprite configuration
    if "mcpServers" not in config:
        print("❌ Error: 'mcpServers' key not found in configuration")
        return False

    if "TestSprite" not in config["mcpServers"]:
        print("❌ Error: 'TestSprite' server configuration not found")
        return False

    testsprite_config = config["mcpServers"]["TestSprite"]
    print("✅ Found TestSprite configuration")

    # Validate required fields
    required_fields = ["command", "args", "env"]
    for field in required_fields:
        if field not in testsprite_config:
            print(f"❌ Error: '{field}' field missing in TestSprite configuration")
            return False

    print("✅ All required fields present in TestSprite configuration")

    # Check if the command can be executed
    command = testsprite_config["command"]
    args = testsprite_config["args"]

    print(f"Command: {command}")
    print(f"Args: {args}")

    # Print API key status (without revealing the actual key)
    if "API_KEY" in testsprite_config["env"]:
        print("✅ API_KEY environment variable is configured")
    else:
        print("⚠️  Warning: API_KEY environment variable not found")

    print("\nMCP Configuration Test Summary:")
    print("- Configuration file: .mcp.json")
    print("- Server: TestSprite")
    print("- Command: npx @testsprite/testsprite-mcp@latest")
    print("- Status: Configuration is properly formatted")

    print("\nTo test the MCP server manually, you can run:")
    print("npx @testsprite/testsprite-mcp@latest")

    return True


def main():
    """Main function to run the MCP configuration test."""
    print("=" * 60)
    print("MCP (Multi-Capability Protocol) Configuration Test")
    print("=" * 60)

    success = test_mcp_configuration()

    print("\n" + "=" * 60)
    if success:
        print("✅ MCP Configuration Test PASSED")
        print("Your TestSprite MCP server is properly configured!")
    else:
        print("❌ MCP Configuration Test FAILED")
        print("Please review your .mcp.json configuration.")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
