# Deployment Guide for Remora-Fin

This guide explains how to deploy the **remora-fin** project as a Python library to PyPI.

## 1. Automated Deployment (GitHub Actions)

The project is configured to publish to PyPI automatically when a new version tag is pushed.

### Prerequisites
1.  **PyPI Account:** Have an account on [pypi.org](https://pypi.org/).
2.  **Trusted Publishing:** Set up "Trusted Publishing" on PyPI:
    *   **PyPI Project Name:** `remora-fin`
    *   **Owner:** Your GitHub username/org.
    *   **Repository name:** `remora-fin`
    *   **Workflow name:** `release.yml`
    *   **Environment name:** `pypi`

### Deployment Steps
1.  Update the `version` in `pyproject.toml`.
2.  Commit the change: `git commit -am "chore: bump version to X.Y.Z"`
3.  Tag the commit: `git tag vX.Y.Z`
4.  Push the tag: `git push origin vX.Y.Z`

---

## 2. Manual Deployment

If you need to publish manually from your local machine, use `uv`.

### Steps
1.  **Build the distribution:**
    ```bash
    uv build
    ```
2.  **Upload to PyPI:**
    ```bash
    uvx twine upload dist/*
    ```
    *(Requires a PyPI API token)*

---

## 3. Configuration Details

*   **Build Backend:** Uses `uv_build`.
*   **Entry Point:** The CLI is accessible via the `remora-fin` command.
*   **Inclusions:** Only `src/remora_fin` is included; `tests` and `.github` are excluded from the distribution.
