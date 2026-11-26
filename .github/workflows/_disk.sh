#!/usr/bin/env bash
# Frees the runner's disk for images of 15 to 40 GB: drops what the job does
# not use and moves Docker (and containerd, where Docker 29 keeps images) to
# /mnt, the runner's larger second disk.
set -euo pipefail
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache /usr/local/share/boost "${AGENT_TOOLSDIRECTORY:-/nonexistent}" || true
sudo docker image prune -af || true
sudo systemctl stop docker
sudo systemctl stop containerd || true
sudo mkdir -p /mnt/docker /mnt/containerd
sudo rm -rf /var/lib/containerd && sudo ln -s /mnt/containerd /var/lib/containerd
echo '{"data-root":"/mnt/docker","features":{"containerd-snapshotter":false}}' | sudo tee /etc/docker/daemon.json
sudo systemctl start containerd || true
sudo systemctl start docker
docker info --format 'root={{.DockerRootDir}} driver={{.Driver}}'
df -h / /mnt
