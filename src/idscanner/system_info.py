"""Distribution-specific instructions; never execute installation commands."""

import platform

SANE_COMMANDS = {
    "debian": "sudo apt install sane-utils",
    "ubuntu": "sudo apt install sane-utils",
    "fedora": "sudo dnf install sane-backends",
    "arch": "sudo pacman -S sane",
    "opensuse": "sudo zypper install sane-backends",
    "opensuse-leap": "sudo zypper install sane-backends",
    "opensuse-tumbleweed": "sudo zypper install sane-backends",
    "suse": "sudo zypper install sane-backends",
}
TK_COMMANDS = {
    "debian": "sudo apt install python3-tk",
    "ubuntu": "sudo apt install python3-tk",
    "fedora": "sudo dnf install python3-tkinter",
    "arch": "sudo pacman -S tk",
    "opensuse": "sudo zypper install python3-tk",
    "opensuse-leap": "sudo zypper install python3-tk",
    "opensuse-tumbleweed": "sudo zypper install python3-tk",
    "suse": "sudo zypper install python3-tk",
}


def linux_install_help(commands: dict[str, str], fallback: str) -> str:
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    name = release.get("PRETTY_NAME") or release.get("NAME") or "Linux"
    # Prefer the distribution itself, then its compatible parents in order.
    candidates = [release.get("ID", ""), *release.get("ID_LIKE", "").split()]
    command = next((commands[key] for key in candidates if key in commands), None)
    if command:
        return f"Detected system: {name}\nRun this command in a terminal:\n{command}"
    return f"Detected system: {name}\n{fallback}"


def sane_install_help() -> str:
    if platform.system() != "Linux":
        return "Scanner support in this application requires Linux and SANE."
    return linux_install_help(
        SANE_COMMANDS, "Install the package providing scanimage using your system's package manager."
    )


def tk_install_help() -> str:
    system = platform.system()
    if system == "Windows":
        return 'Reinstall Python from python.org and keep the "tcl/tk and IDLE" option selected.'
    if system == "Darwin":
        return "Install Python from python.org, which includes Tk, or with Homebrew run:\nbrew install python-tk"
    return linux_install_help(
        TK_COMMANDS, "Install the Tk package for Python (often called python3-tk) using your system's package manager."
    )


def tk_lacks_xft(tk) -> bool:
    """True for an X11 Tk built without Xft, which draws rough fonts and no rounded corners."""
    try:
        return tk.call("tk", "windowingsystem") == "x11" and tk.call("::tk::pkgconfig", "get", "fontsystem") != "xft"
    except Exception:  # an unknown Tk: better no warning than a wrong one
        return False
