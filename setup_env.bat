echo Delete existing environment
@echo off
call deactivate
del /F /Q / S .pyenv > NUL
@echo on
SET SCRIPT_PATH=%~dp0
echo SCRIP_PATH = %SCRIPT_PATH%
python3 -m venv .pyenv
echo "Configuring virtual environment"	
call %SCRIPT_PATH%/.pyenv/Scripts/activate.bat
set PATH=%SCRIPT_PATH%bin\win\usr\bin\;%PATH%
pip3 install -r requirements.txt
