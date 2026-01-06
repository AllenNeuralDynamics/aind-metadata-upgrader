# aind-metadata-upgrader

[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Code Style](https://img.shields.io/badge/code%20style-black-black)
[![semantic-release: angular](https://img.shields.io/badge/semantic--release-angular-e10079?logo=semantic-release)](https://github.com/semantic-release/semantic-release)
![Interrogate](https://img.shields.io/badge/interrogate-100.0%25-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen?logo=codecov)
![Python](https://img.shields.io/badge/python->=3.7-blue?logo=python)

## I want to run the upgrader...

### On my local data

```python
from aind_metadata_upgrader.upgrade import Upgrade

# <Your code here: load your data as a dictionary, e.g. json.load(f)>

upgraded_record = Upgrade(data)
upgraded_record.save()
```

### On a single record in V1 DocDB

```python
from aind_metadata_upgrader.sync import run_one
run_one(record_id="<docdb_id>")
```

### On all records in V1 DocDB

```python
from aind_metadata_upgrader.sync import run
run()
```

## I want to develop new upgraders

Add a new `CoreUpgrader` class, then include it in the `MAPPINGS` object.
