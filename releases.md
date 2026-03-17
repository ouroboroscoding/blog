# blog_oc releases

## 0.3.0
- Updated all pip modules to latest versions.
- Removed local "definition" files and replaced them with submodule "define" files.
- Updated all `_id` fields to be trimmed UUIDs `tuuid` instead of full, `uuid`. This includes all fields that point to an `_id`.
- Refactored install.py and added upgrade.py to allow them to work when loaded by another project, allowing us to call the install and upgrade process form inside our own install/upgrade scripts without forcing the user to also install/upgrade mouth manually.
- Stopped hardcoding DB host to **blog** and now the user can set if via `config.blog.mysql`.
