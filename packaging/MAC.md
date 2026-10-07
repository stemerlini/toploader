# Toploader for macOS

Toploader is a terminal app: it runs in Terminal, iTerm2, Ghostty or any other
terminal.

## Install

1. Unzip, then open Terminal in this folder (or drag the folder onto the
   Terminal icon).
2. macOS blocks apps downloaded from the internet that aren't from the App
   Store or a registered developer. Allow this one:

   ```sh
   xattr -d com.apple.quarantine toploader
   ```

3. Put it on your PATH so you can type `toploader` anywhere:

   ```sh
   mkdir -p ~/.local/bin && mv toploader ~/.local/bin/
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
   ```

   Open a new Terminal window and run `toploader`.

The first start takes a few seconds while it unpacks itself; later starts are
quicker.

## Using it

Press `a` to add a card (search by name, `270/SM-P`, or a set code like `s4a`),
Space to preview, `?` for all the keys, `q` to quit.

Card images look best in **iTerm2**, **Ghostty**, **WezTerm** or **kitty**; the
built-in Terminal app shows them as coloured blocks.

## Your data

Your collection is saved in `~/Library/Application Support/Toploader`. Back up
that folder to keep it safe; replacing the `toploader` file with a newer version
keeps your collection.
