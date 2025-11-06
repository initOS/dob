## Available commands

- `odoo`

  - Generic management tool for Odoo
  - See --help for more information

- `odoo init [options]`

  - Generation of the Odoo configuration file
  - Checking out of the repositories
  - Private Repositories require a valid ssh-agent. See below

- `odoo freeze`

  - Freeze the python packages into the `versions.txt`
  - Freeze repository commits into the the `odoo.versions.yaml`

- `odoo config`

  - Compile the configuration and show the merged result

- `odoo generate`

  - Generation of the Odoo configuration file

- `odoo shell [options]`

  - Start an odoo shell passing the additional parameter

- `odoo test [options]`

  - Start unittests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Coverage report can be created if `bootstrap:coverage` is set
  - Runs pytest under the hood and won't recognize odoos test arguments
  - Pass the location of the module inside of the container
    - Modules loaded from a repository are available inside of `/tmp/addons/`
    - Modules inside of `odoo/src/` are located under `/srv/odoo/odoo/src/`
  - Also check `-k` argument of pytest to filter specific tests

- `odoo black [options]`

  - Start black tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Only if `black` is installed

- `odoo eslint [options]`

  - Start eslint tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`

- `odoo flake8 [options]`

  - Start flake8 tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Only if `flake8` is installed

- `odoo isort [options]`

  - Start isort tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Only if `isort` is installed

- `odoo ruff [options]`

  - Start ruff check passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Only if `ruff` is installed

- `odoo ruff-format [options]`

  - Start ruff format passing the given parameter
  - Runs only on files specified in `odoo:addons_path`
  - Only if `ruff` is installed

- `odoo prettier [options]`

  - Start prettier tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`

- `odoo pylint [options]`

  - Start pylint tests passing the given parameter
  - Runs only on files specified in `odoo:addons_path`

- `odoo update [options] [modules]`

  - Generation of the Odoo configuration file
  - Initialize the database
  - Run `pre_install.py` script
  - Install all not installed modules
  - Run `pre_update.py` script
  - Updates all/changed/listed modules
  - Run `post_update.py` script
  - Update database version

- `odoo run [options]`

  - Start odoo and pass the options directly to Odoo
  - Use `docker-compose up` instead to expose the ports

- `odoo action [action] [options]`

  - Run an action on the database (e.g. anonymize, defuse)

- `psql`, `pg_dump`, `pg_restore`, `pg_activity`, `createdb`, `dropdb`
  - Postgres utitilies
  - Generating compressed dumps using `pg_dump` needs the `-T` option of
    `docker-compose exec/run`.

### Private Repositories and ssh-agent

If private repositories are used for additional Odoo modules an ssh-agent is required
during the `init` command. The following code initializes the ssh-agent and add all
available SSH keys to it:

```
$ eval $(ssh-agent -s)
$ ssh-add
```
