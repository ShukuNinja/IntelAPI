# Candidate generation

Candidate previews are deterministic and schema-derived. They do not issue HTTP requests or claim that a response is defective. Current rules include omission of required parameters and body properties, values outside declared enums, values below an integer minimum, and strings longer than a declared maxLength.

Candidate IDs are stable hashes scoped to an operation and derived from the rule, rationale, and mutation. Preview records have `validation_status: preview`; this status does not mean that a candidate was sent to a target API. String-length boundary mutations are emitted only when `maxLength` is below 4096 so the preview itself stays bounded.

The endpoint-wise preview report labels its policy `schema-preview-v1`. It accepts at most 100 operations, retains up to 20 candidates per endpoint, and caps the report at 500 candidates. A `truncated` flag indicates when those caps removed suggestions. Preview data currently exists only in the API response and browser session; no generation report is persisted.

Current limits: generation only understands inline parameter schemas and inline `application/json` request-body schemas. It does not resolve `$ref`, validate generated requests against a full JSON Schema implementation, deduplicate semantically equivalent mutations across endpoints, execute candidates, or use feedback from prior runs.
