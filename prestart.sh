#!/bin/sh

echo "Attempting setup…"
$VIRTUAL_ENV/bin/python3 -c "from contentfilter.main import setup; setup()"
echo "setup done"

exec "$@"
