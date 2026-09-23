# Releasing and installing this fork

This repository is a fork of [jellyfin/jellyfin-plugin-tvdb](https://github.com/jellyfin/jellyfin-plugin-tvdb).
It publishes its own **plugin repository** so a Jellyfin server can install TheTVDB straight from the
fork, independently of the official `repo.jellyfin.org` catalogue.

## Repository layout

| Remote     | Points at                                        |
| ---------- | ------------------------------------------------ |
| `origin`   | `michalkulik/jellyfin-plugin-tvdb` (this fork)   |
| `upstream` | `jellyfin/jellyfin-plugin-tvdb` (the original)   |

`master` tracks `origin/master`, so a plain `git push` goes to the fork.

## Installing from the fork

1. In Jellyfin open **Dashboard → Plugins → Repositories** and add:

   ```
   https://github.com/michalkulik/jellyfin-plugin-tvdb/releases/latest/download/manifest.json
   ```

2. Reload the catalogue and install **TheTVDB** from it.

The plugin keeps the **upstream GUID** (`a677c0da-fac5-4cde-941a-7134223f14c8`), so Jellyfin treats
it as the same plugin as the official build: it replaces it instead of sitting next to it, and the
configuration as well as all stored provider ids keep working.

Because the GUID is shared, Jellyfin merges the versions listed by every enabled repository. The
fork build therefore has to carry a **higher version** than the official one to be offered as the
newest — that is what the fourth component is for (upstream `24.0.0.0`, fork build `24.0.0.1`).

## Versioning

`Directory.Build.props` holds `PluginVersion`, the single source of truth:

```xml
<PluginVersion Condition="'$(PluginVersion)' == ''">24.0.0.1</PluginVersion>
```

The fourth component is the fork's own counter and must be bumped for **every** release, otherwise
Jellyfin never offers it (see the note about merged versions above). The release workflow passes the
tag version in as `-p:PluginVersion=<tag>`, so the file only matters for a plain local build.

## Publishing a new version

1. Bump `PluginVersion` in `Directory.Build.props` and commit it.
2. Push and tag:

   ```bash
   git push origin master
   git tag -a v24.0.0.1 -m "TheTVDB fork 24.0.0.1"
   git push origin v24.0.0.1
   ```

3. The [`Fork / Plugin Release`](.github/workflows/fork-plugin-release.yaml) workflow builds the
   plugin, packages the ZIP with its `meta.json`, generates `manifest.json` with the MD5 checksum and
   creates (or refreshes) the GitHub release at
   `https://github.com/michalkulik/jellyfin-plugin-tvdb/releases`.

You can also run it manually from the **Actions** tab and type a version.

## What the release contains

| File                       | Purpose                                                            |
| -------------------------- | ------------------------------------------------------------------ |
| `thetvdb_<version>.zip`    | `meta.json` + `Jellyfin.Plugin.Tvdb.dll` + `Tvdb.Sdk.dll`           |
| `manifest.json`            | the plugin repository catalogue Jellyfin reads                      |

`latest/download/manifest.json` always points at the newest release, so Jellyfin keeps working
across releases without changing the repository URL.

Packaging is done by [`tools/build-plugin-repo.py`](tools/build-plugin-repo.py), which reads the
plugin's identity from `build.yaml` and only ships the assemblies listed in its `artifacts` key.

## Keeping the fork up to date with upstream

```powershell
git fetch upstream
git merge upstream/master
```

Resolve any conflicts, bump the fork revision, then release as described above. Merging (not
rebasing) keeps the published tags intact, exactly like the companion forks.

## Compatibility

| | |
| --- | --- |
| `targetAbi` | `12.0.0.0` |
| Framework | `net10.0` |
| Released assets | `Jellyfin.Plugin.Tvdb.dll`, `Tvdb.Sdk.dll` |

Jellyfin only offers a version whose `targetAbi` is less than or equal to the server's own version
(`InstallationManager.cs`), and it refuses to load it otherwise. Building against the `Jellyfin.*`
`12.*-*` packages plus this `targetAbi` covers every Jellyfin 12.x server.
