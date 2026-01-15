/**
 * Embedder - CLI helper for embedding code and game data
 *
 * Provides standalone embedding functions for the ingest scripts.
 * Uses the Voyage AI provider under the hood.
 */

import { VoyageEmbeddingProvider } from "./providers/embedding/voyage.js";
import type { MethodChunk } from "./parser.js";
import type { GameDataChunk, EmbeddedGameDataChunk } from "./types.js";
import type { ClientUIChunk } from "./client-ui-parser.js";

/**
 * Embedded chunk with vector
 */
export interface EmbeddedChunk extends MethodChunk {
  vector: number[];
}

/**
 * Build embedding text for a method chunk
 */
function buildMethodEmbeddingText(chunk: MethodChunk): string {
  const parts = [
    `// Package: ${chunk.packageName}`,
    `// Class: ${chunk.className}`,
    `// Method: ${chunk.methodName}`,
    "",
    chunk.methodSignature,
    "",
    chunk.content,
  ];
  return parts.join("\n");
}

/**
 * Embed code chunks using Voyage AI
 */
export async function embedChunks(
  chunks: MethodChunk[],
  apiKey: string,
  onProgress?: (current: number, total: number) => void
): Promise<EmbeddedChunk[]> {
  const provider = new VoyageEmbeddingProvider({
    type: "voyage",
    apiKey,
    batchSize: 128,
    rateLimitMs: 100,
  });

  // Build texts for embedding
  const texts = chunks.map(buildMethodEmbeddingText);

  // Embed all texts
  const result = await provider.embedBatch(
    texts,
    { purpose: "code", mode: "document" },
    onProgress
  );

  // Combine chunks with vectors
  return chunks.map((chunk, i) => ({
    ...chunk,
    vector: result.vectors[i],
  }));
}

/**
 * Build embedding text for a game data chunk
 */
function buildGameDataEmbeddingText(chunk: GameDataChunk): string {
  // Use the pre-built textForEmbedding field if available
  if (chunk.textForEmbedding) {
    return chunk.textForEmbedding;
  }

  // Fallback to building from fields
  const parts = [
    `Type: ${chunk.type}`,
    `ID: ${chunk.id}`,
    `Path: ${chunk.filePath}`,
  ];

  if (chunk.name) {
    parts.push(`Name: ${chunk.name}`);
  }

  if (chunk.tags && chunk.tags.length > 0) {
    parts.push(`Tags: ${chunk.tags.join(", ")}`);
  }

  if (chunk.relatedIds && chunk.relatedIds.length > 0) {
    parts.push(`Related: ${chunk.relatedIds.join(", ")}`);
  }

  parts.push("");
  parts.push("Data:");
  parts.push(chunk.rawJson);

  return parts.join("\n");
}

/**
 * Embed game data chunks using Voyage AI
 */
export async function embedGameDataChunks(
  chunks: GameDataChunk[],
  apiKey: string,
  onProgress?: (current: number, total: number) => void
): Promise<EmbeddedGameDataChunk[]> {
  const provider = new VoyageEmbeddingProvider({
    type: "voyage",
    apiKey,
    batchSize: 128,
    rateLimitMs: 100,
  });

  // Build texts for embedding
  const texts = chunks.map(buildGameDataEmbeddingText);

  // Embed all texts
  const result = await provider.embedBatch(
    texts,
    { purpose: "text", mode: "document" },
    onProgress
  );

  // Combine chunks with vectors
  return chunks.map((chunk, i) => ({
    ...chunk,
    vector: result.vectors[i],
  }));
}

/**
 * Embedded client UI chunk with vector
 */
export interface EmbeddedClientUIChunk extends ClientUIChunk {
  vector: number[];
}

/**
 * Embed client UI chunks using Voyage AI
 */
export async function embedClientUIChunks(
  chunks: ClientUIChunk[],
  apiKey: string,
  onProgress?: (current: number, total: number) => void
): Promise<EmbeddedClientUIChunk[]> {
  const provider = new VoyageEmbeddingProvider({
    type: "voyage",
    apiKey,
    batchSize: 128,
    rateLimitMs: 100,
  });

  // Use the pre-built textForEmbedding field
  const texts = chunks.map((chunk) => chunk.textForEmbedding);

  // Embed all texts (use "text" purpose since this is markup/config, not code)
  const result = await provider.embedBatch(
    texts,
    { purpose: "text", mode: "document" },
    onProgress
  );

  // Combine chunks with vectors
  return chunks.map((chunk, i) => ({
    ...chunk,
    vector: result.vectors[i],
  }));
}

/**
 * Embed a single query
 */
export async function embedQuery(query: string, apiKey: string): Promise<number[]> {
  const provider = new VoyageEmbeddingProvider({
    type: "voyage",
    apiKey,
  });

  return provider.embedQuery(query, "code");
}
