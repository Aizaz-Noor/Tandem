import { buildSync } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
mkdirSync(new URL(".generated", import.meta.url), { recursive: true });
buildSync({ entryPoints: ["src/lib/rpc.ts"], bundle: true, platform: "node", format: "esm", outfile: "tests/.generated/rpc.mjs" });
const result = spawnSync(process.execPath, ["--test", "tests/rpc.test.mjs"], { stdio: "inherit" });
process.exit(result.status ?? 1);
