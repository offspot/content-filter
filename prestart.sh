#!/bin/sh

echo "Attempting setup…"
python -c "from contentfilter.main import setup; setup()"
echo "setup done"
