#!/bin/bash
set -e
DEFAULT_VERSION="latest"
DEFAULT_INSTALL_PATH="/usr/local/bin/spcli"
SPCLI_S3_URL="http://proxy.uss.s3.sz.shopee.io/api/v4/50054564/spex-s3ia-sg-live/spcli"

echo "Start spcli installation"

if [ "$(uname)" = "Darwin" ];then
  if [ `whoami` = "root" ];then
    echo "Warning: You are using root role for installation! It will cause permissions problem when using spcli!"
    while true; do
      read -p "Do you want to stop installation？(Y/N)" yn
      case $yn in
          [Yy]* ) exit;;
          [Nn]* ) break;;
          * ) echo "Please answer yes or no.";;
      esac
    done
  fi
fi

# get specified version via flag
version=${DEFAULT_VERSION}
while getopts v: flag
do
    case "${flag}" in
        v) version=${OPTARG};;
    esac
done
echo "Installing spcli version: ${version}"

# install binary
install_path=$(which spcli) || install_path=${DEFAULT_INSTALL_PATH}
echo "Install path: ${install_path}"
binary_machine=$(uname -m| tr '[:upper:]' '[:lower:]')
if [ "$binary_machine" == "arm64" ]
then
  echo ${binary_machine}
  binary_name="spcli_$(uname -s| tr '[:upper:]' '[:lower:]')_arm64"
  echo ${binary_name}
else
  echo ${binary_machine}
  binary_name="spcli_$(uname -s| tr '[:upper:]' '[:lower:]')_amd64"
  echo ${binary_name}
fi
wget "${SPCLI_S3_URL}/${version}/${binary_name}" -O ${install_path}-tmp;
mv ${install_path}-tmp ${install_path}
chmod +x ${install_path}

# save cheksums in config dir
mkdir -p ~/.spcli
wget "${SPCLI_S3_URL}/${version}/checksums.txt" -O ~/.spcli/checksums.txt;
ochecksum=$(cat ~/.spcli/checksums.txt | grep ${binary_name} | awk '{print $1}')

# generate & compare checksums
if rchecksum=$(shasum -a 256 ${install_path} 2>/dev/null | awk '{print $1}'); then
    echo "checksum: ${rchecksum}"
elif rchecksum=$(sha256sum ${install_path} 2>/dev/null | awk '{print $1}'); then
    echo "checksum: ${rchecksum}"
else
    echo "get checksums fails (lack checksum shasum generation executable)"
    exit 1
fi
if [ "${ochecksum}" != "${rchecksum}" ]; then
    echo "checksum comparision error"
    echo "correct sha256 checksum: ${ochecksum}"
    echo "current sha256 checksum: ${rchecksum}"
    exit 1
fi

# download http.proto service.proto to $HOME/.spcli
mkdir -p $HOME/.spcli/include/spex/protobuf/
wget "${SPCLI_S3_URL}/${version}/http.proto" -O "$HOME/.spcli/include/spex/protobuf/http.proto";
wget "${SPCLI_S3_URL}/${version}/service.proto" -O "$HOME/.spcli/include/spex/protobuf/service.proto";

# test command
spcli version;
echo "Spcli installation completed."
echo "You can run 'spcli' now"
