"""Entry point: `toploader` or `python -m toploader`."""


def main() -> None:
    # textual-image must probe the terminal before Textual takes over stdin.
    import textual_image.widget  # noqa: F401

    from .app import Toploader
    from .backup import backup
    from .currency import money
    from .paths import ROOT

    app = Toploader()
    app.run()

    app.db.conn.close()  # make sure the collection file is complete before committing
    if app.config.auto_backup:
        copies, unique, value = app.summary()
        message = (f"Collection: {copies} cards ({unique} unique), "
                   f"{money(value, app.currency)}")
        print("Backing up the collection…", flush=True)
        print(backup(ROOT, message))


if __name__ == "__main__":
    main()
