# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path.cwd()

hiddenimports = [
    "client.api_client",
    "client.api_client.client",
    "client.database.local_db",
    "client.files.deletion_service",
    "client.gui.auth_components",
    "client.gui.bundle_detail_widget",
    "client.gui.bundle_list_widget",
    "client.gui.disk_selector",
    "client.gui.login_window",
    "client.gui.main_window",
    "client.gui.scan_progress",
    "client.gui.settings_widget",
    "client.gui.theme",
    "client.gui.theme_manager",
    "client.pipeline.analysis_pipeline",
    "client.scanner.disk_detector",
    "client.scanner.file_ids",
    "client.scanner.incremental",
    "client.utils.formatters",
    "httpx",
    "psutil",
    "send2trash",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
]


a = Analysis(
    [str(ROOT / "client" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "server",
        "tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartCleaner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SmartCleaner",
)
