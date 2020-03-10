#!/usr/bin/env bash
set -eux
container_id=$(sudo docker ps | grep 'cdignam/kodiak' | awk '{print $1}')
sudo docker restart "$container_id"
