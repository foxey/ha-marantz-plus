#!/bin/bash
# Find the SSH agent socket that actually has keys
# This is needed for devpod which creates multiple auth-agent sockets

# Check if SSH_AUTH_SOCK is already set and working
if [ -n "$SSH_AUTH_SOCK" ] && [ -S "$SSH_AUTH_SOCK" ]; then
    if ssh-add -l >/dev/null 2>&1; then
        # Current SSH_AUTH_SOCK works, no need to change
        exit 0
    fi
fi

# Try to find a working auth-agent socket (devpod specific)
shopt -s nullglob
for socket in /tmp/auth-agent*/listener.sock; do
    if [ -S "$socket" ]; then
        if SSH_AUTH_SOCK="$socket" ssh-add -l >/dev/null 2>&1; then
            export SSH_AUTH_SOCK="$socket"
            echo "export SSH_AUTH_SOCK=\"$socket\"" >> /home/vscode/.bashrc
            break
        fi
    fi
done
