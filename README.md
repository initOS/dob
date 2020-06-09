dob (Docker Odoo Bootstrap)
===========================

YAML based odoo bootstrap within docker. Docker sets up the environment odoo will be built into, installs Debian and Python packages. The further tooling is done by the `bootstrap.py` script. See the usage. For a documentation of the main YAML structure see the `odoo/README.md`.

Minimal configuration
---------------------
Minimal `.env` configuration file. See below for more informations:

```
DB_PASSWORD=...
BOOTSTRAP_MODE=dev
```

Usage
-----

Use `-f docker-compose.yaml -f mailhog.yaml` after `docker-compose` if a mailsink is needed.

```
$ ln -P ~/.ssh ssh
$ docker-compose build
$ docker-compose run --rm odoo odoo init
$ docker-compose up

```

Docker
------

* `docker-compose build`
  - Build or rebuild the images

* `docker-compose up [options] [container]`
  - Create and start the containers

* `docker-compose down`
  - Put down running containers

* `docker-compose kill`
  - Kill containers

* `docker-compose exec <container> <command> [args]`
  - Execute the command in the running container
  - File paths must specify a file within the container
  - See below for the commands

* `docker-compose run --rm <container> <command> [args]`
  - Start a new container, execute the command and remove the container afterwards
  - File paths must specify a file within the container
  - See below for the commands

Available commands
------------------

* `odoo`
  - Generic management tool for Odoo
  - See --help for more information

* `odoo init [options]`
  - Initialization of the environment including
    * Generation of configuration file `etc/odoo.cfg`
    * Checking out of the repositories
    * Initial generation of versions.txt file
      + Can aggregate the requirements.txt file of all repositories
      + Experimental because of specifier
    * Creation of the scripts

* `odoo freeze`
  - Freeze the python packages into the versions.txt

* `odoo config`
  - Compile the configuration and show the merged result

* `odoo shell [options]`
  - Start an odoo shell passing the additional parameter

* `odoo test [options]`
  - Start unittests passing the given parameter
  - Runs only on files specified `odoo:addons_path`
  - Coverage report can be created if `bootstrap:coverage` is set

* `odoo flake8 [options]`
  - Start flake8 tests passing the given parameter
  - Runs only on files specified `odoo:addons_path`

* `odoo pylint [options]`
  - Start pylint tests passing the given parameter
  - Runs only on files specified `odoo:addons_path`

* `odoo update [options]`
  - Initialize the database
  - Install all not installed modules
  - Run pre_migrate script
  - Updates all/changed modules
  - Run post_migrate script
  - Update database version

* `odoo run [options]`
  - Start odoo and pass the options directly to Odoo

* `psql`, `pg_dump`, `pg_restore`, `pg_activity`, `createdb`, `dropdb`
  - Postgres utitilies

Environment variables of `.env`
-------------------------------
  * PGPASSWORD .. Required. Postgres password of the database user.
  * DB_VERSION .. Postgres version to use. If not set `latest`
  * ODOO_VERSION .. Odoo version to use with the format `x.0`
  * ODOO_* .. Odoo configuration variables. See `odoo.default.yaml`
  * Ports .. Ports of the hosts. Recommended syntax <ip>:<port>
    - HTTP_PORT .. Regular HTTP port. Default is `127.0.0.1:8069`.
    - HTTP_LONGPOLLING_PORT .. Longpolling port. Default is `127.0.0.1:8072`.
    - MAILHOG_PORT .. HTTP port of the mailsink. Default is `127.0.0.1:8025`.