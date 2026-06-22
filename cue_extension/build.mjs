import * as esbuild from 'esbuild';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distRoot = path.join(__dirname, 'dist');

const sharedOptions = {
  bundle: true,
  target: 'es2022',
  platform: 'browser',
  sourcemap: 'inline',
  logLevel: 'info',
};

async function clean(distDir) {
  await fs.rm(distDir, { recursive: true, force: true });
  await fs.mkdir(distDir, { recursive: true });
}

async function bundle(distDir) {
  // Popup runs as an ES module from popup.html.
  await esbuild.build({
    ...sharedOptions,
    entryPoints: { popup: 'src/popup/popup.ts' },
    format: 'esm',
    outdir: distDir,
  });
  // Content scripts injected via scripting.executeScript run as classic
  // scripts and cannot use ESM imports — bundle as IIFE.
  await esbuild.build({
    ...sharedOptions,
    entryPoints: { content: 'src/content/inject.ts' },
    format: 'iife',
    outdir: distDir,
  });
  // MV3 background service worker supports ESM when manifest declares it.
  await esbuild.build({
    ...sharedOptions,
    entryPoints: { sw: 'src/background/sw.ts' },
    format: 'esm',
    outdir: distDir,
  });
}

async function copyStatic(distDir) {
  const files = [
    ['manifest.json', 'manifest.json'],
    ['src/popup/popup.html', 'popup.html'],
    ['src/popup/popup.css', 'popup.css'],
  ];
  for (const [src, dest] of files) {
    await fs.copyFile(path.join(__dirname, src), path.join(distDir, dest));
  }
}

async function buildTarget(target) {
  const distDir = path.join(distRoot, target);
  await clean(distDir);
  await bundle(distDir);
  await copyStatic(distDir);
  console.log(`Built ${target} bundle → ${distDir}`);
}

const target = process.env.CUE_EXT_TARGET ?? 'chrome';
const targets = target === 'all' ? ['chrome', 'firefox'] : [target];
for (const t of targets) {
  await buildTarget(t);
}
