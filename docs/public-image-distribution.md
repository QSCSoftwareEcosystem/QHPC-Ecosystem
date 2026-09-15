# Public EQO image distribution

The `dev-local` internal-test release at commit `65dc677` distributes its
admitted Linux/AMD64 OCI images through the GitHub Container Registry (GHCR)
namespace `ghcr.io/qscsoftwareecosystem`. A release owner can make the named
packages public when they are approved for external distribution.

The images are intentionally pulled by immutable digest, then checked against
the image identities in the EQO runtime contracts. EQO does not rely on a
mutable `latest` tag or silently replace a missing scientific tool with a
host-native substitute.

## Apptainer distribution (`USE_APPTAINER=1`)

With `USE_APPTAINER=1` set, EQO acquires the same digest-pinned set through
Apptainer instead of a Docker daemon. Each image is pulled by its immutable
`docker://…@sha256:` digest — the identity authority Apptainer verifies at pull
time — into a single `.sif` under
`~/.cache/qhpc-ecosystem/images/operations/<image>.sif`.

Because a SIF is not byte-reproducible across Apptainer versions or hosts, no
fixed SIF hash is pinned in the release manifest. Instead the hash of each
pulled SIF is recorded in a cache-side lock (`operations/sif-locks.json`) keyed
by its admitted local reference and immutable source digest. A later startup
reuses a SIF only when its bytes still match the recorded hash, so local
tampering is detected; a mismatch or a wrong source digest is refused before the
tool runs. The same lock backs the run-time admission check in the FTQC and
ChatQEC operation adapters.

Building images and the Docker Compose development fixtures remain Docker/Podman
operations; `USE_APPTAINER=1` governs image acquisition and tool execution, not
image builds.

## External tester installation

Install Docker Desktop (or a compatible Docker engine), clone the EQO source
release, and start EQO:

```bash
git clone --branch dev-local https://github.com/QSCSoftwareEcosystem/QHPC-Ecosystem.git
cd QHPC-Ecosystem

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[local]"
eqo local up --open
```

At first start, EQO downloads any missing admitted images from GHCR by
immutable digest, applies its required local names, and verifies every local
image ID before the Workbench starts. It reuses verified local images on later
starts. Public images require no GitHub login; for a private pre-release,
authenticate Docker to GHCR using access supplied by the release owner. They
target `linux/amd64`; Docker Desktop on Apple Silicon may use its Linux/AMD64
emulation support.

`tools/install_public_eqo_images.sh` remains available when an administrator
wants to preload the same verified set before installing EQO.

The first local startup also builds the small EQO-owned ChatQEC service image
from the admitted Tsim image. It does not fetch an unpinned parent image.

## Release-owner procedure

Before making a new set public, build and smoke-test every image, verify each
local image ID against its EQO runtime contract, push a versioned GHCR tag,
and record the resulting immutable digest in the installer. Do not overwrite
or rely on mutable tags. Package visibility must be changed to public only
after the image contents have been cleared for external distribution.

The published set for this release comprises QASMTrans, STABSim, NWQEC,
FTPrimitiveBench, LightStim, FTQC, and the ChatQEC QEC-tools, LightStim, and
Tsim images.
