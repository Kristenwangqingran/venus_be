#!/bin/bash
# install spexmgr with one shell command
# bash <(curl -ksSL http://10.105.38.237:9000/spexmgr-releases/install.sh) v${MAJOR}.${MINOR}.${PATCH} # 版本号例如：v0.0.1

set -e

function echoError() {
    echo -e "\033[31m✘ $1\033[0m" # red
}
export -f echoError

function echoInfo() {
    echo -e "\033[32m✔ $1\033[0m" # green
}
export -f echoInfo

function echoWarn() {
    echo -e "\033[33m! $1\033[0m" # yellow
}
export -f echoError

version=$1
pkg="spexmgr-${version}.tar.gz"


function main() {
    echoInfo "Detect target spexmgr package..."

    # download from aliyun OSS or github packages
    url="http://10.105.38.237:9000/spexmgr-releases/$pkg"
    echoInfo "url: ${url}"
    valid_flag=false
    if curl --output /dev/null --silent --head --fail "$url"; then
        valid_flag=true
    fi

    if [[ "$valid_flag" == false ]]; then
        echoError "No available download url found, exit!"
        exit 1
    fi
    echo "Download url: $url"
    echo

    echoInfo "Downloading...."
    echo "$ curl -kL $url -o $pkg"
    curl -kL $url -o "$pkg"
    echo


    # for linux or darwin, install spexmgr to /usr/local/bin
    # extract to temp directory
    echoInfo "Created temp dir..."
    echo "$ mktemp -d -t spexmgr.XXXX"
    tmp_dir=$(mktemp -d -t spexmgr.XXXX)
    echo "$tmp_dir"
    echo "$ mv $pkg $tmp_dir && cd $tmp_dir"
    mv $pkg $tmp_dir
    cd "$tmp_dir"
    echo

    echoInfo "Extracting..."
    echo "$ tar -xzf $pkg"
    tar -xzf "$pkg"
    cp "spexmgr-${version}" spexmgr

    echo "$ ls -lh"
    ls -lh
    echo

    echoInfo "Installing..."
    if spexmgr -v > /dev/null && [ $(command -v spexmgr) != "./spexmgr" ]; then
        echoWarn "$(spexmgr -v) exists, remove first !!!"
        echo "$ rm -rf $(command -v spexmgr)"
        rm -rf "$(command -v spexmgr)"
    fi

    echo "$ chmod +x spexmgr && mv spexmgr /usr/local/bin/"
    chmod +x spexmgr
    mv spexmgr /usr/local/bin/
    echo

    echoInfo "Check installation..."
    echo "$ command -v spexmgr"
    command -v spexmgr
    echo "$ spexmgr -v"
    spexmgr -v
    echo "$ spexmgr -h"
    spexmgr -h
    echo
}
main
