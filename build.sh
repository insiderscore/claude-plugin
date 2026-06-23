#!/bin/sh
echo "You remembered to bump the version, right?"
rm veritydata-claude-plugin.zip
zip -r veritydata-claude-plugin.zip veritydata/
echo "Please rename veritydata-claude-plugin.zip"

