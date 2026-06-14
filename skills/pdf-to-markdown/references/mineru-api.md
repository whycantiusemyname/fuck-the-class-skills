# MinerU API Notes

This skill assumes the MinerU precise parsing API documented at:

- [API docs](https://mineru.net/apiManage/docs)
- [API limits](https://mineru.net/apiManage/limit)

The implementation is intentionally pinned to the constraints verified on 2026-04-30:

- precise API file size limit: `200MB`
- precise API page limit: `200` pages
- local upload endpoint: `POST /api/v4/file-urls/batch`
- upload method: `PUT` to each returned `file_url`
- upload URL request limit: at most `50` files per request
- result polling endpoint: `GET /api/v4/extract-results/batch/{batch_id}`
- result archive field: `data.extract_result[].full_zip_url`
- batch result states: `waiting-file`, `pending`, `running`, `converting`, `done`, `failed`

The skill uses lower internal safety thresholds:

- page limit per chunk: `180`
- size limit per chunk: `180MB`

This margin reduces the chance of edge cases around metadata size, file conversion overhead, or API-side counting differences.

## Error Handling Contract

Treat these conditions as retriable:

- temporary network errors
- HTTP `5xx`
- `-10001`
- `-60001`
- `-60007`
- `-60008`
- `-60009`
- `-60010`
- `-60020`
- `-60021`
- `-60022`

Treat these as oversize or re-split signals:

- `-60005`
- `-60006`

Treat these as permanent without manual intervention:

- `A0202`
- `A0211`
- `-60002`
- `-60003`
- `-60004`
- `-60011`
- `-60015`
- `-60016`

## Result Assumptions

For non-HTML precise parsing results:

- `full.md` is the main Markdown output
- JSON sidecar files may include model or layout details
- images may be stored in subdirectories within the extracted archive

Normalization should treat `full.md` as authoritative for first-pass structure and use sidecar files only when needed for diagnostics.
