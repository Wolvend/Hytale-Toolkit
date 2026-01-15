/**
 * Database - CLI helper for LanceDB operations
 *
 * Provides standalone database functions for the ingest scripts.
 */

import * as lancedb from "@lancedb/lancedb";
import type { EmbeddedChunk, EmbeddedClientUIChunk } from "./embedder.js";
import type { EmbeddedGameDataChunk } from "./types.js";

/**
 * Search result from the database
 */
export interface SearchResult {
  id: string;
  className: string;
  packageName: string;
  methodName: string;
  methodSignature: string;
  content: string;
  filePath: string;
  lineStart: number;
  lineEnd: number;
  score: number;
}

/**
 * Database statistics
 */
export interface DbStats {
  totalMethods: number;
  uniqueClasses: number;
  uniquePackages: number;
}

/**
 * Create or replace the hytale_methods table with embedded chunks
 */
export async function createTable(
  dbPath: string,
  chunks: EmbeddedChunk[],
  tableName: string = "hytale_methods"
): Promise<void> {
  const db = await lancedb.connect(dbPath);

  // Prepare data for LanceDB (convert arrays to JSON strings)
  const data = chunks.map((chunk) => ({
    id: chunk.id,
    className: chunk.className,
    packageName: chunk.packageName,
    methodName: chunk.methodName,
    methodSignature: chunk.methodSignature,
    content: chunk.content,
    filePath: chunk.filePath,
    lineStart: chunk.lineStart,
    lineEnd: chunk.lineEnd,
    imports: JSON.stringify(chunk.imports),
    fields: JSON.stringify(chunk.fields),
    classJavadoc: chunk.classJavadoc || "",
    methodJavadoc: chunk.methodJavadoc || "",
    vector: chunk.vector,
  }));

  // Drop existing table if it exists
  try {
    await db.dropTable(tableName);
  } catch {
    // Table doesn't exist, that's fine
  }

  // Create new table
  await db.createTable(tableName, data);
  console.log(`  Created table '${tableName}' with ${data.length} rows`);
}

/**
 * Create or replace the hytale_gamedata table with embedded chunks
 */
export async function createGameDataTable(
  dbPath: string,
  chunks: EmbeddedGameDataChunk[],
  tableName: string = "hytale_gamedata"
): Promise<void> {
  const db = await lancedb.connect(dbPath);

  // Prepare data for LanceDB
  const data = chunks.map((chunk) => ({
    id: chunk.id,
    type: chunk.type,
    name: chunk.name,
    filePath: chunk.filePath,
    rawJson: chunk.rawJson,
    category: chunk.category || "",
    tags: JSON.stringify(chunk.tags || []),
    parentId: chunk.parentId || "",
    relatedIds: JSON.stringify(chunk.relatedIds || []),
    textForEmbedding: chunk.textForEmbedding,
    vector: chunk.vector,
  }));

  // Drop existing table if it exists
  try {
    await db.dropTable(tableName);
  } catch {
    // Table doesn't exist, that's fine
  }

  // Create new table
  await db.createTable(tableName, data);
  console.log(`  Created table '${tableName}' with ${data.length} rows`);
}

/**
 * Search the code table using a query vector
 */
export async function search(
  dbPath: string,
  queryVector: number[],
  limit: number = 5,
  filter?: string,
  tableName: string = "hytale_methods"
): Promise<SearchResult[]> {
  const db = await lancedb.connect(dbPath);
  const table = await db.openTable(tableName);

  let query = table.vectorSearch(queryVector).limit(limit);

  if (filter) {
    query = query.where(filter);
  }

  const results = await query.toArray();

  return results.map((row: any) => ({
    id: row.id,
    className: row.className,
    packageName: row.packageName,
    methodName: row.methodName,
    methodSignature: row.methodSignature,
    content: row.content,
    filePath: row.filePath,
    lineStart: row.lineStart,
    lineEnd: row.lineEnd,
    score: 1 - (row._distance || 0), // Convert distance to similarity score
  }));
}

/**
 * Get database statistics
 */
export async function getStats(
  dbPath: string,
  tableName: string = "hytale_methods"
): Promise<DbStats> {
  const db = await lancedb.connect(dbPath);
  const table = await db.openTable(tableName);

  const rowCount = await table.countRows();

  // Query all rows to count unique classes and packages
  const classNames = new Set<string>();
  const packageNames = new Set<string>();

  const batchSize = 5000;
  let offset = 0;

  while (true) {
    const batch = await table.query().limit(batchSize).offset(offset).toArray();
    if (batch.length === 0) break;

    for (const row of batch as any[]) {
      if (row.className) classNames.add(row.className);
      if (row.packageName) packageNames.add(row.packageName);
    }

    offset += batch.length;
    if (batch.length < batchSize) break;
  }

  return {
    totalMethods: rowCount,
    uniqueClasses: classNames.size,
    uniquePackages: packageNames.size,
  };
}

/**
 * Create or replace the client UI table with embedded chunks
 */
export async function createClientUITable(
  dbPath: string,
  chunks: EmbeddedClientUIChunk[],
  tableName: string = "hytale_client_ui"
): Promise<void> {
  const db = await lancedb.connect(dbPath);

  // Prepare data for LanceDB
  const data = chunks.map((chunk) => ({
    id: chunk.id,
    type: chunk.type,
    name: chunk.name,
    filePath: chunk.filePath,
    relativePath: chunk.relativePath,
    content: chunk.content,
    category: chunk.category || "",
    textForEmbedding: chunk.textForEmbedding,
    vector: chunk.vector,
  }));

  // Drop existing table if it exists
  try {
    await db.dropTable(tableName);
  } catch {
    // Table doesn't exist, that's fine
  }

  // Create new table
  await db.createTable(tableName, data);
  console.log(`  Created table '${tableName}' with ${data.length} rows`);
}
