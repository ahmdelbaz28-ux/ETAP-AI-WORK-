#!/usr/bin/env node
// =============================================================================
// Bundle Size Checker
// Replaces the vulnerable `bundlesize` package with a simple, secure alternative
// =============================================================================

import { stat } from 'node:fs/promises';
import { resolve } from 'node:path';

const BUNDLE_PATH = resolve('dist/index.js');
const MAX_SIZE_KB = 50;

async function checkBundleSize() {
  try {
    const stats = await stat(BUNDLE_PATH);
    const sizeKB = stats.size / 1024;
    const sizeMB = stats.size / (1024 * 1024);

    console.log(`Bundle: ${BUNDLE_PATH}`);
    console.log(`Size:   ${sizeKB.toFixed(1)} KB (${sizeMB.toFixed(3)} MB)`);
    console.log(`Limit:  ${MAX_SIZE_KB} KB`);

    if (sizeKB > MAX_SIZE_KB) {
      console.error(`\n❌ FAIL: Bundle size ${sizeKB.toFixed(1)} KB exceeds limit ${MAX_SIZE_KB} KB`);
      process.exit(1);
    } else {
      console.log(`\n✅ PASS: Bundle size ${sizeKB.toFixed(1)} KB is within limit ${MAX_SIZE_KB} KB`);
      process.exit(0);
    }
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.error(`\n❌ ERROR: Bundle not found at ${BUNDLE_PATH}`);
      console.error('Run `npm run build` first.');
      process.exit(2);
    } else {
      console.error('Error checking bundle size:', error.message);
      process.exit(2);
    }
  }
}

checkBundleSize();
