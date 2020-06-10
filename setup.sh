#! /usr/bin/env bash

for var in $@; do
  if [[ "$var" = "build" ]]; then
    build=true
  fi

  if [[ "$var" = "init" ]] || [[ "$var" = "i" ]]; then
    init=true
  fi

  if [[ "$var" = "update" ]]; then
    update=true
  fi

done


if [[ "$build" = true ]]; then
  GID="$(id -g $USER)"
  docker-compose build --build-arg UID=$UID --build-arg GID=$GID
fi

if [[ "$init" = true ]]; then
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
  docker-compose run --rm odoo odoo init
fi

if [[ "$update" = true ]]; then
  docker-compose run --rm odoo odoo update 
fi
