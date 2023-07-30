install:
	pip install -e .[dev]

lint:
	flake8 vasp_opt_follows --max-line-length=120 --ignore=N802

test:
	pytest tests