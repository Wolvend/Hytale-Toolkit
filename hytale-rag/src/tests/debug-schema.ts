import { searchCodeSchema } from "../core/schemas.js";
import { zodToJsonSchema } from "../core/tools/index.js";

const schema = zodToJsonSchema(searchCodeSchema);
console.log("Generated JSON Schema:");
console.log(JSON.stringify(schema, null, 2));
