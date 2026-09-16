#!/usr/bin/env bash

set -euo pipefail

secret_value() {
    local path="$1"
    local label="$2"
    local value

    if [[ ! -f "${path}" ]]; then
        echo "Missing ${label} secret: ${path}" >&2
        exit 1
    fi
    value="$(<"${path}")"
    if [[ ! "${value}" =~ ^[0-9a-f]{64}$ ]]; then
        echo "Invalid ${label} secret format" >&2
        exit 1
    fi
    printf '%s' "${value}"
}

install_runtime_secrets() {
    local munge_key
    local jwt_key

    munge_key="$(secret_value /run/secrets/qhpc_munge_key "MUNGE")"
    jwt_key="$(secret_value /run/secrets/qhpc_jwt_key "Slurm JWT")"

    install -d -m 0700 /etc/munge
    install -d -o munge -g munge -m 0755 /run/munge
    install -d -o munge -g munge -m 0700 /var/log/munge
    printf '%s' "${munge_key}" >/etc/munge/munge.key
    chown munge:munge /etc/munge/munge.key
    chmod 0400 /etc/munge/munge.key

    printf '%s' "${jwt_key}" >/etc/slurm/jwt.key
    chown slurm:slurm /etc/slurm/jwt.key
    chmod 0600 /etc/slurm/jwt.key
}

start_munge() {
    install_runtime_secrets
    gosu munge /usr/sbin/munged
}

if [[ "${1:-}" == "slurmdbd" ]]; then
    database_password="$(
        secret_value /run/secrets/qhpc_slurm_db_password "Slurm database"
    )"
    # Slurm 25.05's slurmdbd no longer accepts a config-path flag. The
    # container filesystem is ephemeral, so place the file-backed secret in
    # the daemon's normal configuration path only after startup.
    sed -i "s/^StoragePass=.*/StoragePass=${database_password}/" \
        /etc/slurm/slurmdbd.conf
    start_munge
    until MYSQL_PWD="${database_password}" \
        mysql -h mysql -u slurm -e 'SELECT 1' >/dev/null 2>&1; do
        sleep 2
    done
    unset database_password MYSQL_PWD
    exec gosu slurm /usr/sbin/slurmdbd -D
fi

if [[ "${1:-}" == "slurmctld" ]]; then
    install -d -o slurm -g slurm -m 0700 /var/lib/qfw-slurm/allocations
    start_munge
    until (echo >/dev/tcp/slurmdbd/6819) >/dev/null 2>&1; do
        sleep 2
    done
    exec gosu slurm /usr/sbin/slurmctld -i -D
fi

if [[ "${1:-}" == "slurmd" ]]; then
    start_munge
    until (echo >/dev/tcp/slurmctld/6817) >/dev/null 2>&1; do
        sleep 2
    done
    exec /usr/sbin/slurmd -D
fi

if [[ "${1:-}" == "slurmrestd" ]]; then
    echo "slurmrestd is disabled by the QHPC compatibility profile" >&2
    exit 64
fi

exec "$@"
