#!/usr/bin/env bash
if [ ! -d "filestore" ]; then
  echo -e "\033[0;32mCreating filestore directory\033[0m"
  mkdir filestore
fi

if [ ! -d "ssh" ]; then
  echo -e "\033[0;32mCreating ssh directory\033[0m"
  mkdir ssh
  echo -e "\033[0;32mLinking ssh keys\033[0m"
  ln -P ~/.ssh/* ssh/
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

if [ ! -f "odoo/odoo.local.yaml" ]; then
  echo -e "\033[0;32mGenerating minimal odoo.local.yaml\033[0m"
  cat > odoo/odoo.local.yaml <<EOL
# Machine specific configuration file
bootstrap:
  extend: odoo.project.yaml
EOL
fi
