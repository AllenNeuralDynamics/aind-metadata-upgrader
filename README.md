# aind-metadata-upgrader

[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Code Style](https://img.shields.io/badge/code%20style-black-black)
[![semantic-release: angular](https://img.shields.io/badge/semantic--release-angular-e10079?logo=semantic-release)](https://github.com/semantic-release/semantic-release)
![Interrogate](https://img.shields.io/badge/interrogate-100.0%25-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen?logo=codecov)
![Python](https://img.shields.io/badge/python->=3.7-blue?logo=python)

## I want to run the upgrader

```python
from aind_metadata_upgrader.upgrade import Upgrade

# <Your code here: load your data as a dictionary, e.g. json.load(f)>

upgraded_record = Upgrade(data)
upgraded_record.save()
```

## I want to develop new upgraders

Add a new `CoreUpgrader` class, then include it in the `MAPPINGS` object.