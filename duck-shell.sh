#!/bin/sh
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

# Check if container is running, start if not
if ! podman ps -q -f name=rubber-duck-container | grep -q .; then
    echo "Container not running, starting devcontainer..."
    devcontainer up --docker-path podman --workspace-folder "$(dirname "$0")"
fi

podman exec -it -u vscode -w /workspaces/rubber-duck rubber-duck-container bash
