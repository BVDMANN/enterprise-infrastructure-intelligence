# Python container images

The API, Worker and Connector images use Python 3.12 and install their runtime requirements into the same isolated virtual environment at `/opt/venv`.

## Build contract

- The image creates `/opt/venv` with the interpreter supplied by the official Python base image.
- Dependencies are installed with `/opt/venv/bin/python -m pip`, not into the system interpreter.
- `VIRTUAL_ENV` and `PATH` select this environment for the image entrypoint and runtime commands.
- A build-time assertion checks that the selected interpreter is running inside a virtual environment.
- Application processes continue to run as the existing unprivileged `app` user. The virtual environment is read-only to that runtime user; no package installation occurs at startup.

This avoids using pip's system-environment root installation path. It is not implemented by suppressing pip's warning: the installation target is an actual virtual environment.

## Verification

The repository CI must build all three Python images, verify non-root image UIDs, and run the Compose smoke test (API and Worker health plus the simulation Connector exit status). The CI logs are the evidence for the build-warning outcome; this document does not pre-claim that the warning has disappeared.
