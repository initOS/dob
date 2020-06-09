#!/usr/bin/env python3
import argparse
import os
import re
import sys
import threading
import traceback
from argparse import ArgumentParser
from configparser import ConfigParser
from contextlib import closing, contextmanager
from multiprocessing import cpu_count
from subprocess import PIPE, Popen

# pylint: disable=import-error,wrong-import-order
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
             "c(onfig), i(nit), r(un), s(hell), t(est), u(pdate), f(reeze)"
             "flake8, pylint",
        choices=(
            "c", "config", "i", "init", "s", "shell", "t", "test",
            "u", "update", "r", "run", "f", "freeze", "flake8", "pylint",
        ),
    )
    base.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def load_config_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s config [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
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
        "-versions", action="store_false", default=True,
        help="Skip the bootstrapping of the versions.txt",
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


def load_test_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s test [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def load_update_arguments(args):
    parser = ArgumentParser(
        usage="%(prog)s update [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", dest="cfg", default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "--all", action="store_true", default=False,
        help="Update all modules instead of only changed ones",
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
    return output.strip() if output else ""


def info(msg, *args):
    """ Output a green colored info message """
    print(f"\x1b[32m{msg % args}\x1b[0m")


def warn(msg, *args):
    """ Output a yellow colored warning message """
    print(f"\x1b[1;33m{msg % args}\x1b[0m")


def error(msg, *args):
    """ Output a red colored error """
    print(f"\x1b[31m{msg % args}\x1b[0m")


def merge(a, b):
    """ Merges dicts and lists from the configuration structure """
    if isinstance(a, dict) and isinstance(b, dict):
        res = {}
        for key in set(a).union(b):
            if key not in a:
                res[key] = b[key]
            elif key not in b:
                res[key] = a[key]
            else:
                res[key] = merge(a[key], b[key])
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

    def set(self, *key, value=None):
        """ Set a specific value of the configuration """
        data = self.config
        for k in key[:-1]:
            data = data[k]

        data[key[-1]] = value

    def dump(self):
        """ Simply output the rendered configuration file """
        print(yaml.dump(self.config))

    def _load_config(self, cfg):
        """ Load and process a configuration file """
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
        self.config = merge(self.config, options)

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
        return True

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
            key: merge(default, value)
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

    def generate_requirements(self):
        """ Generate an initial versions.txt for python packages """
        if os.path.isfile("versions.txt"):
            info("versions.txt already exists")
            return

        # Get the requirements of all repositories
        info("Generating requirements")
        requirements = set()
        for path, repo in self.get("repos", default={}).items():
            info(f" * {path}")
            if repo.get("requirements"):
                reqs = self._read(os.path.join(path, "requirements.txt"), [])
                requirements.update(reqs)

        # Create the requirement file
        if requirements:
            with open("versions.txt", "w+") as fp:
                for req in sorted(requirements):
                    fp.write(req + "\n")

    def generate_config(self):
        """ Generate the Odoo configuration file """
        info("Generating configuration file")
        cp = ConfigParser()

        # Generate the configuration with the sections
        for sec, section in sorted(self.get("odoo", default={}).items()):
            if isinstance(section, dict):
                cp.add_section(sec)

                for key, value in sorted(section.items()):
                    if isinstance(value, (set, list)):
                        cp.set(sec, key, ",".join(map(str, value)))
                    elif value is None:
                        cp.set(sec, key, "")
                    else:
                        cp.set(sec, key, str(value))

        # Write the configuration
        with open('etc/odoo.cfg', 'w+') as fp:
            cp.write(fp)

    def install_packages(self):
        """ Install all packages from the versions.txt """
        if not os.path.isfile("versions.txt"):
            info("Missing versions.txt. You should freeze.")
            return

        info("Installing packages")
        cmd = ("-m", "pip", "install", "-r", "versions.txt")
        call(sys.executable, *cmd, pipe=False)

    def freeze(self):
        """ Freeze the python packages in the versions.txt """
        if os.path.isfile("versions.txt"):
            answer = input("Do you want to overwrite the versions.txt? [y/N] ")
            if answer.lower() != "y":
                return

        info("Freezing packages")
        versions = call(sys.executable, "-m", "pip", "freeze")
        with open("versions.txt", "w+") as fp:
            fp.write(versions)

    def init(self, args):
        """ Initialize the environment """
        args, _ = load_init_arguments(args)

        if args.config:
            self.generate_config()

        if args.repos:
            self.bootstrap(args)

        if args.versions:
            self.generate_requirements()

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
        sys.exit(shell.run(["-c", os.path.abspath("etc/odoo.cfg")]))

    def start(self, args):
        """ Start Odoo """
        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        from odoo.cli.server import Server
        server = Server()
        sys.exit(server.run(["-c", os.path.abspath("etc/odoo.cfg")] + args))

    def ci(self, ci, args):
        """ Run CI tests """
        # Always include this script in the tests
        args.append("bootstrap.py")

        for path in self.get("odoo", "addons_path", default=[]):
            args.append(path)

        sys.exit(call(sys.executable, "-m", ci, *args))

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

        # Load the odoo configuration
        with odoo.api.Environment.manage():
            cfg = os.path.abspath("etc/odoo.cfg")
            config.parse_config(["-c", cfg])
            odoo.cli.server.report_configuration()
            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result:
                sys.exit(result)

        # Create the coverage report
        call(sys.executable, "-m", "coverage", "html")
        sys.exit()

    def update_all(self, db_name, blacklist=None):
        """ Update all modules """
        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        info("Updating all modules")
        modules = self.get_modules().difference(blacklist or [])
        config["init"] = {}
        config["update"] = dict.fromkeys(modules, 1)
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

        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        cfg = os.path.abspath("etc/odoo.cfg")
        config.parse_config(["-c", cfg])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]
        with odoo.api.Environment.manage():
            # Ensure that the database is initialized
            db = odoo.sql_db.db_connect(db_name)
            with closing(db.cursor()) as cr:
                if not odoo.modules.db.is_initialized(cr):
                    info("Initializing the database")
                    odoo.modules.db.initialize(cr)
                    cr.commit()

            # Execute the pre install script
            self._run_migration(db_name, pre_install)

            # Install all modules
            info("Installing all modules")
            uninstalled = self.get_uninstalled_modules(db_name)
            if uninstalled:
                config["init"] = dict.fromkeys(uninstalled, 1)
                config["update"] = {}
                odoo.modules.registry.Registry.new(db_name, update_module=True)

            # Execute the pre update script
            self._run_migration(db_name, pre_update)

            # Update all modules which aren't installed before
            if args.all:
                self.update_all(db_name, uninstalled)
            else:
                self.update_changed(db_name, uninstalled)

            # Execute the post update script
            self._run_migration(db_name, post_update)

            # Write the version into the database
            with self.env(db_name) as env:
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
        load_config_arguments(left)
        env.dump()
    elif args.command in ("f", "freeze"):
        env.freeze()
    elif args.command in ("i", "init"):
        env.init(left)
    elif args.command in ("s", "shell"):
        env.shell(left)
    elif args.command in ("t", "test"):
        env.test(left)
    elif args.command in ("flake8", "pylint"):
        env.ci(args.command, left)
    elif args.command in ("u", "update"):
        env.update(left)
    elif args.command in ("r", "run"):
        env.start(left)
    elif show_help:
        load_arguments(["--help"])
    else:
        error("Unknown command")
        load_arguments(["--help"])
