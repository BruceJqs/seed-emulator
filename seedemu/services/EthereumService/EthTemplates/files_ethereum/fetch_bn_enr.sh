#!/bin/bash

BOOTNODES_FILE="/tmp/beacon-eth-nodes"
OUTPUT_ENR_FILE="/tmp/bc_enrs.txt"

MAX_RETRIES=60
SLEEP_SECONDS=3

ENRS=()

while read -r url; do
    echo "Fetching ENR from $url..."

    count=0
    while true; do
        enr=$(curl -s "$url" | jq -r '.data.enr')

        if [ -n "$enr" ] && [ "$enr" != "null" ]; then
            echo "Fetched ENR from $url"
            ENRS+=("$enr")
            break
        else
            echo "Failed to get ENR from $url, retrying in $SLEEP_SECONDS seconds..."
            sleep "$SLEEP_SECONDS"
            ((count++))
            if [ "$count" -ge "$MAX_RETRIES" ]; then
                echo "Gave up on $url after $MAX_RETRIES retries."
                break
            fi
        fi
    done
done < "$BOOTNODES_FILE"

# Join ENRs with commas
IFS=','; echo "${ENRS[*]}" > "$OUTPUT_ENR_FILE"; unset IFS

echo "All ENRs saved to $OUTPUT_ENR_FILE"
