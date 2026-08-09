const fs = require('node:fs');
const path = require('node:path');

// Test script to validate MCP configuration
console.log('Testing MCP configuration...');

try {
  // Read the .mcp.json file
  const mcpConfigPath = path.join(__dirname, '.mcp.json');
  const mcpConfigRaw = fs.readFileSync(mcpConfigPath, 'utf8');
  const mcpConfig = JSON.parse(mcpConfigRaw);

  console.log('✓ MCP configuration file found and parsed successfully');
  console.log('Configuration:', JSON.stringify(mcpConfig, null, 2));

  // Validate structure
  if (!mcpConfig.mcpServers) {
    throw new Error('Missing mcpServers property in configuration');
  }

  // Check for TestSprite server
  if (!mcpConfig.mcpServers.TestSprite) {
    throw new Error('Missing TestSprite server configuration');
  }

  const testSpriteConfig = mcpConfig.mcpServers.TestSprite;
  console.log('\n✓ TestSprite server configuration found:');
  console.log('- Command:', testSpriteConfig.command);
  console.log('- Args:', testSpriteConfig.args);
  console.log('- Has API_KEY env var:', !!testSpriteConfig.env?.API_KEY);

  console.log('\n✓ MCP configuration is valid!');
} catch (error) {
  console.error('✗ MCP configuration validation failed:', error.message);
  process.exit(1);
}
