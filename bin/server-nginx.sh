#!/bin/sh

export LC_CTYPE=ru_RU.UTF-8
export HOME=/home/aml
export PYTHONPATH=/home/mg:/home/joyblog

cd /home/joyblog

screen -D -S server -m bin/mg_server -n
sleep 2
