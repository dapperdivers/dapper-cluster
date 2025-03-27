#!/bin/sh

# Use yq to process the template and replace environment variables
echo "Reading template file..."
cat /app/config-file/config.json.template > /tmp/config.json

# Replace environment variables using yq
echo "Processing configuration..."
yq -i '.ApiPart.FanartTvAPIKey = env(FANARTTV_API_KEY)' /tmp/config.json
yq -i '.ApiPart.tvdbapi = env(TVDB_API_KEY)' /tmp/config.json
yq -i '.ApiPart.tmdbtoken = env(TMDB_READ_API_TOKEN)' /tmp/config.json
yq -i '.ApiPart.PlexToken = env(PLEX_TOKEN)' /tmp/config.json

# Move the processed file to the app config directory
mkdir -p /app/config
chmod 660 /tmp/config.json

mv /tmp/config.json /app/config/config.json


echo "Config processed successfully"


# Remove running file if it exists
if [ -f "/app/config/temp/Posterizarr.Running" ]; then
    rm /app/config/temp/Posterizarr.Running
fi

echo "Container ready to start"
