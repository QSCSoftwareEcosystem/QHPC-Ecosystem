# ChatQEC Bundled Corpus Verification

- Date: 2026-09-03
- Source: `https://github.com/QSCSoftwareThrust/ChatQEC`
- Revision: `a1ddc2e4916b1f4152fba4c94c9c7512eea0d977`
- Upstream license: Apache-2.0
- Canonical pages: 60
- Corpus digest: `sha256:95e43b52660f4789457ef54b0b5c3ffc557b0610e24fc4780ed709c800928330`
- License digest: `sha256:c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`

## Result

EQO Local packages the exact ChatQEC canonical Markdown corpus and its upstream
license inside the release wheel. Startup validates `SOURCE.json` against the
active service contract, verifies the license checksum, reconstructs the
canonical corpus digest, and checks the expected page count before exposing the
loopback Assistant service. The default `eqo local up` path therefore performs
no clone, fetch, model request, embedding request, or corpus write.

The 60 operational canonical pages were unchanged between EQO's previous pin
`4c017510511f835001bfe5901a9d59e86cc130cd` and the selected revision. The newer
revision adds upstream ChatQEC application, documentation, QAppsWiki, and QEC
tooling work without changing the locally served canonical content.

## Boundary

This evidence covers the deterministic, extractive, tool-disabled local
Assistant only. It does not approve the upstream generative model stack,
Qdrant deployment, web fallback, MCP tool execution, provider credentials, or
institutional production deployment.
