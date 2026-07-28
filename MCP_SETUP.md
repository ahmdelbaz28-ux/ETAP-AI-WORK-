# MCP (Model Context Protocol) Setup Guide

This guide explains how to properly install and test MCP servers for the ETAP-AI Engineering Platform.

## What is MCP?

Model Context Protocol (MCP) is a standard for connecting AI models with tools and data sources. It allows AI assistants to access external systems like documentation, APIs, and databases during conversations.

## Current MCP Configuration

The project includes a configuration file [`.mcp.json`](file:///c:/Users/Repair%20SC/Desktop/test/ahmedetap-hf/.mcp.json) that defines available MCP servers:

```json
{
  "mcpServers": {
    "TestSprite": {
      "command": "npx",
      "args": [
        "-y",
        "@testsprite/testsprite-mcp@latest"
      ],
      "env": {
        "API_KEY": "REDACTED_TESTSPRITE_KEY"
      }
    }
  }
}
```

## How to Install and Test MCP in VS Code

### Method 1: Using Cursor (Recommended)

If you're using Cursor (AI-powered code editor), MCP servers are automatically detected and started when you open the project.

1. Open the project in Cursor
2. The TestSprite MCP server will start automatically
3. You can then interact with the AI assistant which will have access to TestSprite functionality

### Method 2: Manual Installation

1. Install the MCP server globally:
   ```bash
   npm install -g @testsprite/testsprite-mcp
   ```

2. Or run it directly with npx:
   ```bash
   npx @testsprite/testsprite-mcp@latest
   ```

### Method 3: Using VS Code Settings

Add the MCP configuration to your VS Code `settings.json`:

```json
{
  "mcpServers": {
    "TestSprite": {
      "command": "npx",
      "args": [
        "-y",
        "@testsprite/testsprite-mcp@latest"
      ],
      "env": {
        "API_KEY": "REDACTED_TESTSPRITE_KEY"
      }
    }
  }
}
```

## Testing the Configuration

To test if MCP is working properly:

1. Start your development environment (Cursor or VS Code with MCP extension)
2. Verify that the MCP server starts without errors
3. Use an AI assistant that supports MCP and verify it can access the TestSprite functionality

## Troubleshooting

- If you see "command not found" errors, ensure Node.js and npm are properly installed
- If API keys are rejected, verify they are correctly formatted in the configuration
- Some MCP servers may require additional dependencies or permissions to run

## Security Note

⚠️ **Important**: The API key in this configuration is exposed in plain text. For production use, consider using environment variables or secure credential management systems instead of hardcoding API keys.