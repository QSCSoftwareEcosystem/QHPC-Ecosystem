# Independent Stim and Tsim image build — 2026-09-16

The dedicated Linux/AMD64 images were built from the pinned
`chatqec-mcp-tools` Git archive and the contract-verified offline wheel cache.
Docker build-step networking was disabled by the `OperationRuntime` builder.

| Image | Local immutable image ID | Declared smoke result |
| --- | --- | --- |
| `qhpc/stim:0.1.0-linux-amd64` | `sha256:6e71488fd8cc36581295ab23807a538acd9e6b978a1cbc7e77b4f342e0448678` | Passed; `samples.json`, 316 bytes, `sha256:ef37816c1ca5118e5ee55917d55ac4e70a9e4dc8de47d117c6dc793930807630` |
| `qhpc/tsim:0.1.0-linux-amd64` | `sha256:2201fe400234a451f6a0bd38902f8c0c83e9a444001d035cdabde6aee22b4b17` | Passed; `samples.json`, 371 bytes, `sha256:d63f5568156acb1a14355902c00880a2dd157fe0a1d81748b99d1c4d427022b0` |

These are new development-only image identities. They have no published
registry digest, SBOM, signature, or attestation yet and must not replace the
public-image manifest until those release artifacts are generated and reviewed.
