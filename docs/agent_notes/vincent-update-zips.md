---
name: vincent-update-zips
description: Vincent wants only changed files zipped for package updates, not a full rebuild of mpf_package.zip
metadata:
  type: feedback
---

When updating tron/mpf_package, don't rebuild the full mpf_package.zip (~147 MB) with all assets. Zip only the files that changed (e.g. tron/mpf_package_update_YYYY-MM-DD.zip) and tell Vincent which files are in it.
**Why:** Vincent said so on 2026-10-02 ("Don't rebuild the zip with all assets, just the modified content").
**How to apply:** any thread changing the MPF package ships a small update zip plus a file list. Related: [[tron-dmd-mpf-package]]
