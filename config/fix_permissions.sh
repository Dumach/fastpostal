#!/bin/bash
chown -R root:fastapi /opt/fastpostal
chmod -R u=rwX,g=rX,o= /opt/fastpostal
chmod g+x .venv/bin/*
sudo -u fastapi /opt/fastpostal/.venv/bin/serve --help