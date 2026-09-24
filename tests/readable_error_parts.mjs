//: **The pieces `readableError` is assembled from, in ONE place.**
//:
//: Two harnesses build that function out of `app.js`: `readable_error_harness.mjs` (which tests it
//: directly) and `web_dom_harness.mjs` (whose scenarios need the message a reader actually gets).
//: They each carried their own copy of this list, and adding three constants to one of them left
//: the other silently building a DIFFERENT function — it did not fail loudly, it produced the wrong
//: sentence, which is the failure mode this project keeps a tripwire for elsewhere (invariant 28).
//: A shared module rather than a tripwire, because here the duplication can simply be removed.
export const CONSTANTS = [
  "NO_SERVER", "CANCELLED_RUN", "CANCELLED_STATUS", "SIZE_REFUSED", "NO_MODEL", "REFUSED_TARGET",
  "UNREACHABLE", "RUN_TIMED_OUT", "PROVIDER_DOWN", "HTML_BODY",
  "FROM_PROVIDER", "FROM_FETCH", "HTTP_STATUS", "URL_ANYWHERE",
  "BAD_KEY", "OVER_QUOTA", "NO_SUCH_MODEL", "REPLY_TOO_LONG", "CONTEXT_TOO_LONG",
  "MODEL_TAG", "BAD_PDF", "BAD_FILE_TYPE",
  "LEADING_NOISE", "CLASS_NAME", "EXC_REPR", "TRAILING_BLOB",
];

//: Functions `readableError` calls. Extracted BY NAME, so a rename fails loudly here rather than
//: leaving a copy behind that no longer ships.
export const HELPERS = ["fromProviderNotAUrl"];

//: Build the real function out of `src` (the text of `app.js`).
export function buildReadableError(src) {
  const decl = (name) => {
    const found = src.match(new RegExp(`^const ${name} =\\s*\\n?\\s*/[\\s\\S]*?/[a-z]*;$`, "m"));
    if (!found) throw new Error(`app.js no longer declares ${name}`);
    return found[0];
  };
  const helper = (name) => {
    const at = src.indexOf(`function ${name}(`);
    if (at < 0) throw new Error(`app.js no longer declares ${name}`);
    return src.slice(at, src.indexOf("\n}\n", at) + 3);
  };
  const at = src.indexOf("function readableError(");
  if (at < 0) throw new Error("app.js no longer declares readableError");
  return new Function(
    CONSTANTS.map(decl).join("\n") +
      "\n" + HELPERS.map(helper).join("\n") +
      "\nconst t = (key, fallback) => fallback;\n" +
      "const humanBytes = (n) => `${n} bytes`;\n" +
      src.slice(at, src.indexOf("\n}\n", at) + 3) +
      "\nreturn readableError;"
  )();
}
