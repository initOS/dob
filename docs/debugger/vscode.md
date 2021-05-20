## Required Extension
The `Python` extension needs to be installed before setting up the configuration.


## Configuration

The configuration file to set up debugpy debugger for VS Code is defined in
a `launch.json` file that's stored in a `.vscode` folder in your workspace.
Make sure that port 5678 is open.
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
            // Start the container if the debugger is starting
            "preLaunchTask": "dob start",
            // Stop the container if the debugging ends
            "postDebugTask": "dob stop",
            //maps the files on the server to the right files on local machine
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

In order to start and stop the container by hitting F5 the following `.vscode/tasks.json`
file has to be created inside of the workspace:

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
