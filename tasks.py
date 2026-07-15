"""camas task definitions for msgspec-cbor."""

from pathlib import Path

from camas import Claude, Config, Parallel, Sequential, Task

format = Task("uv run ruff format {paths}", mutates=True, paths=".")
format_check = Task("uv run ruff format --check {paths}", paths=".")
lint = Task("uv run ruff check {paths}", paths=".")
lint_fix = Task("uv run ruff check --fix {paths}", mutates=True, paths=".")
fix = Sequential(lint_fix, format)
actionlint = Task("uv run actionlint")
mypy = Task("uv run mypy")
pyright = Task("uv run pyright")

typecheck = Parallel(mypy, pyright)
test = Task("uv run pytest")

check = Parallel(format_check, lint, actionlint, typecheck, test)

matrix = Sequential(
	Task("uv sync"),
	check,
	env={"UV_PROJECT_ENVIRONMENT": ".venv-{PY}", "UV_PYTHON": "{PY}"},
	matrix={
		"PY": tuple(
			stripped
			for line in (Path(__file__).parent / ".python-version").read_text().splitlines()
			if (stripped := line.strip()) and not stripped.startswith("#")
		)
	},
)

_ = Config(default_task=check, github_task=check, agent=Claude(fix=fix, check=check))
