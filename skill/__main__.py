"""Allow `python -m skill "intent"` invocation."""

from skill.builder import main

if __name__ == "__main__":
    raise SystemExit(main())
