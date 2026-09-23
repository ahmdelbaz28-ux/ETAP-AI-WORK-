/**
 * scripts/check_bundle_size.js
 * Verifies production UI bundle size (raw + gzip) against documented 5MB baseline.
 * Does NOT implicitly trigger build; fails closed if build artifacts are missing.
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '..');
const UI_DIST_DIR = path.join(ROOT_DIR, 'ui', 'dist');
const ASSETS_DIR = path.join(UI_DIST_DIR, 'assets');
const MAX_BUNDLE_SIZE_MB = 5.0;

function checkBundleSize() {
  if (!fs.existsSync(ASSETS_DIR)) {
    console.error('❌ Error: UI dist/assets does not exist. A prior build step (build-ui) is required.');
    process.exit(1);
  }

  const files = fs.readdirSync(ASSETS_DIR);
  let totalRawBytes = 0;
  let totalGzipBytes = 0;
  const assetItems = [];

  for (const file of files) {
    if (file.endsWith('.js') || file.endsWith('.css')) {
      const filePath = path.join(ASSETS_DIR, file);
      const content = fs.readFileSync(filePath);
      const rawSize = content.length;
      const gzipSize = zlib.gzipSync(content).length;

      totalRawBytes += rawSize;
      totalGzipBytes += gzipSize;

      assetItems.push({
        file,
        type: file.endsWith('.js') ? 'JS' : 'CSS',
        rawKB: (rawSize / 1024).toFixed(2),
        gzipKB: (gzipSize / 1024).toFixed(2),
        gzipBytes: gzipSize,
      });
    }
  }

  if (assetItems.length === 0) {
    console.error('❌ Error: No JS or CSS assets found in dist/assets.');
    process.exit(1);
  }

  const totalRawMB = (totalRawBytes / (1024 * 1024)).toFixed(2);
  const totalGzipMB = (totalGzipBytes / (1024 * 1024)).toFixed(2);

  console.log('\n========================================');
  console.log('📊 Production UI Bundle Size Summary');
  console.log('========================================');
  console.log(`Assets scanned:       ${assetItems.length} files (JS & CSS)`);
  console.log(`Total Raw Size:       ${totalRawMB} MB`);
  console.log(`Total Gzip Size:      ${totalGzipMB} MB`);
  console.log(`Configured Threshold: ${MAX_BUNDLE_SIZE_MB} MB (Gzip)`);
  console.log('========================================\n');

  // Sort and print top 5 largest assets by gzip size
  assetItems.sort((a, b) => b.gzipBytes - a.gzipBytes);
  console.log('Top production assets by gzip size:');
  for (const item of assetItems.slice(0, 5)) {
    console.log(`  - [${item.type}] ${item.file}: ${item.gzipKB} KB gzip (${item.rawKB} KB raw)`);
  }

  if (totalGzipBytes > MAX_BUNDLE_SIZE_MB * 1024 * 1024) {
    console.error(`\n❌ BLOCKED: Gzip bundle size ${totalGzipMB} MB exceeds threshold of ${MAX_BUNDLE_SIZE_MB} MB.`);
    process.exit(1);
  }

  console.log(`\n✅ Bundle size verification PASSED: ${totalGzipMB} MB <= ${MAX_BUNDLE_SIZE_MB} MB\n`);
}

checkBundleSize();
