#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 PREPARED_QFW_SLURM_CHECKOUT" >&2
    exit 64
fi

fixture_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd "${fixture_dir}/../../.." && pwd)"
checkout="$(realpath "$1")"
builder="qhpc-attested"
buildkit_image="docker.io/moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
scanner_image="docker.io/docker/buildkit-syft-scanner@sha256:ae4f3b554449e7e25548e7d8ccc029d17357348e30c6e3df01b92bc93654d6a9"
image="qhpc/openqse-qfw-slurm:0.1.0-office"
evidence_dir="${workspace_root}/.development/qfw-admission/evidence"
archive="${evidence_dir}/qfw-slurm-office.oci.tar"

for command in docker realpath; do
    command -v "${command}" >/dev/null || {
        echo "required command is unavailable: ${command}" >&2
        exit 69
    }
done

for file in Dockerfile.qhpc Dockerfile.qhpc.dockerignore source-lock.json; do
    [[ -f "${checkout}/${file}" ]] || {
        echo "prepared checkout is missing ${file}: ${checkout}" >&2
        exit 66
    }
done

mkdir -p "${evidence_dir}"

if ! docker buildx inspect "${builder}" >/dev/null 2>&1; then
    docker buildx create \
        --name "${builder}" \
        --driver docker-container \
        --driver-opt "image=${buildkit_image}" \
        --use >/dev/null
fi
docker buildx inspect "${builder}" --bootstrap >/dev/null

builder_container="buildx_buildkit_${builder}0"
actual_builder_image="$(
    docker inspect --format '{{.Config.Image}}' "${builder_container}"
)"
if [[ "${actual_builder_image}" != "${buildkit_image}" \
    && "${actual_builder_image}" != "${buildkit_image#docker.io/}" ]]; then
    echo "builder ${builder} does not use the admitted BuildKit image" >&2
    echo "expected: ${buildkit_image}" >&2
    echo "actual:   ${actual_builder_image}" >&2
    exit 65
fi

docker buildx build \
    --progress=plain \
    --builder "${builder}" \
    --platform linux/amd64 \
    --file "${checkout}/Dockerfile.qhpc" \
    --tag "${image}" \
    --provenance=mode=max \
    --attest "type=sbom,generator=${scanner_image}" \
    --metadata-file "${evidence_dir}/build-metadata.json" \
    --output "type=oci,dest=${archive}" \
    "${checkout}"

# Docker's local image store does not retain the OCI attestation manifests.
# Reuse the verified build cache to load the same platform image for tests;
# callers must compare its config digest with the OCI platform descriptor.
docker buildx build \
    --progress=plain \
    --builder "${builder}" \
    --platform linux/amd64 \
    --file "${checkout}/Dockerfile.qhpc" \
    --tag "${image}" \
    --provenance=false \
    --sbom=false \
    --load \
    "${checkout}"

docker image inspect --format '{{.Id}}' "${image}"
echo "Attested OCI archive: ${archive}"
