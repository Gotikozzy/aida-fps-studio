# Copyright (c) 2021-2023, PyInstaller Development Team.
# GPL-2.0-or-later WITH Bootloader-exception, as in PyInstaller's original hook.
# Preserve the upstream Qt collection behavior; expose LGPL Python wrappers as
# replaceable files rather than embedding them into the application PYZ archive.
from PyInstaller.utils.hooks import check_requirement
from PyInstaller.utils.hooks.qt import (
    ensure_single_qt_bindings_package,
    pyside6_library_info,
)

ensure_single_qt_bindings_package("PySide6")
module_collection_mode = "py"
if pyside6_library_info.version is not None:
    hiddenimports = ["shiboken6", "inspect"]
    if check_requirement("PySide6 >= 6.4.0"):
        hiddenimports += ["PySide6.support.deprecated"]
    binaries = pyside6_library_info.collect_extra_binaries()
