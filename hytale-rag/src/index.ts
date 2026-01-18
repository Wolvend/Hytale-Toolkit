#!/usr/bin/env node
/**
 * Hytale RAG - Main Entry Point
 *
 * A semantic search system for the Hytale codebase and game data.
 * Supports multiple server modes: MCP (Claude), REST API, and OpenAI-compatible.
 */

import * as fs from "fs";
import * as path from "path";
import { loadConfig } from "./config/index.js";
import { createEmbeddingProvider } from "./providers/embedding/factory.js";
import { createVectorStore } from "./providers/vectorstore/factory.js";
import { ToolRegistry, type ToolContext } from "./core/tools/index.js";
import { searchCodeTool } from "./core/tools/search-code.js";
import { searchClientCodeTool } from "./core/tools/search-client-code.js";
import { searchGameDataTool } from "./core/tools/search-gamedata.js";
import { codeStatsTool } from "./core/tools/code-stats.js";
import { clientCodeStatsTool } from "./core/tools/client-code-stats.js";
import { gameDataStatsTool } from "./core/tools/gamedata-stats.js";
import { startMCPServer } from "./servers/mcp/index.js";
import { createRESTServer, startRESTServer } from "./servers/rest/index.js";
import { createOpenAIServer, startOpenAIServer } from "./servers/openai/index.js";

/**
 * Check .env file for common misconfigurations
 * Returns a helpful error message if issues are found
 */
function checkEnvFile(): string | undefined {
  const envPath = path.resolve(process.cwd(), ".env");

  if (!fs.existsSync(envPath)) {
    return undefined; // No .env file - will be handled by main config check
  }

  try {
    const content = fs.readFileSync(envPath, "utf-8");
    const lines = content.split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));

    // Check for common issues
    for (const line of lines) {
      // Check if someone put just the API key without the variable name
      if (line.match(/^pa-[A-Za-z0-9_-]+$/)) {
        return `.env file misconfigured: Found what looks like a Voyage API key without the variable name.\n\nYour .env file contains:\n  ${line}\n\nIt should be:\n  VOYAGE_API_KEY=${line}\n\nPlease fix your .env file and restart Claude Code.`;
      }

      // Check if someone put just "sk-" style key (OpenAI format)
      if (line.match(/^sk-[A-Za-z0-9_-]+$/)) {
        return `.env file misconfigured: Found what looks like an OpenAI API key without the variable name.\n\nYour .env file contains:\n  ${line}\n\nIt should be:\n  OPENAI_API_KEY=${line}\n\nPlease fix your .env file and restart Claude Code.`;
      }
    }
  } catch {
    // Ignore read errors
  }

  return undefined;
}

/**
 * Validate API key format for the given provider
 * Returns an error message if the key appears invalid
 */
function validateApiKeyFormat(provider: string, apiKey: string): string | undefined {
  switch (provider) {
    case "voyage":
      if (!apiKey.startsWith("pa-")) {
        return `Invalid Voyage API key format. Voyage API keys should start with "pa-".\n\nYour key starts with: "${apiKey.substring(0, 3)}..."\n\nGet a valid API key at https://www.voyageai.com/ and update your .env file.`;
      }
      break;
    case "openai":
      if (!apiKey.startsWith("sk-")) {
        return `Invalid OpenAI API key format. OpenAI API keys should start with "sk-".\n\nYour key starts with: "${apiKey.substring(0, 3)}..."\n\nCheck your API key and update your .env file.`;
      }
      break;
  }
  return undefined;
}

/**
 * Main entry point
 */
async function main() {
  // Load configuration
  const config = loadConfig();

  // Check for embedding API key - warn but don't exit (for MCP mode)
  let configError: string | undefined;
  let embedding: ReturnType<typeof createEmbeddingProvider> | undefined;

  // First, check for .env file misconfigurations
  const envFileError = checkEnvFile();
  if (envFileError) {
    configError = envFileError;
  } else if (!config.embedding.apiKey) {
    const envVar =
      config.embedding.provider === "voyage"
        ? "VOYAGE_API_KEY"
        : config.embedding.provider === "openai"
          ? "OPENAI_API_KEY"
          : `${config.embedding.provider.toUpperCase()}_API_KEY`;

    configError = `API key not configured. Get a free Voyage API key at https://www.voyageai.com/ and add it to your .env file:\n\n${envVar}=your-key-here\n\nThen restart Claude Code.`;
  } else {
    // Validate API key format
    const formatError = validateApiKeyFormat(config.embedding.provider, config.embedding.apiKey);
    if (formatError) {
      configError = formatError;
    }
  }

  // Only exit for non-MCP modes if there's an error (they need the API key to function)
  if (configError && config.server.mode !== "mcp") {
    console.error(`Error: ${configError}`);
    process.exit(1);
  }

  // Initialize embedding provider only if no config errors
  if (!configError && config.embedding.apiKey) {
    embedding = createEmbeddingProvider({
      type: config.embedding.provider,
      apiKey: config.embedding.apiKey,
      baseUrl: config.embedding.baseUrl,
      models: config.embedding.models,
      batchSize: config.embedding.batchSize,
      rateLimitMs: config.embedding.rateLimitMs,
    });
  }

  // Initialize vector store
  const vectorStore = createVectorStore({
    type: config.vectorStore.provider,
    path: config.vectorStore.path,
    apiKey: config.vectorStore.apiKey,
    host: config.vectorStore.host,
    environment: config.vectorStore.environment,
    namespace: config.vectorStore.namespace,
  });

  // Connect to vector store
  await vectorStore.connect();

  // Create tool registry and register tools
  const registry = new ToolRegistry();
  registry.register(searchCodeTool);
  registry.register(searchClientCodeTool);
  registry.register(searchGameDataTool);
  registry.register(codeStatsTool);
  registry.register(clientCodeStatsTool);
  registry.register(gameDataStatsTool);

  // Create tool context
  const context: ToolContext = {
    embedding,
    vectorStore,
    config,
    configError,
  };

  const { mode, host, port } = config.server;

  // Start servers based on mode
  if (mode === "mcp") {
    // MCP-only mode (for Claude)
    await startMCPServer(registry, context);
  } else if (mode === "rest") {
    // REST API only
    const restApp = createRESTServer(registry, context, config);
    startRESTServer(restApp, config);
  } else if (mode === "openai") {
    // OpenAI-compatible only
    const openaiApp = createOpenAIServer(registry, context, config);
    startOpenAIServer(openaiApp, host, port);
  } else if (mode === "all") {
    // Start all servers
    // Note: MCP uses stdio, so it runs in the background
    // REST and OpenAI use HTTP on different ports

    console.log("Starting Hytale RAG in multi-server mode...\n");

    // REST API on configured port
    const restApp = createRESTServer(registry, context, config);
    startRESTServer(restApp, config);

    // OpenAI-compatible on port + 1
    const openaiApp = createOpenAIServer(registry, context, config);
    startOpenAIServer(openaiApp, host, port + 1);

    console.log("\nTo use with Claude, run: npx tsx src/index.ts");
    console.log("(MCP mode is the default when no HTTP servers are needed)\n");
  }
}

// Run main
main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
