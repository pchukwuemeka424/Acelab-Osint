# Dependencies

Backend pins are in `backend/requirements.txt`. Frontend pins are in `frontend/package-lock.json`.

They were resolved for CPython 3.14. The API image uses `python:3.14-slim`. The first pins chosen for older 3.12-era releases did not publish `pydantic-core` wheels for 3.14, so the lockfile uses the current releases that do.

## Updating

1. Change the direct pin in `backend/requirements.txt` or update the frontend package with npm.
2. Install into a clean virtualenv or run `npm install`.
3. Run `pytest`, `npm test`, and the Playwright investigation test.
4. Read `pip index` release notes and `npm audit` before keeping the upgrade.
5. Commit the lockfile with the code change.

Do not copy an unpinned `pip freeze` from a developer machine over the requirements file without checking that the API image can still build.
