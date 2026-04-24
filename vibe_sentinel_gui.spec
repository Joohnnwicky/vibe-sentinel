# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['vibe_sentinel_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'mss',
        'mss.base',
        'mss.exception',
        'mss.factory',
        'mss.screenshot',
        'numpy',
        'numpy.core',
        'numpy.core.multiarray',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'tkinter',
        'winsound',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VibeSentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
