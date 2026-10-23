@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Olist - JupyterLab server - Python 3.13
rem Put this file in the root folder of your local Olist project.
rem The project folder is always the folder containing this BAT file.
set "OLIST_PROJECT=%~dp0"
pushd "%OLIST_PROJECT%"
if errorlevel 1 goto folder_error

echo [1/5] Checking the project Python environment...
if exist ".venv_313\Scripts\python.exe" goto check_environment
if exist ".venv_313" goto environment_error

py -3.13 -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1
if not errorlevel 1 goto create_with_py
python -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1
if not errorlevel 1 goto create_with_python
echo ERROR: Python 3.13 was not found.
echo Install Python 3.13, close this window, and run this BAT again.
echo Command: winget install --exact --id Python.Python.3.13 --source winget
goto failed

:create_with_py
py -3.13 -m venv ".venv_313"
if errorlevel 1 goto environment_error
goto check_environment

:create_with_python
python -m venv ".venv_313"
if errorlevel 1 goto environment_error

:check_environment
".venv_313\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1
if errorlevel 1 goto environment_error
echo [2/5] Checking Jupyter and analysis packages...
".venv_313\Scripts\python.exe" -c "import notebook, jupyterlab, ipykernel, pandas, numpy, matplotlib, seaborn, plotly, scipy, statsmodels, sklearn, openpyxl, xlsxwriter, sqlalchemy, psycopg" >nul 2>&1
if not errorlevel 1 goto register_kernel
echo Installing missing packages into the local .venv_313. Internet is required.
".venv_313\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_error
".venv_313\Scripts\python.exe" -m pip install --only-binary=:all: notebook jupyterlab ipykernel pandas numpy matplotlib seaborn plotly scipy statsmodels scikit-learn openpyxl xlsxwriter sqlalchemy "psycopg[binary]"
if errorlevel 1 goto install_error
".venv_313\Scripts\python.exe" -c "import notebook, jupyterlab, ipykernel, pandas, numpy, matplotlib, seaborn, plotly, scipy, statsmodels, sklearn, openpyxl, xlsxwriter, sqlalchemy, psycopg"
if errorlevel 1 goto install_error

:register_kernel
echo [3/5] Registering the Olist Python kernel...
".venv_313\Scripts\python.exe" -m ipykernel install --sys-prefix --name olist-313 --display-name "Python (Olist 3.13)"
if errorlevel 1 goto kernel_error
".venv_313\Scripts\python.exe" -c "import sys, ipykernel, zmq, tornado; from jupyter_client.kernelspec import KernelSpecManager; from pathlib import Path; spec=KernelSpecManager().get_kernel_spec('olist-313'); print('Kernel Python:', spec.argv[0]); sys.exit(Path(spec.argv[0]).resolve() != Path(sys.executable).resolve())"
if errorlevel 1 goto kernel_error

:launch
echo [4/5] Opening project folder and two command prompts...
start "Olist - CMD" "%ComSpec%" /d /v:off /k .venv_313\Scripts\activate.bat
start "" explorer.exe "%OLIST_PROJECT%"
rem Only the separate command prompt requests elevation. Cancellation is OK.
rem The relative activation path avoids inserting the project path into shell code.
powershell.exe -NoProfile -Command "try { Start-Process -FilePath $env:ComSpec -WorkingDirectory $env:OLIST_PROJECT -Verb RunAs -ArgumentList '/d /v:off /k .venv_313\Scripts\activate.bat' -ErrorAction Stop } catch { Write-Host 'Administrator prompt was not opened. Jupyter will still start.'; exit 1 }"

echo [5/5] Starting JupyterLab in your browser...
echo In your notebook select Kernel - Change Kernel - Python (Olist 3.13).
echo Keep this window open while working. Press Ctrl+C here to stop Jupyter.
echo If the browser does not open, copy the local URL printed below.
".venv_313\Scripts\python.exe" -m jupyterlab --MappingKernelManager.default_kernel_name=olist-313 --ServerApp.ip=127.0.0.1 --ServerApp.open_browser=True --ServerApp.root_dir="%CD%"
if errorlevel 1 goto jupyter_error
popd
endlocal
exit /b 0

:folder_error
echo ERROR: Cannot open the project folder. Move this BAT to a local project folder.
pause
endlocal
exit /b 1

:environment_error
echo ERROR: The .venv_313 environment is incomplete, incompatible or cannot be created.
echo Check Python and folder permissions. If the project was moved, recreate .venv_313.
echo No existing environment or project files have been deleted.
goto failed

:install_error
echo ERROR: Package installation or import failed. Check the messages above.
echo Only prebuilt packages are allowed; no C++ compiler is needed.
echo Check the failed package and your Internet connection, then retry.
goto failed

:kernel_error
echo ERROR: Olist kernel registration or import check failed. Copy the messages above.
goto failed

:jupyter_error
echo ERROR: Jupyter stopped with an error. Copy the messages above for troubleshooting.

:failed
pause
popd
endlocal
exit /b 1
