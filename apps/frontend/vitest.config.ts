import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests for the shared SDK (@crs/sdk) run from here because the frontend
// owns the toolchain; the SDK package itself is consumed as source via the
// tsconfig path alias.
export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
  },
  resolve: {
    alias: {
      "@crs/sdk": fileURLToPath(new URL("../../packages/sdk/src/index.ts", import.meta.url)),
    },
  },
});
