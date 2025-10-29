#!/bin/sh

# Ensure config directory exists
mkdir -p /config

# Check if config.json exists
if [ -f /config/config.json ]; then
    echo "Config file exists, updating API keys only..."

    # Surgically update only the API key fields, preserving all other settings
    yq -i '.ApiPart.FanartTvAPIKey = env(FANARTTV_API_KEY)' /config/config.json
    yq -i '.ApiPart.tvdbapi = env(TVDB_API_KEY)' /config/config.json
    yq -i '.ApiPart.tmdbtoken = env(TMDB_READ_API_TOKEN)' /config/config.json
    yq -i '.ApiPart.PlexToken = env(PLEX_TOKEN)' /config/config.json

    echo "API keys updated successfully"
else
    echo "Config file does not exist, creating from template..."

    # Copy template and inject secrets
    cat /app/config-file/config.json.template > /tmp/config.json

    # Replace environment variables using yq
    yq -i '.ApiPart.FanartTvAPIKey = env(FANARTTV_API_KEY)' /tmp/config.json
    yq -i '.ApiPart.tvdbapi = env(TVDB_API_KEY)' /tmp/config.json
    yq -i '.ApiPart.tmdbtoken = env(TMDB_READ_API_TOKEN)' /tmp/config.json
    yq -i '.ApiPart.PlexToken = env(PLEX_TOKEN)' /tmp/config.json

    chmod 660 /tmp/config.json
    mv /tmp/config.json /config/config.json

    echo "Initial config created successfully"
fi

# Remove running file if it exists
if [ -f "/config/temp/Posterizarr.Running" ]; then
    echo "Removing stale running lock file..."
    rm /config/temp/Posterizarr.Running
fi

echo "Init container completed successfully"
