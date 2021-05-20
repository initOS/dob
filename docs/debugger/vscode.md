## Required Extension
The `Python` extension needs to be installed before setting up the configuration.


## Configuration

The configuration file to set up debugpy debugger for VS Code is defined in
a `launch.json` file that's stored in a `.vscode` folder in your workspace.
Make sure that port 5678 is open.
The specific settings are described below:

```
name: Provides the name for the debug configuration that appears in the VS Code dropdown list.
type: Identifies the type of debugger to use; leave this set to python for Python code.
request: Specifies the mode in which to start debugging:
    1. launch: start the debugger on the file specified in program
    2- attach: attach the debugger to an already running process.
port: port used by the debugger.
host: the host that will be used.
pathMappings: maps the files on the server to the right files on local machine.
```

Copy these configurations to `launch.json` file.

```
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "port": 5678,
            "host": "localhost",
            "preLaunchTask": "dob start",
            "postDebugTask": "dob stop",
            "pathMappings": [
                {
                "localRoot": "${workspaceFolder}",
                "remoteRoot": "/srv/odoo"
                }
            ]
        }
    ]
}
```

In order to start and stop the container by hitting F5, a `tasks.json` file
needs to be created in a `.vscode` folder in your workspace.
Copy these configurations to `tasks.json` file.

```
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "dob start",
            "type": "shell",
            "command": "docker-compose -f docker-compose.yaml -f dev.yaml up -d"
        },
        {
            "label": "dob stop",
            "type": "shell",
            "command": "docker-compose -f docker-compose.yaml -f dev.yaml stop odoo"
        }
    ]
}
```
