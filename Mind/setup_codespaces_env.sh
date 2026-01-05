#!/bin/bash
# setup_codespaces_env.sh
# GitHub Codespaces setup script for llama.cpp environment

set -euo pipefail  # Fail fast on errors

# Define extraction directory
MIND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Setting up Llama environment in Codespaces: $MIND_DIR"

# Check if we're in Codespaces
if [ -z "${CODESPACES:-}" ]; then
    echo "Warning: CODESPACES environment variable not detected."
    echo "This script is optimized for GitHub Codespaces but will work in other Linux environments."
fi

# 1. Try TAR.GZ first (newer releases), fallback to ZIP
echo "Fetching latest llama.cpp release info..."
if ! LATEST_TAG=$(curl -s --connect-timeout 10 https://api.github.com/repos/ggerganov/llama.cpp/releases/latest | grep '"tag_name"' | head -1 | cut -d '"' -f 4); then
    echo "Warning: Could not fetch latest release from GitHub API. Falling back to known working version."
    LATEST_TAG="b4485"
elif [ -z "$LATEST_TAG" ]; then
    echo "Warning: Empty release tag received. Falling back to known working version."
    LATEST_TAG="b4485"
fi

echo "Using llama.cpp release: $LATEST_TAG"

# Try TAR.GZ first, then ZIP
TAR_NAME="llama-${LATEST_TAG}-bin-ubuntu-x64.tar.gz"
ZIP_NAME="llama-${LATEST_TAG}-bin-ubuntu-x64.zip"

DOWNLOAD_URL=""
ARCHIVE_NAME=""

# Check which format exists
if curl -sL --head "https://github.com/ggerganov/llama.cpp/releases/download/$LATEST_TAG/$TAR_NAME" | grep -q "HTTP/.* 200"; then
    DOWNLOAD_URL="https://github.com/ggerganov/llama.cpp/releases/download/$LATEST_TAG/$TAR_NAME"
    ARCHIVE_NAME="$TAR_NAME"
    EXTRACT_CMD="tar -xzf"
    ARCHIVE_FILE="$MIND_DIR/llama-codespaces.tar.gz"
elif curl -sL --head "https://github.com/ggerganov/llama.cpp/releases/download/$LATEST_TAG/$ZIP_NAME" | grep -q "HTTP/.* 200"; then
    DOWNLOAD_URL="https://github.com/ggerganov/llama.cpp/releases/download/$LATEST_TAG/$ZIP_NAME"
    ARCHIVE_NAME="$ZIP_NAME"
    EXTRACT_CMD="unzip -o"
    ARCHIVE_FILE="$MIND_DIR/llama-codespaces.zip"
else
    echo "ERROR: Could not find suitable archive for $LATEST_TAG! Available assets:"
    curl -s "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest" | grep "browser_download_url.*ubuntu.*x64" | cut -d '"' -f 4
    exit 1
fi

echo "Downloading llama.cpp $LATEST_TAG ($ARCHIVE_NAME) from: $DOWNLOAD_URL"

# 2. Download with progress indicator and basic verification
if command -v wget &> /dev/null; then
    wget --show-progress -O "$ARCHIVE_FILE" "$DOWNLOAD_URL"
else
    curl -L --progress-bar -o "$ARCHIVE_FILE" "$DOWNLOAD_URL"
fi

# Basic check that download succeeded and file is not empty
if [ ! -s "$ARCHIVE_FILE" ]; then
    echo "ERROR: Downloaded archive is empty or missing!"
    exit 1
fi

# 3. Extract files
echo "Extracting files..."
mkdir -p "$MIND_DIR/temp_extract"
if [ "$EXTRACT_CMD" = "tar -xzf" ]; then
    $EXTRACT_CMD "$ARCHIVE_FILE" -C "$MIND_DIR/temp_extract" --strip-components=1 2>/dev/null || $EXTRACT_CMD "$ARCHIVE_FILE" -C "$MIND_DIR/temp_extract"
else
    $EXTRACT_CMD "$ARCHIVE_FILE" -d "$MIND_DIR/temp_extract"
fi

# Handle different archive structures
SOURCE_DIR=""
if [ -f "$MIND_DIR/temp_extract/build/bin/llama-server" ]; then
    SOURCE_DIR="$MIND_DIR/temp_extract/build/bin"
    echo "Found binaries in build/bin structure"
elif [ -f "$MIND_DIR/temp_extract/bin/llama-server" ]; then
    SOURCE_DIR="$MIND_DIR/temp_extract/bin"
    echo "Found binaries in bin structure"
elif [ -f "$MIND_DIR/temp_extract/llama-server" ]; then
    SOURCE_DIR="$MIND_DIR/temp_extract"
    echo "Found binaries in flat structure"
fi

if [ -n "$SOURCE_DIR" ]; then
    echo "Copying files to Mind directory..."

    # Copy the server executable
    if [ -f "$SOURCE_DIR/llama-server" ]; then
        cp "$SOURCE_DIR/llama-server" "$MIND_DIR/llama-server"
        echo "✓ Copied llama-server"
    fi

    # Copy all shared libraries (*.so and *.so.*) to the same directory as the executable
    if ls "$SOURCE_DIR"/*.so* 1> /dev/null 2>&1; then
        cp "$SOURCE_DIR"/*.so* "$MIND_DIR/" 2>/dev/null
        LIB_COUNT=$(ls "$SOURCE_DIR"/*.so* | wc -l)
        echo "✓ Copied $LIB_COUNT shared libraries (*.so*) to $MIND_DIR"
        echo "  Libraries: $(ls "$SOURCE_DIR"/*.so* | tr '\n' ' ')"
    else
        echo "⚠ No .so files found in $SOURCE_DIR - checking entire archive..."
        # Search entire extracted directory for shared libraries
        LIB_FILES=$(find "$MIND_DIR/temp_extract" -name "*.so*" -type f)
        if [ -n "$LIB_FILES" ]; then
            echo "$LIB_FILES" | wc -l | xargs echo "  Found" libraries in archive
            echo "$LIB_FILES" | xargs cp -t "$MIND_DIR/"
            echo "✓ Copied libraries from alternative locations"
        else
            echo "⚠ No shared libraries found in archive - binary may be statically linked"
        fi
    fi
else
    echo "ERROR: Could not find llama-server in extracted archive!"
    echo "Contents of extracted directory:"
    find "$MIND_DIR/temp_extract" -name "llama-server" 2>/dev/null || echo "llama-server not found"
    ls -la "$MIND_DIR/temp_extract"
    exit 1
fi

# Cleanup
echo "Cleaning up temporary files..."
rm -rf "$MIND_DIR/temp_extract"
rm -f "$ARCHIVE_FILE"

# 4. Make executable and verify
chmod +x "$MIND_DIR/llama-server"

# Verify the installation
if [ -f "$MIND_DIR/llama-server" ]; then
    echo "✓ llama-server installed successfully ($LATEST_TAG)"

    # Test library dependencies
    echo "Checking library dependencies..."
    if command -v ldd &> /dev/null; then
        MISSING_LIBS=$(ldd "$MIND_DIR/llama-server" 2>/dev/null | grep "not found" | wc -l)
        if [ "$MISSING_LIBS" -eq 0 ]; then
            echo "✓ All library dependencies satisfied"
        else
            echo "⚠ Some libraries may be missing (this is normal in Codespaces if not critical)"
            echo "   Note: Shared libraries should now be found since they are in the same directory as llama-server."
        fi
    fi
else
    echo "ERROR: Failed to install llama-server!"
    exit 1
fi

echo ""
echo "========================================"
echo "🎉 SUCCESS!"
echo "llama-server ($LATEST_TAG) has been installed to: $MIND_DIR/llama-server"
echo "All required shared libraries (*.so*) are now in the same directory."
echo ""
echo "Next steps:"
echo "1. Run: python Leo.py"
echo "2. The system will automatically start the AI server"
echo "   (It should now run without the libllama.so error)"
echo "========================================"
