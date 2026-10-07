# PyInstaller spec: one self-contained `toploader` executable.
#   .venv/bin/pyinstaller packaging/toploader.spec   ->  dist/toploader
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = (
    collect_data_files("toploader")        # app.tcss
    + collect_data_files("textual")        # Textual's own stylesheets
    + collect_data_files("textual_image")
)
hiddenimports = (
    collect_submodules("toploader")
    + collect_submodules("textual.widgets")  # loaded lazily by name
    + collect_submodules("textual_image")
)

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="toploader",
    console=True,
    strip=False,
    upx=False,
)
