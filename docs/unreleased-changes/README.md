Unreleased changes
==================

This directory contains a YAML file for each changelog entry belonging to the version of beets that's currently in development.


To add a new changelog entry, use the helper script, passing the pull request
number:

```
./extra/changelog.py 1234
```

Note that this means that you need to have already opened a pull request with your change so that you know the number!

The changelog helper will guide you through the other information we need to collect with a wizard-like approach. Check out `./extra/changelog.py --help` for some more advanced instructions. When the file is created, add it you your pull request.
