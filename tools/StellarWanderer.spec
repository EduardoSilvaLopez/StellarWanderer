# PyInstaller build recipe: onedir, windowed. Run through Tools/build_windows.ps1.
# Output: dist/StellarWanderer/StellarWanderer.exe (the folder is what the installer packs).

from PyInstaller.utils.hooks import collect_all

ICON = 'Resources/presentation/game_icon.ico'

datas = [('Resources', 'Resources')]  # fonts, textures, dialogs, people names, portraits
binaries = []
hiddenimports = []

# PyOpenGL loads its platform modules dynamically, so PyInstaller cannot see them.
opengl_datas, opengl_binaries, opengl_hiddenimports = collect_all('OpenGL')
datas += opengl_datas
binaries += opengl_binaries
hiddenimports += opengl_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['tests', 'Tools'],
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
