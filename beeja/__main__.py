"""Allow `python -m beeja "intent"` invocation."""

from beeja.builder import main

if __name__ == "__main__":
    raise SystemExit(main())
