# PyInstaller build recipe: onedir, windowed. Run through tools/build_windows.ps1.
# Output: temp/dist/StellarWanderer/StellarWanderer.exe (the folder is what the installer packs).

import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)  # this spec is in tools/, the project folder is its parent
RESOURCES = os.path.join(ROOT, 'common', 'resources')
ICON = os.path.join(RESOURCES, 'presentation', 'game_icon.ico')

# fonts, textures, dialogs, people names, portraits. The target must mirror the source layout:
# common.paths.resource_path looks for common/resources inside the build.
datas = [(RESOURCES, 'common/resources')]
binaries = []
hiddenimports = []

# PyOpenGL loads its platform modules dynamically, so PyInstaller cannot see them.
opengl_datas, opengl_binaries, opengl_hiddenimports = collect_all('OpenGL')
datas += opengl_datas
binaries += opengl_binaries
hiddenimports += opengl_hiddenimports

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['tests', 'tools'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StellarWanderer',
    icon=ICON,
    console=False,  # windowed: no console; logs go to the data folder
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='StellarWanderer',
)
