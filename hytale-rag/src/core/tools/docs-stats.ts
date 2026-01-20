/**
 * Documentation Stats Tool
 *
 * Returns statistics about the indexed Hytale modding documentation.
 */

import { emptySchema, type EmptyInput } from "../schemas.js";
import type { ToolDefinition, ToolContext, ToolResult } from "./index.js";
import type { VersionInfo } from "../version-checker.js";

/**
 * Documentation statistics
 */
export interface DocsStats {
  totalDocs: number;
  byCategory: Record<string, number>;
  byType: Record<string, number>;
}

/**
 * Documentation stats tool definition
 */
export const docsStatsTool: ToolDefinition<EmptyInput, DocsStats> = {
  name: "hytale_docs_stats",
  description:
    "Get statistics about the indexed HytaleModding.dev documentation. " +
    "Shows total documents and breakdown by category and type.",
  inputSchema: emptySchema,

  async handler(_input, context): Promise<ToolResult<DocsStats>> {
    // Check for configuration errors
    if (context.configError) {
      return {
        success: false,
        error: context.configError,
      };
    }

    try {
      const tableName = context.config.tables.docs;

      // Check if table exists
      const exists = await context.vectorStore.tableExists(tableName);
      if (!exists) {
        return {
          success: false,
          error: "Documentation table not found. Run 'npm run ingest-docs' to index the documentation.",
        };
      }

      // Get basic stats
      const tableStats = await context.vectorStore.getStats(tableName);

      // Count by type and category by iterating through all rows
      const byCategory: Record<string, number> = {};
      const byType: Record<string, number> = {};

      for await (const batch of context.vectorStore.queryAll<{ type: string; category: string }>(tableName)) {
        for (const row of batch) {
          const category = row.category || "Other";
          const type = row.type || "unknown";

          byCategory[category] = (byCategory[category] || 0) + 1;
          byType[type] = (byType[type] || 0) + 1;
        }
      }

      return {
        success: true,
        data: {
          totalDocs: tableStats.rowCount,
          byCategory,
          byType,
        },
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  },
};

/**
 * Format documentation stats as markdown (for MCP/display)
 */
export function formatDocsStats(stats: DocsStats, versionInfo?: VersionInfo | null): string {
  const lines = [
    "# Hytale Modding Documentation Statistics",
    "",
    `**Total Documents:** ${stats.totalDocs.toLocaleString()}`,
    "",
  ];

  // By Category
  lines.push("## By Category");
  const sortedCategories = Object.entries(stats.byCategory)
    .sort((a, b) => b[1] - a[1]);
  for (const [category, count] of sortedCategories) {
    lines.push(`- **${category}:** ${count.toLocaleString()}`);
  }

  lines.push("");

  // By Type
  lines.push("## By Type");
  const sortedTypes = Object.entries(stats.byType)
    .sort((a, b) => b[1] - a[1]);
  for (const [type, count] of sortedTypes) {
    lines.push(`- **${type}:** ${count.toLocaleString()}`);
  }

  // Version info
  if (versionInfo) {
    lines.push("");
    lines.push("---");
    lines.push(`*Database version: ${versionInfo.currentVersion}*`);
    if (versionInfo.updateAvailable) {
      lines.push(`*Update available: ${versionInfo.latestVersion}*`);
    }
  }

  return lines.join("\n");
}
