#!/usr/bin/env python3
# © 2020 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import glob
import os
import random
import re
import string
import sys
import threading
import traceback
import uuid
from argparse import ArgumentParser
from configparser import ConfigParser
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from multiprocessing import cpu_count
from subprocess import PIPE, Popen

# pylint: disable=import-error,wrong-import-order,print-used
import pytest
import yaml
from git_aggregator.config import get_repos
from git_aggregator.main import match_dir
from git_aggregator.repo import Repo
from git_aggregator.utils import ThreadNameKeeper

try:
    import pre_install
except ImportError:
    pre_install = None

try:
    import pre_update
except ImportError:
    pre_update = None

try:
    import post_update
except ImportError:
    post_update = None

# pylint: enable=import-error,wrong-import-order
try:
    from Queue import Queue, Empty as EmptyQueue
except ImportError:
    from queue import Queue, Empty as EmptyQueue


ALNUM = string.ascii_letters + string.digits
ODOO_CONFIG = os.path.abspath("etc/odoo.cfg")
SECTION = "bootstrap"

# Mapping of environment variables to configurations
ENVIRONMENT = {
    "ODOO_VERSION": ("odoo", "version"),
    "BOOTSTRAP_MODE": (SECTION, "mode"),
}


def get_config_file():
    """ Favor a odoo.local.yaml if exists """
    for file in ["odoo.local.yaml", "odoo.project.yaml"]:
        if os.path.isfile(file):
            return file
    error("No configuration file found.")
    return None


def load_arguments(args):
    """ Parse the command line options """
    parser = ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    base = parser.add_argument_group("Basic")
    base.add_argument(
        "command", metavar="command", nargs="?",
        help="Command to use. Possible choices: "
             "c(onfig), i(nit), r(un), s(hell), t(est), u(pdate), f(reeze), "
             "flake8, pylint, eslint, defuse",
        choices=(
            "c", "config", "i", "init", "s", "shell", "t", "test",
            "u", "update", "r", "run", "f", "freeze", "flake8", "pylint",
            "eslint", "defuse",
        ),
    )
    base.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def load_default_arguments(command, args):
    parser = ArgumentParser(
        usage=f"%(prog)s {command} [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def load_freeze_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s freeze [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "--mode", choices=("all", "ask", "skip"), default="ask",
        help="Mode of the freeze with\n"
             "`all` .. Freeze all and don't ask\n"
             "`skip` .. Skip existing files\n"
             "`ask` .. Ask if a file would be overwritten",
    )
    parser.add_argument(
        "-packages", action="store_false", default=True,
        help="Skip the packages",
    )
    parser.add_argument(
        "-repos", action="store_false", default=True,
        help="Skip the repositories",
    )
    return parser.parse_known_args(args)


def load_init_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s init [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "-config", action="store_false", default=True,
        help="Skip the bootstrapping of the configuration",
    )
    parser.add_argument(
        "-repos", action="store_false", default=True,
        help="Skip the bootstrapping of the repositories",
    )
    parser.add_argument(
        "-f", "--force", action="store_true", default=False,
        help="Force the bootstrapping of repositories by stashing",
    )
    parser.add_argument(
        "-d", "--dirmatch", dest="dirmatch", type=str, nargs="?",
        help="Only bootstrap repositories with a matching glob",
    )
    parser.add_argument(
        "-j", "--jobs", dest="jobs", default=cpu_count(), type=int,
        help="Number of jobs used for the bootstrapping. Default %(default)s",
    )
    return parser.parse_known_args(args)


def load_shell_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s shell [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "file", nargs="?", help="File to execute",
    )
    return parser.parse_known_args(args)


def load_update_arguments(args):
    def no_flags(x):
        if x.startswith("-"):
            raise argparse.ArgumentTypeError("Invalid argument")
        return x

    parser = ArgumentParser(
        usage="%(prog)s update [options] [modules ...]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "modules", nargs=argparse.REMAINDER, type=no_flags, default=[],
        help="Module to update",
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "--all", action="store_true", default=False,
        help="Update all modules instead of only changed ones",
    )
    parser.add_argument(
        "--passwords", action="store_true", default=False,
        help="Forcefully overwrite passwords",
    )
    return parser.parse_known_args(args)


def call(*cmd, cwd=None, pipe=True):
    """ Call a subprocess and return the stdout """
    proc = Popen(
        cmd,
        cwd=cwd,
        stdout=PIPE if pipe else None,
        universal_newlines=True,
    )
    output = proc.communicate()[0]
    if pipe:
        return output.strip() if output else ""
    return proc.returncode


def info(msg, *args):
    """ Output a green colored info message """
    print(f"\x1b[32m{msg % args}\x1b[0m")


def warn(msg, *args):
    """ Output a yellow colored warning message """
    print(f"\x1b[33m{msg % args}\x1b[0m")


def error(msg, *args):
    """ Output a red colored error """
    print(f"\x1b[31m{msg % args}\x1b[0m")


class Defuser:
    """ Defuser class """

    def defuse(self, rec, name, **kw):
        field = kw.get("field")
        if field:
            return rec[field]

        field_type = rec._fields[name].type
        if field_type == "boolean":
            return self._boolean(rec, name, **kw)
        if field_type == "integer":
            return self._integer(rec, name, **kw)
        if field_type in ("float", "monetary"):
            return self._float(rec, name, **kw)
        if field_type == "date":
            return self._date(rec, name, **kw)
        if field_type == "datetime":
            return self._datetime(rec, name, **kw)
        if field_type in ("char", "html", "text"):
            return self._text(rec, name, **kw)
        raise TypeError("Field type is not supported by defuser")

    def _boolean(self, rec, name, **kw):
        field = kw.get("field")
        # Use the value of a different field
        if field:
            return bool(rec[field])
        return random.choice((False, True))

    def _integer(self, rec, name, **kw):
        lower = kw.get("lower", None)
        upper = kw.get("upper", None)
        field = kw.get("field", None)
        # Use the value of a different field
        if field:
            return rec[field]
        # Randomize the value
        if isinstance(lower, int) and isinstance(upper, int):
            return random.randint(lower, upper)
        raise TypeError("Lower and upper bounds must be integer")

    def _float(self, rec, name, **kw):
        lower = kw.get("lower", 0.0)
        upper = kw.get("upper", 1.0)
        field = kw.get("field", None)
        # Use the value of a different field
        if field:
            return rec[field]
        # Randomize the value
        return random.random() * (upper - lower) + lower

    def _text(self, rec, name, **kw):
        # pylint: disable=attribute-deprecated
        prefix = kw.get("prefix", "")
        suffix = kw.get("suffix", "")
        length = kw.get("length", None)
        field = kw.get("field", None)
        vuuid = kw.get("uuid", None)
        # Support for uuid1 and uuid4
        if vuuid == 1:
            return str(uuid.uuid1())
        if vuuid == 4:
            return str(uuid.uuid4())
        # Use the value of a different field
        if isinstance(field, str):
            return f"{prefix}{rec[field]}{suffix}"
        # Randomize the value
        if isinstance(length, int) and length > 0:
            return prefix + "".join(random.choices(ALNUM, k=length)) + suffix
        return prefix + rec[name] + suffix

    def _datetime(self, rec, name, **kw):
        lower = kw.get("lower", datetime(1970, 1, 1))
        upper = kw.get("upper", datetime.now())
        field = kw.get("field", None)
        if field:
            return rec[field]
        diff = upper - lower
        return lower + timedelta(seconds=random.randint(0, diff.seconds))

    def _date(self, rec, name, **kw):
        lower = kw.get("lower", date(1970, 1, 1))
        upper = kw.get("upper", date.today())
        field = kw.get("field", None)
        if field:
            return rec[field]
        return lower + timedelta(days=random.randint(0, (upper - lower).days))


def merge(a, b, *, replace=None):
    """ Merges dicts and lists from the configuration structure """
    if isinstance(a, dict) and isinstance(b, dict):
        if not replace:
            replace = set()

        res = {}
        for key in set(a).union(b):
            if key not in a:
                res[key] = b[key]
            elif key not in b:
                res[key] = a[key]
            elif key in replace:
                res[key] = b[key]
            else:
                res[key] = merge(a[key], b[key], replace=replace)
        return res

    if isinstance(a, list) and isinstance(b, list):
        return a + b

    if isinstance(a, set) and isinstance(b, set):
        return a.union(b)

    return b


def aggregate_repo(repo, args, sem, err_queue):
    """ Aggregate one repo according to the args """
    try:
        dirmatch = args.dirmatch
        if not match_dir(repo.cwd, dirmatch):
            return
        repo.aggregate()
    except Exception:
        err_queue.put_nowait(sys.exc_info())
    finally:
        sem.release()


def raise_keyboard_interrupt(*a):
    raise KeyboardInterrupt()


class Version:
    """ Class to read and and compare versions. Instances are getting
    passed to the migration scripts """

    def __init__(self, ver):
        if isinstance(ver, Version):
            self.version = ver.version
        elif isinstance(ver, str):
            self.version = tuple(
                int(x) if x.isdigit() else x
                for x in ver.split(".")
            )
        elif isinstance(ver, int) and not isinstance(ver, bool):
            self.version = (ver,)
        else:
            self.version = tuple()

    def __str__(self):
        return ".".join(map(str, self.version))

    def __eq__(self, other):
        return self.version == Version(other).version

    def __lt__(self, other):
        return self.version < Version(other).version

    def __le__(self, other):
        return self.version <= Version(other).version

    def __gt__(self, other):
        return self.version > Version(other).version

    def __ge__(self, other):
        return self.version >= Version(other).version


# pylint: disable=too-many-public-methods
class Environment:
    """ Bootstrap environment """

    def __init__(self, cfg):
        os.makedirs("etc", exist_ok=True)

        info("Loading configuration file")
        self.config = {}
        self._load_config(cfg)
        self._load_config("odoo.versions.yaml", False)
        self._post_process_config()

    def _post_process_config(self):
        """ Post process the configuration by replacing variables """
        regex = re.compile(r'\$\{(?P<var>(\w|:)+)\}')

        def repl(match, sub=True):
            """ Replaces the matched parts with the variable """
            data = match.groupdict()
            var = data.get("var")
            if not var:
                raise SyntaxError()
            result = self.get(*var.split(':'))
            return str(result) if sub else result

        def sub_dict(data):
            """ Substitute variables in dictionaries """
            tmp = {}
            for sec, section in data.items():
                if isinstance(section, str):
                    tmp[sec] = sub_str(section)
                elif isinstance(section, list):
                    tmp[sec] = sub_list(section)
                elif isinstance(section, dict):
                    tmp[sec] = sub_dict(section)
                else:
                    tmp[sec] = section
            return tmp

        def sub_str(line):
            """ Substitute variables in strings """
            match = regex.fullmatch(line)
            return repl(match, False) if match else regex.sub(repl, line)

        def sub_list(ls):
            """ Substitute variables in lists """
            tmp = []
            for x in ls:
                if isinstance(x, dict):
                    tmp.append(sub_dict(x))
                elif isinstance(x, str):
                    tmp.append(sub_str(x))
                elif isinstance(x, list):
                    tmp.append(sub_list(x))
                else:
                    tmp.append(x)
            return tmp

        # Include environment variables first for later substitutions
        for env, keys in ENVIRONMENT.items():
            if os.environ.get(env):
                self.set(*keys, value=os.environ[env])

        options = self.get("odoo", "options", default={})
        for key, value in options.items():
            options[key] = os.environ.get(f"ODOO_{key.upper()}") or value

        # Run the substitution on the configuration
        self.config = sub_dict(self.config)

        # Combine the addon paths
        current = set(self.get("odoo", "addons_path", default=[]))
        current.update({
            section.get("addon_path", sec)
            for sec, section in self.get("repos", default={}).items()
        })

        # Generate the addon paths
        current = set(map(os.path.abspath, current))
        self.set("odoo", "options", "addons_path", value=current)

    def _read(self, filename, default=None):
        """ Read a specific file within the repository """
        if not os.path.isfile(filename):
            return default

        result = set()
        for line in open(filename, "r").read().splitlines():
            line = line.strip()
            if line and line[0].isalpha():
                result.add(line)
        return result

    def _run_migration(self, db_name, script):
        """ Run a migration script by executing the migrate function """
        if script:
            info(f"Executing {script.__name__.replace('_', ' ')} script")
            with self.env(db_name) as env:
                version = Version(env["ir.config_parameter"].get_param(
                    "db_version", False
                ))
                script.migrate(env, version)

    def get(self, *key, default=None):
        """ Get a specific value of the configuration """
        data = self.config
        try:
            for k in key:
                data = data[k]
            if data is None:
                return default
            return data
        except KeyError:
            return default

    def opt(self, *key, default=None):
        """ Short cut to directly access odoo options """
        return self.get("odoo", "options", *key, default=default)

    def set(self, *key, value=None):
        """ Set a specific value of the configuration """
        data = self.config
        for k in key[:-1]:
            data = data[k]

        data[key[-1]] = value

    def dump(self):
        """ Simply output the rendered configuration file """
        print(yaml.dump(self.config))

    def _load_config(self, cfg, raise_if_missing=True):
        """ Load and process a configuration file """
        if not os.path.isfile(cfg) and not raise_if_missing:
            warn(f" * {cfg}")
            return

        info(f" * {cfg}")
        with open(cfg) as fp:
            options = yaml.load(fp, Loader=yaml.FullLoader)

        # Load all base configuration files first
        extend = options.get(SECTION, {}).get("extend")
        if isinstance(extend, str):
            self._load_config(extend)
        elif isinstance(extend, list):
            for e in extend:
                self._load_config(e)
        elif extend is not None:
            raise TypeError(f"{SECTION}:extend must be str or list")

        # Merge the configurations
        self.config = merge(self.config, options, replace=["merges"])

    def _init_odoo(self):
        """ Initialize Odoo to enable the module import """
        path = self.get(SECTION, "odoo")
        if not path:
            error(f"No {SECTION}:odoo defined")
            return False

        path = os.path.abspath(path)
        if not os.path.isdir(path):
            error("Missing odoo folder")
            return False

        if path not in sys.path:
            sys.path.append(path)
        return path

    @contextmanager
    def env(self, db_name, rollback=False):
        """ Create an environment from a registry """
        # pylint: disable=C0415,E0401
        import odoo
        # Get all installed modules
        reg = odoo.registry(db_name)
        with closing(reg.cursor()) as cr:
            uid = odoo.SUPERUSER_ID
            ctx = odoo.api.Environment(cr, uid, {})['res.users'].context_get()

            yield odoo.api.Environment(cr, uid, ctx)

            if rollback:
                cr.rollback()
            else:
                cr.commit()

    def get_modules(self):
        """ Return the list of modules """
        modes = self.get(SECTION, "mode", default=[])
        modes = set(modes.split(',') if isinstance(modes, str) else modes)

        modules = set()
        for module in self.get("modules", default=[]):
            if isinstance(module, str):
                modules.add(module)
            elif isinstance(module, dict) and len(module) == 1:
                mod, mode = list(module.items())[0]
                if isinstance(mode, str) and mode in modes:
                    modules.add(mod)
                elif isinstance(mode, list) and modes.intersection(mode):
                    modules.add(mod)
            else:
                raise TypeError("modules:* must be str or dict of length 1")

        return modules

    def get_uninstalled_modules(self, db_name):
        """ Return the list of modules which aren't installed """
        with self.env(db_name, False) as env:
            domain = [("state", "=", "installed")]
            installed = env["ir.module.module"].search(domain).mapped("name")
            return self.get_modules().union(["base"]).difference(installed)

    def bootstrap(self, args):
        """ Bootstrap the git repositories using git aggregator """
        info("Bootstrapping repositories")

        # Mostly adapted from the git aggregator main module with integration
        # into the bootstrapping structure
        jobs = max(args.jobs, 1)
        threads = []
        sem = threading.Semaphore(jobs)
        err_queue = Queue()

        default = self.get(SECTION, "repo", default={})
        repos = {
            key: merge(default, value, replace=["merges"])
            for key, value in self.get("repos", default={}).items()
        }
        for repo_dict in get_repos(repos, args.force):
            if not err_queue.empty():
                break

            sem.acquire()
            r = Repo(**repo_dict)
            tname = os.path.basename(repo_dict['cwd'])

            if jobs > 1:
                t = threading.Thread(
                    target=aggregate_repo, args=(r, args, sem, err_queue),
                )
                t.daemon = True
                t.name = tname
                threads.append(t)
                t.start()
            else:
                with ThreadNameKeeper():
                    threading.current_thread().name = tname
                    aggregate_repo(r, args, sem, err_queue)

        for t in threads:
            t.join()

        if not err_queue.empty():
            while True:
                try:
                    exc_type, exc_obj, exc_trace = err_queue.get_nowait()
                except EmptyQueue:
                    break
                traceback.print_exception(exc_type, exc_obj, exc_trace)
            sys.exit(1)

    def generate_config(self):
        """ Generate the Odoo configuration file """
        info("Generating configuration file")
        cp = ConfigParser()

        # Generate the configuration with the sections
        options = self.get("odoo", "options", default={})
        for key, value in sorted(options.items()):
            if key == "load_language":
                continue
            if "." in key:
                sec, key = key.split(".", 1)
            else:
                sec = "options"

            if not cp.has_section(sec):
                cp.add_section(sec)

            if isinstance(value, (set, list)):
                cp.set(sec, key, ",".join(map(str, value)))
            elif value is None:
                cp.set(sec, key, "")
            else:
                cp.set(sec, key, str(value))

        # Write the configuration
        with open(ODOO_CONFIG, 'w+') as fp:
            cp.write(fp)

    def _defuse_delete(self, env, model, domain):
        """ Runs the delete defusing """
        if model in env:
            env[model].with_context(active_test=False).search(domain).unlink()

    def _defuse_update(self, env, model, domain, values):
        """ Runs the update defusing """
        if not values or model not in env:
            return

        records = env[model].with_context(active_test=False).search(domain)

        # Split the values in constant and dynamic
        const, dynamic = {}, {}
        for name, defuse_opt in values.items():
            if name not in records._fields:
                continue

            if isinstance(defuse_opt, dict):
                dynamic[name] = defuse_opt
            else:
                const[name] = defuse_opt

        # Handle the constant values
        if const:
            records.write(const)

        # Handle the dynamic values
        if dynamic:
            defuser = Defuser()
            for rec in records:
                vals = {}
                for name, defuse_opt in dynamic.items():
                    vals[name] = defuser.defuse(rec, name, **defuse_opt)
                rec.write(vals)

    def defuse(self):
        """ Defuses the database """
        if not self._init_odoo():
            return

        defuses = self.get("odoo", "defuse", default={})
        if not defuses:
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        config.parse_config(["-c", ODOO_CONFIG])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]

        info("Running defuse")
        with odoo.api.Environment.manage():
            with self.env(db_name) as env:
                for name, defuse in defuses.items():
                    info(f"Defuse {name}")

                    model = defuse.get("model")
                    if not isinstance(model, str):
                        error("Model must be string")
                        continue

                    domain = defuse.get("domain", [])
                    if not isinstance(domain, list):
                        error("Domain must be list")
                        continue

                    action = defuse.get("action", "update")
                    if action == "update":
                        values = defuse.get("values", {})
                        self._defuse_update(env, model, domain, values)
                    elif action == "delete":
                        self._defuse_delete(env, model, domain)
                    else:
                        error(f"Undefined action {action}")

    def _freeze_mode(self, file, mode="ask"):
        """ Return true if the file should be written/created """
        if not os.path.isfile(file):
            return True

        if mode == "skip":
            return False

        if mode == "ask":
            answer = input(f"Do you want to overwrite the {file}? [y/N] ")
            if answer.lower() != "y":
                return False

        return True

    def _freeze_packages(self, file, mode="ask"):
        """ Freeze the python packages in the versions.txt """
        if self._freeze_mode(file, mode):
            info("Freezing packages")
            versions = call(sys.executable, "-m", "pip", "freeze")
            with open(file, "w+") as fp:
                fp.write(versions)

    def _freeze_repositories(self, file, mode="ask"):
        """ Freeze the repositories """

        # Get the default merges dict from the configuration
        version = self.get(SECTION, "version", default="0.0")
        default_merges = self.get(
            SECTION, "repo", "merges", default=[f"origin {version}"],
        )

        # Get the used remotes and commits from the repositoriey
        commits = {}
        for path, repo in self.get("repos", default={}).items():
            # This will return all branches with "<remote> <commit>" syntax
            output = call(
                "git", "branch", "-va",
                "--format=%(refname) %(objectname)",
                cwd=path,
            )
            remotes = dict(line.split() for line in output.splitlines())

            # Aggregate the used commits from each specified merge
            tmp = []
            for remote in repo.get("merges", default_merges):
                name = f"refs/remotes/{remote.replace(' ', '/')}"
                remote = remote.split()[0]
                if name in remotes:
                    tmp.append(f"{remote} {remotes[name]}")

            if tmp:
                commits[path] = {"merges": tmp}

        if not commits:
            return

        # Output the suggestion in a proper format to allow copy & paste
        if self._freeze_mode(file, mode):
            info("Freeze repositories:")
            with open(file, "w+") as fp:
                fp.write(yaml.dump({"repos": commits}))

    def freeze(self, args):
        """ Freeze the python packages in the versions.txt """
        args, _ = load_freeze_arguments(args)

        if args.packages:
            self._freeze_packages("versions.txt", args.mode)

        if args.repos:
            self._freeze_repositories("odoo.versions.yaml", args.mode)

    def init(self, args):
        """ Initialize the environment """
        args, _ = load_init_arguments(args)

        if args.config:
            self.generate_config()

        if args.repos:
            self.bootstrap(args)

    def shell(self, args):
        """ Start an Odoo shell """
        args, left = load_shell_arguments(args)
        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        from odoo.cli.shell import Shell
        if args.file:
            sys.stdin = open(args.file, "r")
            sys.argv = [args.file] + left
        else:
            sys.argv = [""]

        shell = Shell()
        sys.exit(shell.run(["-c", ODOO_CONFIG, "--no-http"]))

    def start(self, args):
        """ Start Odoo without wrapper """
        path = self._init_odoo()
        if not path:
            return

        cmd = sys.executable, "odoo-bin", "-c", ODOO_CONFIG
        sys.exit(call(*cmd, *args, cwd=path))

    def ci(self, ci, args):
        """ Run CI tests """
        # Always include this script in the tests
        for path in self.get("odoo", "addons_path", default=[]):
            if ci == "pylint":
                args.extend(glob.glob(f"{path}/**/*.py", recursive=True))
            else:
                args.append(path)

        cmd = [sys.executable, "-m", ci]
        if ci == "pylint":
            args.extend(("--rcfile=.pylintrc", "dob.py"))
        elif ci == "eslint":
            cmd = ["eslint", "--no-error-on-unmatched-pattern"]
        else:
            args.append("dob.py")

        sys.exit(call(*cmd, *args, pipe=False))

    def test(self, args):
        """ Run tests """
        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Append needed parameter
        if self.get(SECTION, "coverage"):
            for path in self.get("odoo", "addons_path", default=[]):
                args.extend([f"--cov={path}", path])

            args.append("--cov-report=html")
            args.append("--cov-report=term")

        # Load the odoo configuration
        with odoo.api.Environment.manage():
            config.parse_config(["-c", ODOO_CONFIG])
            odoo.cli.server.report_configuration()
            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result and result != pytest.ExitCode.NO_TESTS_COLLECTED:
                sys.exit(result)
            sys.exit()

    def install_all(self, db_name, modules):
        """ Install all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        config["init"] = dict.fromkeys(modules, 1)
        config["update"] = {}
        config["overwrite_existing_translations"] = True
        without_demo = self.opt("without_demo", default=True)
        languages = self.opt("load_language")
        if languages and isinstance(languages, list):
            config["load_language"] = ",".join(languages)
        elif languages:
            config["load_language"] = languages

        odoo.modules.registry.Registry.new(
            db_name, update_module=True, force_demo=not without_demo,
        )

    def update_all(self, db_name, blacklist=None):
        """ Update all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        info("Updating all modules")
        modules = self.get_modules().difference(blacklist or [])
        config["init"] = {}
        config["update"] = dict.fromkeys(modules, 1)
        config["overwrite_existing_translations"] = True
        odoo.modules.registry.Registry.new(db_name, update_module=True)

    def update_changed(self, db_name, blacklist=None):
        """ Update only changed modules """
        info("Updating changed modules")
        with self.env(db_name, False) as env:
            model = env["ir.module.module"]
            if hasattr(model, "upgrade_changed_checksum"):
                model.upgrade_changed_checksum(True)
                return

        info("The module module_auto_update is needed. Falling back")
        self.update_all(db_name, blacklist)

    def update(self, args):
        """ Install/update Odoo modules """
        args, _ = load_update_arguments(args)

        self.generate_config()

        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        config.parse_config(["-c", ODOO_CONFIG])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]
        with odoo.api.Environment.manage():
            # Ensure that the database is initialized
            db = odoo.sql_db.db_connect(db_name)
            initialized = False
            with closing(db.cursor()) as cr:
                if not odoo.modules.db.is_initialized(cr):
                    info("Initializing the database")
                    odoo.modules.db.initialize(cr)
                    cr.commit()
                    initialized = True

            # Execute the pre install script
            self._run_migration(db_name, pre_install)

            # Get the modules to install
            if initialized:
                uninstalled = self.get_modules()
            else:
                uninstalled = self.get_uninstalled_modules(db_name)

            # Install all modules
            info("Installing all modules")
            if uninstalled:
                self.install_all(db_name, uninstalled)

            # Execute the pre update script
            self._run_migration(db_name, pre_update)

            # Update all modules which aren't installed before
            if args.modules:
                self.update_all(db_name, args.modules)
            elif args.all:
                self.update_all(db_name, uninstalled)
            else:
                self.update_changed(db_name, uninstalled)

            # Execute the post update script
            self._run_migration(db_name, post_update)

            # Finish everything
            with self.env(db_name) as env:
                # Set the user passwords if previously initialized
                users = self.get("odoo", "users", default={})
                if (initialized or args.passwords) and users:
                    info("Setting user passwords")
                    model = env["res.users"]
                    for user, password in users.items():
                        domain = [("login", "=", user)]
                        model.search(domain).write({"password": password})

                # Write the version into the database
                info("Setting database version")
                version = self.get(SECTION, "version", default="0.0")
                env["ir.config_parameter"].set_param("db_version", version)


if __name__ == "__main__":
    args = sys.argv[1:]
    show_help = "-h" in args or "--help" in args
    args = [x for x in args if x not in ("-h", "--help")]
    args, left = load_arguments(args)
    env = Environment(args.cfg)

    if show_help:
        left.append("--help")

    if args.command in ("c", "config"):
        load_default_arguments("config", left)
        env.dump()
    elif args.command in ("f", "freeze"):
        env.freeze(left)
    elif args.command in ("i", "init"):
        env.init(left)
    elif args.command in ("s", "shell"):
        env.shell(left)
    elif args.command in ("t", "test"):
        env.test(left)
    elif args.command in ("flake8", "pylint", "eslint"):
        env.ci(args.command, left)
    elif args.command in ("u", "update"):
        env.update(left)
    elif args.command in ("r", "run"):
        env.start(left)
    elif args.command in ("defuse",):
        env.defuse()
    elif show_help:
        load_arguments(["--help"])
    else:
        error("Unknown command")
        load_arguments(["--help"])
