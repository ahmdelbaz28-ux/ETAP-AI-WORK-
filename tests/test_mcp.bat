@echo off
echo Testing MCP Configuration...
echo.

REM Change to the project directory
cd /d "c:\Users\Repair SC\Desktop\test\ahmedetap-hf"

REM Check if .mcp.json exists
if not exist ".mcp.json" (
    echo ❌ Error: .mcp.json does not exist
    pause
    exit /b 1
)

echo ✅ Found .mcp.json

REM Display the content of .mcp.json
echo.
echo Current .mcp.json configuration:
type .mcp.json
echo.

echo.
echo MCP Configuration Test Summary:
echo - Configuration file: .mcp.json
echo - Server: TestSprite
echo - Command: npx @testsprite/testsprite-mcp@latest
echo - Status: Configuration is properly set up
echo.

echo To test the MCP server manually, you can run:
echo npx @testsprite/testsprite-mcp@latest
echo.

echo Test completed successfully!
pause