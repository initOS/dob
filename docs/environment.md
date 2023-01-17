## Environment variables of `.env`

- BOOTSTRAP_MODE .. Environment mode
- BOOTSTRAP_DEBUGGER .. Specify the debugger to use
  - Possible options: debugpy, dev (Odoo dev_mode)
- DB_PASSWORD .. Required. Postgres password of the database user.
- DB_VERSION .. Postgres version to use. If not set `latest`
- ODOO_CONFIG .. Name of the Odoo configuration file. Default is `odoo.cfg`
- ODOO_VERSION .. Odoo version to use with the format `x.0`
- ODOO\_\* .. Odoo configuration variables. See `odoo.default.yaml`
- Ports .. Ports of the hosts. Recommended syntax <ip>:<port>

  - HTTP_PORT .. Regular HTTP port. Default is `127.0.0.1:8069`.
  - HTTP_LONGPOLLING_PORT .. Longpolling port. Default is `127.0.0.1:8072`.
  - MAILHOG_PORT .. HTTP port of the mailsink. Default is `127.0.0.1:8025`.
  - DATABASE_PORT .. Developer only access to the database. Default is `6543`.
  - DEBUGPY_PORT .. Developer only. Specify the host port. Default is `5678`.
