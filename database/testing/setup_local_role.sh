#!/usr/bin/env bash
# Local test bootstrap. Requires sudo or root, because it creates a cluster role.
# Usage: sudo bash database/testing/setup_local_role.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must run as root so it can create the local PostgreSQL role." >&2
    exit 1
fi

su postgres -c "psql -v ON_ERROR_STOP=1 -q -d postgres -f '${HERE}/bootstrap_local_role.sql'"
echo "Local PostgreSQL role itp_app is ready (password is local only, never used in production)."
