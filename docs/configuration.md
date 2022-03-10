## Minimal configuration

Minimal YAML configuration file `odoo.local.yaml`. This is optional and only necessary
to overwrite predefined settings locally:

```
# Machine specific configuration file
bootstrap:
  extend: odoo.project.yaml
```

## Files

- `apt.txt` .. Debian package dependencies
- `odoo.default.yaml` .. Default settings for the `odoo.cfg`
- `odoo.local.yaml` .. Machine specific configuration file
- `odoo.project.yaml` .. Project specific configuration file
- `odoo.yaml` .. General configuration file
- `requirements.txt` .. Requirements for the bootstrapping.
- `versions.txt` .. Python dependencies for odoo. Used for freezing.

## Configuration

The main configuration is stored in .yaml files extended and merged together. It's
possible to access other parts of the configuration using the `${...}` syntax (e.g.
`${odoo:version}`). Below are the important sections described.

```
actions -> dict
  - DB actions defined which need to run (see below)

bootstrap -> dict
  - Basic bootstrap configuration
bootstrap:blacklist -> list
  - Blacklist files for the CI
  - Glob patterns can be used
  - Requires doblib>=0.8
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
  - Can replace the configuration key with the ODOO_key (upper case) environment
    variable
odoo:users -> dict
  - Dictionary of user:password mappings
  - Sets the password of the specific user on initialization of the database
odoo:version -> str
  - Odoo version to use
  - Uses environment ODOO_VERSION if set

repos -> dict
  - Configuration of the repositories to load
  - Check [git-aggregator](https://github.com/acsone/git-aggregator) for more
```

## Database actions

Actions can be defined to alter the database to be able to run specific things on the
database. Actions are defined using a name and a dictionary in the `actions` section.

```
<action_name>:
  action: .. Action type. Either update, insert or delete with update as default.
  model: .. Odoo model. Required.
  domain: .. Search domain to specify specific records. Default is []
  values: .. Dictionary to define the new value of each field. Required.
  context .. Dictionary to update the context of the environment for the action.
  references: .. Dictionary of unique identifiers to XML references of Odoo
  chunk: .. Update or delete is done in chunks of given size. Default is 0 (no chunks).
  truncate: .. The delete action uses truncate .. cascade on the table instead.
```

Values can be defined in multiple ways: directly or as a dictionary. Depending on the
field type the dictionary option offers parameter for the manipulation of the field.

```
<field>:
  field: .. A field name to copy the value from.
  lower: .. The lower bounds for randomized values.*
  upper: .. The upper bounds for randomized values.*
  prefix: .. Prefix to add for the new value.**
  suffix: .. Suffix to add for the new value.**
  length: .. The length of the randomized value.**
  uuid: .. Generate a new uuid. Supported options are 1 or 4.**

*  Only available for Integer, Float, Date, Datetime
** Only available for Char, Html, Text
```

References are defined as a mapping where is the key is getting used to replace values
in the `domain` and `values` of the action with the id of the record referenced by the
xmlid of Odoo.

## Migration

Next to the module migrations you can create the `pre_install.py`, `pre_update.py`
and/or `post_update.py` scripts for full flexibility. These scripts need the following
interface:

```
def migrate(env, db_version):
    pass
```
