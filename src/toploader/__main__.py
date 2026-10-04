"""Entry point: `toploader` or `python -m toploader`."""


def main() -> None:
    # textual-image must probe the terminal before Textual takes over stdin.
    import textual_image.widget  # noqa: F401

    from .app import Toploader

    Toploader().run()


if __name__ == "__main__":
    main()
