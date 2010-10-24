#!/bin/sh

export LC_CTYPE=ru_RU.UTF-8
export HOME=/home/aml
export PYTHONPATH=/home/mg:/home/joyblog

cd /home/joyblog

screen -D -S dir -m bin/mg_director
