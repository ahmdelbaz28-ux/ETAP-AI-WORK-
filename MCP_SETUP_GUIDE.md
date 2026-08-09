# 🤖 MCP (Model Context Protocol) Setup Guide

This guide explains how to set up the MCP servers for the AhmedETAP project, including TestSprite, LangWatch, and Mastra.

---

## ✅ Currently Configured MCP Servers

Your `.mcp.json` has been set up with:

| MCP Server | Purpose | Status |
|------------|---------|--------|
| **TestSprite** | AI-powered testing platform | ✅ Configured |
| **LangWatch** | LLM observability & monitoring | ✅ Configured |
| **Mastra** | Documentation server | ✅ Configured |

---

## 📁 Files Included

| File | Description |
|------|-------------|
| `.mcp.json` | Main MCP configuration (**DO NOT COMMIT TO GIT**) |
| `.mcp.json.example` | Example configuration template |
| `mcp_server_intelligent_index_system.json` | Advanced MCP system design |
| `MCP_SETUP_GUIDE.md` | This guide |

---

## 🚀 How to Use in Your IDE

### Cursor / Windsurf / VS Code with MCP Extensions:

1. **Install the MCP Extension**
   - For Cursor: Built-in support
   - For VS Code: Install "Model Context Protocol" extension

2. **Place `.mcp.json` in Your Project Root**
   - The file is already created at `/.mcp.json`

3. **Restart Your IDE**
   - The MCP servers should be detected automatically

---

## 📋 Available MCP Tools

### TestSprite
- AI-powered test generation
- Test execution and reporting
- Code quality analysis

### LangWatch
- LLM call tracking
- Cost monitoring
- Performance analytics

### Mastra
- Documentation search
- Code snippet retrieval
- Project knowledge base

---

## 🔒 Security Note

- `.mcp.json` contains API keys and is **already in `.gitignore`**
- Never commit `.mcp.json` to git
- Use `.mcp.json.example` as a template for your team

---

## ✅ Verification

To verify MCP is working:
1. Open your IDE's MCP panel
2. Check that all 3 servers show as "Connected"
3. Try using a tool like TestSprite's test generator

---

## 📚 More Information

- [MCP Official Docs](https://modelcontextprotocol.io/)
- [TestSprite MCP](https://testsprite.ai/)
- [LangWatch](https://langwatch.ai/)
- [Mastra](https://mastra.ai/)
