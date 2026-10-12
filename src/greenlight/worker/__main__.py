"""Worker entry point: ``python -m greenlight.worker`` (or the ``greenlight-worker`` script)."""

from greenlight.core.logging_config import configure_logging
from greenlight.worker.loop import run_forever


def main() -> None:
    configure_logging()
    run_forever()


if __name__ == "__main__":
    main()
