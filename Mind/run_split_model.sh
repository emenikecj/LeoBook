#!/bin/bash
echo "==================================================="
echo "     Official Llama.cpp Server (Split Files)"
echo "==================================================="
echo ""
echo "This runs your split model files using 'llama-server'."
echo "Ensure 'llama-server' binary is in this folder and executable."
echo ""

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ ! -f "$DIR/llama-server" ]; then
    echo "[ERROR] llama-server binary not found in $DIR!"
    echo "Please ensure the linux binary is renamed to 'llama-server' and placed here."
    exit 1
fi

echo "Starting Server..."
echo "Model: model.gguf"
echo "Vision: mmproj.gguf"
echo "URL: http://127.0.0.1:8080"
echo ""

# Make executable
chmod +x "$DIR/llama-server"

# Run the server (including local dir in library path for .so files)
export LD_LIBRARY_PATH="$DIR:$LD_LIBRARY_PATH"
"$DIR/llama-server" -m "$DIR/model.gguf" --mmproj "$DIR/mmproj.gguf" --host 127.0.0.1 --port 8080 -c 16384 > "$DIR/server.log" 2>&1 &
