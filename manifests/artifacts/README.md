# manifests/artifacts

Manifests of sim evidence stored in the fleet artifact store (`klt artifact put`).
Git keeps only these small `*.manifest.json` files (one per run, `<bench>-<record-id>`)
plus the Markdown summary; the bytes are fetched with `klt artifact get` and checked with
`klt artifact verify <manifest>`. Every `uri` is a logical `artifact:<key>`; no bucket,
endpoint or presigned URL is ever written here. Append-only. See `sim/README.md`.
