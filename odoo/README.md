Bootstrap odoo
==============

Yaml based Odoo deployment tool.

Minimal configuration
---------------------

Minimal YAML configuration file `odoo.local.yaml`. This is optional and only necessary to overwrite predefined settings locally:

```
# Machine specific configuration file
bootstrap:
  extend: odoo.project.yaml
```

Files
-----
* `apt.txt` .. Debian package dependencies
* `odoo.default.yaml` .. Default settings for the `odoo.cfg`
* `odoo.local.yaml` .. Machine specific configuration file
* `odoo.project.yaml` .. Project specific configuration file
* `odoo.yaml` .. General configuration file
* `requirements.txt` .. Requirements for the bootstrapping. Do not use for odoo dependencies.
* `versions.txt` .. Python dependencies for odoo. Used for freezing.

Configuration
-------------

The main configuration is stored in .yaml files extended and merged together. It's possible to access other parts of the configuration using the `${...}` syntax (e.g. `${odoo:version}`). Below are the important sections described.

```
bootstrap -> dict
  - Basic bootstrap configuration
bootstrap:coverage -> bool
  - Enable/disable the coverage report when running tests
bootstrap:extend -> str or list
  - Extend the configuration with another file which will be loaded in order
bootstrap:mode -> str or list
  - Possibility to define different modes/environments
  - Modes are used to conditionally load modules
  - Uses environment BOOTSTRAP_MODE if set
bootstrap:odoo -> str
  - Path to the odoo instance
bootstrap:repo -> dict
  - Default definition of the repositories which is getting merged
  - Simplifies the definition of repositories by only defining differences
bootstrap:version -> str
  - Version of the database used for the migration

modules: -> list
  - List of modules to load with 2 options
  - Using a dictionary only loads modules when in one of the given modes

odoo -> dict
  - Basic odoo configuration
odoo:addons_path -> list
  - List of additional directories with odoo modules
odoo:options -> dict
  - Odoo configuration options which are getting compiled to etc/odoo.cfg
  - Can replace the configuration key with the ODOO_key (upper case) environment variable
odoo:users -> dict
  - Dictionary of user:password mappings
  - Sets the password of the specific user on initialization of the database
odoo:version -> str
  - Odoo version to use
  - Uses environment ODOO_VERSION if set

repos -> dict
  - Configuration of the repositories to load
  - Check git-aggregator for more
```

Migration
---------

Next to the module migrations you can create the `pre_install.py`, `pre_update.py` and/or `post_update.py` scripts for full flexibility. These scripts need the following interface:

```
def migrate(env, db_version):
    pass
```
