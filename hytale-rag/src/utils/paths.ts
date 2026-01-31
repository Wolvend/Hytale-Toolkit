import * as fs from "fs";
import { resolve } from "path";

/**
 * Format a code file path for display.
 * If the user has decompiled code locally (via HYTALE_DECOMPILED_DIR env var),
 * returns the full path to their local file. Otherwise returns the relative path.
 */
export function resolveCodePath(relativePath: string): string {
  const decompDir = process.env.HYTALE_DECOMPILED_DIR;
  if (decompDir) {
    const fullPath = resolve(decompDir, relativePath);
    if (fs.existsSync(fullPath)) {
      return fullPath;
    }
  }
  // Fallback to relative path (user doesn't have local decompiled code)
  return relativePath;
}

/**
 * Format a Client UI file path for display.
 * If the user has client data locally (via HYTALE_CLIENT_DATA_DIR env var),
 * returns the full path to their local file. Otherwise returns the relative path.
 */
export function resolveClientDataPath(relativePath: string): string {
  const clientDir = process.env.HYTALE_CLIENT_DATA_DIR;
  if (clientDir) {
    const fullPath = resolve(clientDir, relativePath);
    if (fs.existsSync(fullPath)) {
      return fullPath;
    }
  }
  return relativePath;
}

/**
 * Format a Game Data file path for display.
 * If the user has extracted assets locally (via HYTALE_ASSETS_DIR env var),
 * returns the full path. Otherwise indicates the file is inside Assets.zip.
 */
export function resolveGameDataPath(relativePath: string): string {
  const assetsDir = process.env.HYTALE_ASSETS_DIR;
  if (assetsDir) {
    const fullPath = resolve(assetsDir, relativePath);
    if (fs.existsSync(fullPath)) {
      return fullPath;
    }
  }
  return `Assets.zip//${relativePath}`;
}
