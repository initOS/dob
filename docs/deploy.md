## Autonomous deployments

For a fully autonomous deployments you have to build using the build stage `deploy` to
include everything for a self-containing image. On the start up you need to change the
command to `bash -c "odoo update && odoo run"` to run all required steps in atleast one
container while others can run `bash -c "odoo run"`.

Following folders of the containers must be mapped to volumes to ensure a persistent
state:

`/srv/odoo/filestore` .. Contains the Odoo filestore and sessions

`/srv/odoo/odoo/odoo.local.yaml` .. To make some instance specific settings (optional)

### Building the image

SSH access to the private repositories is required during the build process.

```bash
ssh-agent
docker build --build-arg=PYTHON_VERSION=3.10 --ssh default --target deploy -t <tag> .
```
