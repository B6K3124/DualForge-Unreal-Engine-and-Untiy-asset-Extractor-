"""DualForge Ghidra key-hunter bridge server (runs INSIDE Ghidra).

Executed by Ghidra's analyzeHeadless as a ``-postScript``. It starts the
ghidra_bridge server (the pip-installed ``ghidra_bridge_server.py`` must be
reachable via ``-scriptPath``) in a background thread, then keeps the JVM
alive until the host process signals completion by creating the sentinel file
named in the ``DF_STOP_FILE`` environment variable (or until
``DF_MAX_IDLE_SECONDS`` elapses, whichever comes first). The server binds
``GHIDRA_BRIDGE_PORT`` when set, otherwise the package default port.

The postScript intentionally contains no scanning logic: the host side owns
all analysis and talks to Ghidra's flat API (``currentProgram.getMemory()``)
over the bridge, per the headless-lifecycle design.
"""

import os
import time


def run_bridge_server():
    # Jython 2.7: no type annotations, no f-strings.
    # Imported from the directory given to analyzeHeadless via -scriptPath.
    import ghidra_bridge_server  # type: ignore

    try:
        port = int(os.environ.get("GHIDRA_BRIDGE_PORT", "4768"))
    except ValueError:
        port = 4768
    ghidra_bridge_server.GhidraBridgeServer.run_server(
        server_port=port,
        response_timeout=300,
        background=True,
    )

    stop_file = os.environ.get("DF_STOP_FILE", "")
    max_idle = int(os.environ.get("DF_MAX_IDLE_SECONDS", "1800"))
    started = time.time()
    while True:
        time.sleep(1.0)
        if stop_file and os.path.exists(stop_file):
            break
        if time.time() - started > max_idle:
            break


# Ghidra executes a postScript as the main module; call unconditionally so
# it also works if Jython names the module differently.
run_bridge_server()
