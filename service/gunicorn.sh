#!/bin/bash

cd /home/ubuntu/membership.synshop.org
source /home/ubuntu/membership.synshop.org/activate;
gunicorn --bind 127.0.0.1:8000 --log-file /tmp/gunicorn.log --pid /tmp/gunicorn.pid server:app
