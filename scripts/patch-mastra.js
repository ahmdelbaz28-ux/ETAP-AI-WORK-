import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');

const patchSnippet = `
export const MAX_KNOWLEDGE_NODE_DESCRIPTION_LENGTH = 10000;
export const assertKnowledgeScopeWithinCeiling = () => {};
export const canonicalizeKnowledgeScope = (s) => s;
export const createKnowledgeNodeCursor = () => {};
export const expandKnowledgeScope = () => {};
export const isKnowledgeScopeVisible = () => true;
export const knowledgeScopeKey = (s) => String(s);
`;

function patchFile(filePath) {
  if (fs.existsSync(filePath)) {
    try {
      const targetPath = fs.realpathSync(filePath);
      const content = fs.readFileSync(targetPath, 'utf-8');
      if (!content.includes('MAX_KNOWLEDGE_NODE_DESCRIPTION_LENGTH')) {
        fs.appendFileSync(targetPath, patchSnippet, 'utf-8');
        console.log(`[patch-mastra] Successfully patched ${targetPath}`);
      } else {
        console.log(`[patch-mastra] Already patched ${targetPath}`);
      }
    } catch (e) {
      console.warn(`[patch-mastra] Warning while patching ${filePath}:`, e.message);
    }
  }
}

// 1. Direct path
patchFile(path.join(rootDir, 'node_modules', '@mastra', 'core', 'dist', 'storage', 'index.js'));

// 2. Scan .pnpm if present
const pnpmDir = path.join(rootDir, 'node_modules', '.pnpm');
if (fs.existsSync(pnpmDir)) {
  try {
    const entries = fs.readdirSync(pnpmDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory() && entry.name.startsWith('@mastra+core@')) {
        const candidate = path.join(pnpmDir, entry.name, 'node_modules', '@mastra', 'core', 'dist', 'storage', 'index.js');
        patchFile(candidate);
      }
    }
  } catch (err) {
    console.warn('[patch-mastra] Could not inspect .pnpm directory:', err.message);
  }
}
