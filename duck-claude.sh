#!/bin/sh
podman exec -it -u vscode -w /workspaces/rubber-duck rubber-duck-container claude --dangerously-skip-permissions
