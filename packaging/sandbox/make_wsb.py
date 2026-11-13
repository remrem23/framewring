"""Creates Windows Sandbox configs in build\\sandbox (absolute paths are machine-specific, so they are generated).

    python packaging\\sandbox\\make_wsb.py
    then double-click build\\sandbox\\install-test.wsb or build\\sandbox\\update-test.wsb

Windows Sandbox is a throw-away clean Windows: nothing done inside it touches your system or your installed
Framewring. Enable it once: "Turn Windows features on or off" -> "Windows Sandbox" -> restart.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SBX = ROOT / "packaging" / "sandbox"
OUT = ROOT / "build" / "sandbox"
REL = ROOT / "build" / "release"

TEMPLATE = """<Configuration>
  <Networking>Enable</Networking>
  <MappedFolders>
    <MappedFolder><HostFolder>{sbx}</HostFolder><SandboxFolder>C:\\sbx</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
{extra}  </MappedFolders>
  <LogonCommand><Command>powershell -NoExit -ExecutionPolicy Bypass -File C:\\sbx\\{script}</Command></LogonCommand>
</Configuration>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rel = ("    <MappedFolder><HostFolder>%s</HostFolder><SandboxFolder>C:\\release</SandboxFolder>"
           "<ReadOnly>true</ReadOnly></MappedFolder>\n" % REL)
    (OUT / "install-test.wsb").write_text(TEMPLATE.format(sbx=SBX, extra=rel, script="install.ps1"), encoding="utf-8")
    (OUT / "update-test.wsb").write_text(TEMPLATE.format(sbx=SBX, extra="", script="update.ps1"), encoding="utf-8")
    print("ok:", OUT / "install-test.wsb", OUT / "update-test.wsb")


if __name__ == "__main__":
    main()
