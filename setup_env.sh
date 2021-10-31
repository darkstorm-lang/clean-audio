#!/bin/bash

#------------------------------------------------------------------------------
# Sets up the correct python virtual environment for running the server
#------------------------------------------------------------------------------
SCRIPT_PATH=`dirname "$BASH_SOURCE"`

if [ ! -d .pyenv ]; then
	echo "Creating virtual environment"	
	pip3 install -q virtualenv
	virtualenv --python=python3 .pyenv
fi
echo "Configuring virtual environment"	
source ${SCRIPT_PATH}/.pyenv/bin/activate
pip3 install -r requirements.txt



