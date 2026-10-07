# Toploader for macOS

## Install

1. Drag **Toploader.app** into your **Applications** folder.
2. macOS blocks apps that aren't from the App Store or a registered developer.
   Allow this one once: open **Terminal** and run

   ```sh
   xattr -dr com.apple.quarantine /Applications/Toploader.app
   ```

3. Open Toploader from Launchpad, Spotlight or the Applications folder. It opens
   in a Terminal window; drag it to the Dock to keep it there.

The first start takes a few seconds while it unpacks itself; later starts are
quicker.

## Using it

Press `a` to add a card (search by name, `270/SM-P`, or a set code like `s4a`),
Space to preview, `?` for all the keys, `q` to quit.

Card images: Apple's Terminal can't show pictures, so there Space opens the card
at full size in **Quick Look** next to the details (Space closes it again, `o`
reopens it). To see cards inside Toploader itself, install
[Ghostty](https://ghostty.org) (free), kitty or WezTerm: Toploader.app opens in
it automatically. In iTerm2 or any other terminal you can run it directly:

```sh
mkdir -p ~/.local/bin
ln -sf /Applications/Toploader.app/Contents/MacOS/toploader-cli ~/.local/bin/toploader
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

Then type `toploader` in a new window.

## Your data

Your collection is saved in `~/Library/Application Support/Toploader`. Back up
that folder to keep it safe; replacing Toploader.app with a newer version keeps
your collection.
