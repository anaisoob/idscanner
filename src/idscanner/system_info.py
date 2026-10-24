"""Distribution-specific instructions; never execute installation commands."""

import platform

INSTALL_COMMANDS = {
    "debian": "sudo apt install sane-utils",
    "ubuntu": "sudo apt install sane-utils",
    "fedora": "sudo dnf install sane-backends",
    "arch": "sudo pacman -S sane",
    "opensuse": "sudo zypper install sane-backends",
    "opensuse-leap": "sudo zypper install sane-backends",
    "opensuse-tumbleweed": "sudo zypper install sane-backends",
    "suse": "sudo zypper install sane-backends",
}


def sane_install_help() -> str:
    if platform.system() != "Linux":
        return "Scanner support in this application requires Linux and SANE."
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    name = release.get("PRETTY_NAME") or release.get("NAME") or "Linux"
    # Prefer the distribution itself, then its compatible parents in order.
    candidates = [release.get("ID", ""), *release.get("ID_LIKE", "").split()]
    command = next((INSTALL_COMMANDS[key] for key in candidates if key in INSTALL_COMMANDS), None)
    if command:
        return f"Detected system: {name}\nRun this command in a terminal:\n{command}"
    return f"Detected system: {name}\nInstall the package providing scanimage using your system's package manager."
