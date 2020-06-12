#! /usr/bin/env bash
if [ ! -d "filestore" ]; then
  echo "Creating filestore directory"
  mkdir filestore
fi
if [ ! -d "ssh" ]; then
  echo "Creating ssh directory"
  mkdir ssh
  echo "Linking ssh keys"
  ln -P ~/.ssh/* ssh/
fi
