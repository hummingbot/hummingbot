#!/bin/bash

# Script to create symlink between gateway/conf and gateway_files/conf
# This prevents duplicate configuration directories when running Gateway from both source and Docker

echo "Gateway Configuration Symlink Setup"
echo "==================================="
echo ""
echo "This script creates a symlink from gateway_files/conf to gateway/conf"
echo "to prevent duplicate configuration directories when using both source and Docker."
echo ""

# Check if we're in the hummingbot directory
if [ ! -f "docker-compose.yml" ] || [ ! -d "gateway" ]; then
    echo "Error: This script must be run from the hummingbot root directory."
    echo "Please cd to your hummingbot directory and run again."
    exit 1
fi

# Check if gateway/conf exists
if [ ! -d "gateway/conf" ]; then
    echo "Warning: gateway/conf directory does not exist."
    echo "You may need to run gateway setup first."
    echo ""
fi

# Create gateway_files directory if it doesn't exist
if [ ! -d "gateway_files" ]; then
    echo "Creating gateway_files directory..."
    mkdir -p gateway_files
fi

# Check if gateway_files/conf already exists
if [ -e "gateway_files/conf" ]; then
    if [ -L "gateway_files/conf" ]; then
        echo "Symlink already exists at gateway_files/conf"
        target=$(readlink gateway_files/conf)
        echo "Currently pointing to: $target"

        if [ "$target" = "../gateway/conf" ]; then
            echo "✓ Symlink is already correctly configured."
            exit 0
        else
            echo ""
            read -p "Do you want to update the symlink to point to ../gateway/conf? (y/n) " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Aborted."
                exit 0
            fi
            rm gateway_files/conf
        fi
    else
        echo "Warning: gateway_files/conf exists but is not a symlink."
        echo "This directory contains:"
        ls -la gateway_files/conf 2>/dev/null | head -10
        echo ""
        read -p "Do you want to remove it and create a symlink instead? (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 0
        fi

        # Backup existing conf if it has content
        if [ -d "gateway_files/conf" ] && [ "$(ls -A gateway_files/conf)" ]; then
            backup_name="gateway_files/conf.backup.$(date +%Y%m%d_%H%M%S)"
            echo "Backing up existing conf to $backup_name"
            mv gateway_files/conf "$backup_name"
        else
            rm -rf gateway_files/conf
        fi
    fi
fi

# Create the symlink
echo "Creating symlink: gateway_files/conf -> ../gateway/conf"
ln -s ../gateway/conf gateway_files/conf

# Verify the symlink was created successfully
if [ -L "gateway_files/conf" ]; then
    echo "✓ Symlink created successfully!"
    echo ""
    echo "Configuration:"
    echo "- Source runs will use: gateway/conf/"
    echo "- Docker runs will use: gateway/conf/ (via symlink)"
    echo ""
    echo "Both setups will now share the same configuration."
else
    echo "✗ Failed to create symlink."
    exit 1
fi
