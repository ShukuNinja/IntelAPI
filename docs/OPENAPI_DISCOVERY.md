# Specification import status

The current import workflow accepts content supplied by the user in the Explorer. It does not make outbound network requests.

## Supported formats

- OpenAPI 3.0.x and 3.1.x as JSON or YAML.
- Swagger 2.0 as JSON or YAML, normalized to an OpenAPI 3.0-shaped document before operation extraction.
- YAML uses PyYAML `safe_load`; Python-specific YAML constructors are not enabled.
- Source content and dictionary imports are limited to 2,000,000 bytes.

## Current API

- `POST /api/v1/specifications/parse` accepts either `{ "document": {...} }` or `{ "content": "...", "source_format": "json|yaml" }`.
- `POST /api/v1/specifications/candidates/preview` previews candidates for one normalized operation.
- `POST /api/v1/specifications/candidates/report` builds a deterministic, endpoint-wise preview report for 1–100 operations, with at most 20 candidates per operation and 500 per report.

The parse result has a specification title/version and normalized operation records with stable IDs, method, path, operation ID, summary, tags, request body, and merged path/operation parameters. Swagger 2 body/form parameters are mapped to OpenAPI request bodies.

## Security and limitations

- Imports are session-only and are not persisted yet.
- URL discovery, Swagger UI config inspection, remote fetching, auth handling, and SSRF protections are not implemented. Do not pass a URL to the content endpoint expecting it to fetch the document.
- `$ref` values are not resolved or fetched. Candidate generation uses only inline schemas and parameters.
- This is structural normalization, not a complete OpenAPI validator. Invalid or unsupported fields may be omitted; supported version/root errors return 422.
- Swagger 2 conversion supports common body, formData, parameter, server, and security-scheme shapes. It is not a complete equivalence transform for every vendor extension or legacy edge case.
