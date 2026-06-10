# Environment Setup Report: Docker CLI + winutils

Workdir: `C:\Users\blankxxc\Desktop\work_space\stock_good`

## Docker

Installed with winget:

```bash
winget install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements --disable-interactivity
```

Verified files:

- `C:\Program Files\Docker\Docker\Docker Desktop.exe`
- `C:\Program Files\Docker\Docker\resources\bin\docker.exe`
- `C:\Program Files\Docker\Docker\resources\bin\docker-compose.exe`

Verified CLI output with Docker bin added to PATH:

- `docker --version` -> `Docker version 29.5.2, build 79eb04c`
- `docker compose version` -> `Docker Compose version v5.1.4`

User environment PATH was updated to include:

- `C:\Program Files\Docker\Docker\resources\bin`

Current blocker:

- Docker Linux engine is not ready yet.
- `docker info` returns an API/server error because WSL is not installed/enabled.
- This shell is not elevated (`net session` returned access denied), so WSL/VirtualMachinePlatform could not be enabled here.

Admin follow-up needed:

```bat
wsl --install
```

If that still reports WSL not installed, run from an Administrator terminal:

```bat
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

Then reboot, start Docker Desktop, and verify:

```bash
docker info
docker run --rm hello-world
cd /c/Users/blankxxc/Desktop/work_space/stock_good/deploy/docker
docker compose config
```

## winutils / Hadoop native helper

Installed to:

- `C:\Users\blankxxc\hadoop\bin\winutils.exe`
- `C:\Users\blankxxc\hadoop\bin\hadoop.dll`

Downloaded from:

- `https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.6/bin/winutils.exe`
- `https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.6/bin/hadoop.dll`

SHA256:

- `winutils.exe`: `496a591eb1e67df2a620f710d529ba6ddfe1c19149e6647cc4e320bb0efd8553`
- `hadoop.dll`: `d7ab36a68518748cef142be2da5069b4c763c2cd764c1d2e6ac48c7200405be3`

User environment was updated:

- `HADOOP_HOME=C:\Users\blankxxc\hadoop`
- PATH includes `C:\Users\blankxxc\hadoop\bin`

Spark verification:

```bash
.venv/Scripts/python.exe spark/jobs/foundation_spark_smoke.py
```

Result:

```json
{"status":"ok","runtime":"pyspark-local","read_status":"ok","write_status":"parquet_ok","rows":3}
```

foundation acceptance was rerun successfully after winutils installation:

```bash
python scripts/check_foundation_acceptance.py
```

Result: `status=ok`, including `6 passed` and Spark `write_status=parquet_ok`.
