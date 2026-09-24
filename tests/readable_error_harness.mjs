/* Runs the SHIPPED `readableError` from `rlm_notebook/web/app.js` against inputs on stdin.
 *
 * Why this exists: the previous test for this function re-compiled its regex LITERALS with Python's
 * `re` and never called it. Replacing the whole body with `return String(text || "")` left the
 * suite green, while the live function was returning the empty string for two of the commonest
 * provider failures. A test that pins a function's inputs is not a test of the function.
 *
 * Extraction rather than import: `app.js` is a classic script that touches `document` at load, and
 * there is no build step to make it importable. Pulling the constants and the one function out by
 * name keeps this honest — a rename here fails loudly rather than silently testing nothing.
 *
 * **Stated limit:** `humanBytes` here returns the raw byte count where the product returns a
 * human size ("50 MB"). Nothing asserts on that string today and `FORBIDDEN` carries no digit
 * rule, so it is not load-bearing — but a header that says a helper is stubbed should say where
 * the stub and the product differ, or the next reader trusts a number this file never produced.
 *
 * stdin:  {"cases": ["raw message", …]}
 * stdout: {"results": ["cleaned", …]}
 */
import { readFileSync } from "node:fs";

const APP = new URL("../rlm_notebook/web/app.js", import.meta.url);
const src = readFileSync(APP, "utf8");

import { buildReadableError } from "./readable_error_parts.mjs";

const readableError = buildReadableError(src);

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { cases } = JSON.parse(input);
process.stdout.write(JSON.stringify({ results: cases.map((c) => readableError(c)) }));
