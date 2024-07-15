#!/usr/bin/env bash

SSH_HOSTS=(
  git.initos.com
  github.com
)

if [ ! -d "filestore" ]; then
  echo -e "\033[0;32mCreating filestore directory\033[0m"
  mkdir filestore
fi

if [ ! -d "ssh" ]; then
  echo -e "\033[0;32mCreating ssh directory\033[0m"
  mkdir ssh
  echo -e "\033[0;32mGenerating hosts keys\033[0m"
  rm -f ssh/known_hosts
  for host in "${SSH_HOSTS[@]}"; do
    ssh-keyscan "$host" >> ssh/known_hosts
  done
fi

if [ ! -f ".env" ]; then
  echo -e "\033[0;32mGenerating basic .env\033[0m"
  cat > .env <<EOL
UID=$(id -u)
GID=$(id -g)
UMASK=$(umask)

DB_PASSWORD=$(cat /dev/urandom | tr -d -c "[:alnum:]" | head -c 25)

ODOO_ADMIN_PASSWD=$(cat /dev/urandom | tr -d -c "[:alnum:]" | head -c 25)
EOL
fi

if [ -z $(grep "DOB_TAG=" ".env") ]; then
  echo -e "\033[0;32mAdding DOB_TAG to .env\033[0m"
  if [ -z "$CI_PROJECT_ID" ]; then
    echo -e "\nDOB_TAG=$(pwd | sha256sum | head -c 10)" >> .env
  else
    echo -e "\nDOB_TAG=$CI_PROJECT_ID" >> .env
  fi
fi

if [ ! -f "odoo/odoo.local.yaml" ]; then
  echo -e "\033[0;32mGenerating minimal odoo.local.yaml\033[0m"
  cat > odoo/odoo.local.yaml <<EOL
# Machine specific configuration file
bootstrap:
  extend: odoo.project.yaml
EOL
fi
