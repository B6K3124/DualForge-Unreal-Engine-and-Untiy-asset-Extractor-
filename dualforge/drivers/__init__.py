"""Game drivers: portable, JSON-serializable configs for handling specific games.

A game driver bundles engine type, encryption pipeline, export format defaults,
detection patterns, and CLI hints into a single object. Drivers can be loaded
from disk, shared between users, auto-applied during extraction, or auto-built
from an archive "from scratch".

Usage::

    from dualforge.drivers import GameDriver, registry, build_driver_from_archive

    # List all registered drivers
    for d in registry.list():
        print(d.name, d.label)

    # Find the best driver for an archive
    driver = registry.match("/path/to/pakchunk0-Windows.pak")

    # Auto-build a driver from an unknown archive (engine, scheme, formats)
    driver = build_driver_from_archive("/path/to/unknown.bundle")
    registry.save(driver)                 # persist to ~/.dualforge/drivers/

    # Import/export
    registry.export_all("/tmp/my_drivers")
    registry.load_file("/path/to/custom.dualforge-driver.json")
"""

from dualforge.drivers.build import build_driver_from_archive
from dualforge.drivers.driver import GameDriver
from dualforge.drivers.registry import DriverRegistry, registry

__all__ = [
    "GameDriver",
    "DriverRegistry",
    "registry",
    "build_driver_from_archive",
]
