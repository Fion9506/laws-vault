@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs

rem [1] idempotent probe
python -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('127.0.0.1',18062))==0 else 1)"
if %errorlevel%==0 (
  echo [OK] flk-mcp already running: http://127.0.0.1:18062/mcp
  exit /b 0
)

rem [2] dependency self-check
python -c "import mcp, httpx, pydantic, dotenv" >nul 2>&1
if not %errorlevel%==0 (
  echo [FIX] installing deps: mcp^<2 httpx pydantic python-dotenv ...
  python -m pip install "mcp<2" httpx pydantic python-dotenv --quiet --disable-pip-version-check
  python -c "import mcp, httpx, pydantic, dotenv" >nul 2>&1
  if not %errorlevel%==0 (
    echo [FAIL] deps install failed. Run: python -m pip install "mcp<2" httpx pydantic python-dotenv
    exit /b 1
  )
)

rem [3] locate server dir (wildcard, avoid non-ASCII in this file)
set "SRVDIR="
for /d %%D in ("mcp\legal-tools\*MCP") do set "SRVDIR=%%D"
if "%SRVDIR%"=="" (
  echo [FAIL] server dir not found: mcp\legal-tools\*MCP
  exit /b 1
)
if not exist "%SRVDIR%\scripts\server.py" (
  echo [FAIL] server.py not found
  exit /b 1
)

rem [4] background start, log to logs\flk-mcp.log
echo [START] launching flk-mcp in background ...
start "flk-mcp" /min /d "%SRVDIR%" cmd /c "python scripts\server.py > "%~dp0..\logs\flk-mcp.log" 2>&1"

rem [5] probe loop: ping wait (timeout breaks on redirected stdin), 10 x 2s
set /a tries=0
:wait_loop
ping -n 3 127.0.0.1 >nul
python -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(0 if s.connect_ex(('127.0.0.1',18062))==0 else 1)"
if %errorlevel%==0 (
  echo [OK] flk-mcp started: http://127.0.0.1:18062/mcp
  exit /b 0
)
set /a tries+=1
if %tries% lss 10 goto wait_loop
echo [FAIL] no listener within 20s. Log: logs\flk-mcp.log
echo [HINT] in agent terminals use foreground long-running start instead (see SKILL.md path A)
exit /b 1
