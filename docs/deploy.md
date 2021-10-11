## Autonomous deployments

For a fully autonomous deployments you have to build using the build stage `deploy` to
include everything for a self-containing image. On the start up you need to change the
command to `bash -c "odoo init && odoo update && odoo run"` to run all required steps.

Following folders of the containers must be mapped to volumes to ensure a persistent
state:

`/srv/odoo/filestore` .. Contains the Odoo filestore and sessions

`/srv/odoo/.ssh` .. Contains the SSH keys needed to fetch private repositories

`/srv/odoo/odoo/odoo.local.yaml` .. To make some instance specific settings (optional)
