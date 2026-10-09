# Contributing

Thanks for your interest! Bug reports (especially "this matplotlib element looks different in Igor"), new Igor/OS version reports, and pull requests are welcome.

## Reporting a problem

Please include: Igor version and OS, Python/matplotlib/numpy versions, a **minimal script**, the `report.summary()` output, and — if it is about the look — a screenshot of the matplotlib figure and of the Igor graph.
Security problems: see [SECURITY.md](SECURITY.md) (do not file those publicly).

## Development

See [docs/en/developing.md](docs/en/developing.md). In short:

```
pip install -e ".[test]"
python -X utf8 tests/run_all.py
```

## Pull requests

- Keep the tests passing, and add tests for new behavior.
- **Changes to the allow-list** (`eig_allowlist.py`) need a strict pattern, good *and* malicious samples, and a regenerated loader (`python -m export_igorgraph loader igor/`). Never loosen the allow-list with a permissive regex.
- Changes that affect what Igor draws should be compared in Igor (`tools/run_igor_round.py` on Windows, or by hand). Say which Igor version you used. Add what you measured to `docs/en/verified.md`.
- Igor syntax: confirm it in the official documentation (https://docs.wavemetrics.com/) — if you could not, say "unverified".
- Generated `.ipf` files and the loader are ASCII-only with CRLF line endings (non-ASCII characters inside strings as `\uXXXX`).
- Use public matplotlib API; switch on features (`hasattr`), not on version numbers.

By contributing you agree that your contribution is licensed under the MIT License.
