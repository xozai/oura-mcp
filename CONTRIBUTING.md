# Contributing

## Commits and Releases

This repo uses [Conventional Commits](https://www.conventionalcommits.org) enforced on PR titles. Because we squash-merge, the PR title becomes the commit message on `main`.

### Allowed types

| Type       | When to use                                  |
|------------|----------------------------------------------|
| `feat`     | New tool, endpoint, or user-visible feature  |
| `fix`      | Bug fix                                       |
| `docs`     | README, CONTRIBUTING, inline docs only       |
| `refactor` | Internal restructure, no behavior change     |
| `test`     | Tests only                                    |
| `chore`    | Dependency bumps, config, tooling             |
| `perf`     | Performance improvement                       |
| `ci`       | CI/CD workflow changes                        |
| `style`    | Formatting, whitespace                        |
| `build`    | Build system changes                          |

### Versioning (pre-1.0)

| Change                    | Bump    |
|---------------------------|---------|
| `feat` or breaking change | MINOR   |
| `fix`, `perf`, `refactor` | PATCH   |

Breaking changes are marked with `!` after the type (`feat!: ...`) or a `BREAKING CHANGE:` footer in the commit body.

### Good PR title examples

```
feat: add oura_get_tags tool
fix: handle 429 rate-limit response in heart rate endpoint
docs: update README with Claude Desktop config example
chore: bump httpx to 0.28.0
feat!: rename start_date param to date_start across all tools
```

### Bad PR title examples

```
update stuff          ← no type
feat(scope): add X   ← scopes are not used in this repo
Fixed the bug        ← wrong format, no type
WIP                  ← not a conventional commit
```

### How releases work

1. Merge a PR to `main` with a valid conventional-commit title.
2. `release-please` opens a Release PR within ~1 minute, updating `CHANGELOG.md` and bumping the version.
3. The Release PR is auto-merged once all required status checks pass — no manual step needed.
4. A `vX.Y.Z` tag and GitHub Release are created automatically.
