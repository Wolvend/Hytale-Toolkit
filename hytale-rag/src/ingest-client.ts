#!/usr/bin/env node
/**
 * Ingest Hytale Client UI files into LanceDB.
 *
 * Parses client UI files (.xaml, .ui, .json) from the Client/Data directory,
 * generates embeddings, and stores them in the hytale_client_ui table.
 *
 * Usage: npm run ingest-client [client-data-path] [db-path]
 */

import { parseClientUIDirectory, getClientUIStats } from "./client-ui-parser.js";
import { embedClientUIChunks, type EmbeddedClientUIChunk } from "./embedder.js";
import { createClientUITable } from "./db.js";
import * as path from "path";
import * as fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default paths - update these to match your setup
const DEFAULT_CLIENT_DATA = "D:/Roaming/install/release/package/game/latest/Client/Data";
const DEFAULT_DB_PATH = path.resolve(__dirname, "..", "data", "lancedb");
const TABLE_NAME = "hytale_client_ui";

async function main() {
  const clientDataPath = process.argv[2] || DEFAULT_CLIENT_DATA;
  const dbPath = process.argv[3] || DEFAULT_DB_PATH;

  const apiKey = process.env.VOYAGE_API_KEY;
  if (!apiKey) {
    console.error("Error: VOYAGE_API_KEY environment variable is required");
    process.exit(1);
  }

  console.log("=== Hytale Client UI Ingestion ===");
  console.log("");
  console.log(`Client Data path: ${clientDataPath}`);
  console.log(`Database path: ${dbPath}`);
  console.log(`Table name: ${TABLE_NAME}`);
  console.log("");

  // Check if source directory exists
  if (!fs.existsSync(clientDataPath)) {
    console.error(`Error: Client Data directory not found: ${clientDataPath}`);
    console.error("");
    console.error("Provide the path to your Hytale Client/Data folder:");
    console.error("  npm run ingest-client <path-to-hytale>/Client/Data");
    process.exit(1);
  }

  // Ensure db directory exists
  fs.mkdirSync(dbPath, { recursive: true });

  // Show stats preview
  console.log("Scanning Client/Data directory...");
  const stats = await getClientUIStats(clientDataPath);
  console.log(`  Total files: ${stats.totalFiles}`);
  console.log(`  XAML files: ${stats.xamlFiles}`);
  console.log(`  .ui files: ${stats.uiFiles}`);
  console.log(`  JSON files: ${stats.jsonFiles}`);
  console.log("");
  console.log("Files by category:");
  for (const [category, count] of Object.entries(stats.byCategory).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${category}: ${count}`);
  }
  console.log("");

  // Step 1: Parse UI files
  console.log("Step 1: Parsing client UI files...");
  const startParse = Date.now();

  const { chunks, errors } = await parseClientUIDirectory(clientDataPath, (current, total, file) => {
    if (current % 50 === 0 || current === total) {
      process.stdout.write(`\r  Parsed ${current}/${total} files`);
    }
  });
  console.log("");

  const parseTime = ((Date.now() - startParse) / 1000).toFixed(1);
  console.log(`  Parsed ${chunks.length} UI files`);
  console.log(`  Parse time: ${parseTime}s`);

  if (errors.length > 0) {
    console.log(`  Errors: ${errors.length}`);
    const errorFile = path.join(dbPath, "client_ui_parse_errors.txt");
    fs.writeFileSync(errorFile, errors.join("\n"));
    console.log(`  Error log: ${errorFile}`);
  }
  console.log("");

  if (chunks.length === 0) {
    console.error("No UI files found to embed. Check the Client/Data path.");
    process.exit(1);
  }

  // Step 2: Embed chunks
  console.log("Step 2: Embedding UI files with Voyage AI (voyage-3)...");
  const startEmbed = Date.now();

  let embeddedChunks: EmbeddedClientUIChunk[];
  try {
    embeddedChunks = await embedClientUIChunks(chunks, apiKey, (current, total) => {
      process.stdout.write(`\r  Embedded ${current}/${total} files`);
    });
    console.log("");
  } catch (e: any) {
    console.error(`\nEmbedding failed: ${e.message}`);
    process.exit(1);
  }

  const embedTime = ((Date.now() - startEmbed) / 1000).toFixed(1);
  console.log(`  Embed time: ${embedTime}s`);
  console.log("");

  // Step 3: Store in LanceDB
  console.log(`Step 3: Storing in LanceDB (${TABLE_NAME} table)...`);
  const startStore = Date.now();

  try {
    await createClientUITable(dbPath, embeddedChunks, TABLE_NAME);
  } catch (e: any) {
    console.error(`Storage failed: ${e.message}`);
    process.exit(1);
  }

  const storeTime = ((Date.now() - startStore) / 1000).toFixed(1);
  console.log(`  Store time: ${storeTime}s`);
  console.log("");

  // Summary
  const totalTime = ((Date.now() - startParse) / 1000).toFixed(1);
  console.log("=== Client UI Ingestion Complete ===");
  console.log(`Total UI files indexed: ${embeddedChunks.length}`);
  console.log(`Total time: ${totalTime}s`);
  console.log(`Database location: ${dbPath}`);
  console.log("");
  console.log("You can now use the search_hytale_client_ui MCP tool to query client UI.");
}

main().catch((e) => {
  console.error("Fatal error:", e);
  process.exit(1);
});
