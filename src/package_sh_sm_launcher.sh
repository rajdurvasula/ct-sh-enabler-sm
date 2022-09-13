#!/bin/bash
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

pushd $SCRIPT_DIRECTORY > /dev/null

rm -rf .package sh_sm_launcher.zip

zip sh_sm_launcher.zip sh_sm_launcher.py

popd > /dev/null
