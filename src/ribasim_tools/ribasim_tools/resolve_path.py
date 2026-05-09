from pathlib import Path

from win32com.client import Dispatch


def resolve_mfms_path(path):
    """Resolve a normal directory, symlink/junction or Windows .lnk shortcut to its real target path.

    Parameters
    ----------
    path : str | Path

    Returns
    -------
    Path
        Resolved target path.
    """
    path = Path(path)

    # Windows shortcut (.lnk)
    shortcut = path / "GRAM32_BASIS1_TA-PRJ.PRJ.lnk"
    if shortcut:
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut))
        target = Path(shortcut.Targetpath)

        if not target.exists():
            raise FileNotFoundError(f"Shortcut target does not exist: {target}")

        return target.resolve()
    elif not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    else:
        return path
