#!/bin/sh
# SPDX-FileCopyrightText: 2025 Rubber Duck Contributors
# SPDX-License-Identifier: MPL-2.0

podman exec -it -u vscode -w /workspaces/rubber-duck rubber-duck-container claude --dangerously-skip-permissions
