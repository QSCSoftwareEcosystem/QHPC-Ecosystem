#!/usr/bin/env bash
# Install the exact public OCI images admitted for the EQO internal-test release.
#
# This script deliberately pulls immutable digest references, retags them only
# to the local names EQO verifies, and then checks each local image identity.
set -euo pipefail

readonly release_tag="0.1.0-dev-local-65dc677"
readonly platform="linux/amd64"

install_image() {
  local package_name="$1"
  local expected_id="$2"
  local local_reference="$3"
  local remote_reference="ghcr.io/qscsoftwareecosystem/${package_name}@${expected_id}"

  printf 'Installing %s\n' "${local_reference}"
  docker pull --platform "${platform}" "${remote_reference}"
  docker tag "${remote_reference}" "${local_reference}"

  local actual_id
  actual_id="$(docker image inspect --format '{{.Id}}' "${local_reference}")"
  if [[ "${actual_id}" != "${expected_id}" ]]; then
    printf 'error: image identity mismatch for %s: expected %s, found %s\n' \
      "${local_reference}" "${expected_id}" "${actual_id}" >&2
    exit 1
  fi
}

install_image "eqo-qasmtrans" \
  "sha256:28e761efbd030c01e51edb96c7da6bafed7f18155c5b3973aa54aa030dbac9df" \
  "qhpc/qasmtrans:1843c98-linux-amd64"
install_image "eqo-stabsim" \
  "sha256:4ee1a6deae715be6c22d44447b6f6a655a81c0ee1be63c67ab601431c44a904b" \
  "qhpc/stabsim:a0d8d2e-linux-amd64"
install_image "eqo-nwqec" \
  "sha256:ec487f7735925388fb960ea3a0c97aca2298f51c05beb1b96f3d90a81f7b9e7b" \
  "qhpc/nwqec:d93299c-linux-amd64"
install_image "eqo-ftprimitivebench" \
  "sha256:329c0f99e7fb2373323a5d3fae5f1f4266d290914ec6f6a8bdd60ef2326259c9" \
  "qhpc/ftprimitivebench:ba15eba-linux-amd64"
install_image "eqo-lightstim" \
  "sha256:7731c5d9188a4eb5ad8f9448323b60e6ab722786d8f00f9b691d082edf6ec074" \
  "qhpc/lightstim:23924ee-linux-amd64"
install_image "eqo-ftqc" \
  "sha256:f46f1c36dc78310453776706316e8cc6baa0bb112ff2dea8512697cd0f005c96" \
  "qhpc/ftqc:779216de-linux-amd64"
install_image "eqo-chatqec-qec-tools" \
  "sha256:b3b7a84fd409ef979df26e37dad4ef45f946782238ec6c085a345a154ef125e2" \
  "qhpc/chatqec-qec-tools:dd19a85-linux-amd64-v2"
install_image "eqo-chatqec-lightstim" \
  "sha256:476e66c70130e8f413827a3264659581d92a80fbc4e5ec9113e67f596d760d21" \
  "qhpc/chatqec-lightstim:dd19a85-linux-amd64-v3"
install_image "eqo-chatqec-tsim" \
  "sha256:05524a6a1cb04618fc0797c46f071ac5447cd2f89aa7fe36598c2fa550538db0" \
  "qhpc/chatqec-tsim:dd19a85-linux-amd64"

printf 'EQO public OCI images installed for %s (%s).\n' "${release_tag}" "${platform}"
