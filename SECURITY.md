# Security policy

`export-igorgraph` writes files that contain Igor commands, and an Igor procedure (`ExportIgorGraphLoader.ipf`) executes them with `Execute`.
The design (a strict allow-list; reject the whole file if any command is not allowed) is described in [docs/en/safety.md](docs/en/safety.md).

## Reporting a vulnerability

If you find a way to make the loader run a command that is not a drawing command, to bypass the allow-list, or anything else with security impact,
**please do not open a public issue**. Use GitHub's private vulnerability reporting ("Security" tab → "Report a vulnerability") for this repository.
Include the `.h5` file or the command string and the Igor version, if possible.

You can expect an acknowledgement within a week. This is a volunteer-maintained project; please allow reasonable time for a fix.

## Scope and known limits

Known limits (for example `DoWindow/K` closing an existing window of the same name) are listed in `docs/en/safety.md`.
Only open `.h5` files from sources you trust, and keep your Igor work saved.
