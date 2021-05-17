docker run -d \
    -v /tmp/git-data:/tmp/git \
    -v /home/jon.battista/.ssh/traitor:/etc/git-secret/ssh \
    -v /home/jon.battista/.ssh/known_hosts:/etc/git-secret/known_hosts \
    registry/git-sync:tag \
        --repo=git@github.com:jonbattista/trading_infra.git \
        --ssh \
        --ssh-keyfile='/etc/git-secret/ssh' \
        --ssh-known-hosts \
        --ssh-known-hosts-file='/etc/git-secret/known_hosts'
        --branch=master \
        --wait=30