# Release Guide

## 1) First-time setup

- Create the package on PyPI: `metaspn-entities`.
- In PyPI project settings, configure Trusted Publishers for your GitHub repo and the `publish` workflow.
- In GitHub, configure the `pypi` environment used by `.github/workflows/publish.yml`.

## 2) Local validation

```bash
python -m unittest discover -s tests -v
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

## 3) Commit and push

```bash
git init
git add .
git commit -m "Initial release: metaspn-entities v0.1.0"
git branch -M main
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

## 4) Tag-based release

```bash
git tag v0.1.0
git push origin v0.1.0
```

Pushing the tag triggers `.github/workflows/publish.yml` and publishes to PyPI via trusted publishing.

## 5) Optional manual upload (token fallback)

```bash
python -m twine upload dist/*
```

Set `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<pypi-token>` if prompted.
