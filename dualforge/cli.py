from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dualforge import __version__
from dualforge.compression import METHODS, is_available
from dualforge.detector import detect
from dualforge.extract import ExtractOptions, extract_file
from dualforge.unreal import KeyStore
from dualforge.unreal.keys import DEFAULT_ENDPOINTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dualforge",
        description="Universal Unity + Unreal game asset extraction toolkit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    detect_parser = sub.add_parser("detect", help="identify an archive format")
    detect_parser.add_argument("path", help="file to inspect")
    detect_parser.set_defaults(handler=_cmd_detect)

    extract_parser = sub.add_parser("extract", help="extract assets from an archive")
    extract_parser.add_argument("path", help="archive to extract")
    extract_parser.add_argument("-o", "--out", required=True, help="output directory")
    extract_parser.add_argument("--engine", choices=["auto", "unity", "unreal"], default="auto")
    extract_parser.add_argument("--aes", help="AES-256 key (hex) for encrypted Unreal archives")
    extract_parser.add_argument(
        "--usmap",
        help="CUE4Parse mappings file (.usmap) for unversioned UE5 packages; "
        "auto-detected from DUALFORGE_USMAP, ~/.dualforge or the game folder",
    )
    extract_parser.add_argument(
        "--types", nargs="*", help="Unity object types to export, e.g. Texture2D AudioClip"
    )
    extract_parser.add_argument("--files", nargs="*", help="Unreal paths to extract")
    extract_parser.add_argument(
        "--format",
        help="export format applied to all types that support it, e.g. png, wav, obj, gltf",
    )
    extract_parser.add_argument(
        "--driver",
        help="game driver name to apply (overrides aes/scheme/format defaults); "
        "'auto' matches the archive path automatically",
    )
    extract_parser.set_defaults(handler=_cmd_extract)

    keys_parser = sub.add_parser("keys", help="manage the decryption key database")
    keys_sub = keys_parser.add_subparsers(dest="key_command", required=True)
    keys_list = keys_sub.add_parser("list")
    keys_list.set_defaults(key_handler=_cmd_keys_list)
    keys_add = keys_sub.add_parser("add")
    keys_add.add_argument("title")
    keys_add.add_argument("aes_key")
    keys_add.add_argument("--engine", default="unreal")
    keys_add.add_argument(
        "--scheme",
        default=None,
        help="encryption scheme/preset (default: aes-256). See 'dualforge keys schemes'.",
    )
    keys_add.add_argument("--guid", default="", help="encryption key GUID (dynamic-key games)")
    keys_add.add_argument(
        "--param", action="append", default=[],
        metavar="KEY=VALUE",
        help="scheme parameter, e.g. xor_key=1122334455667788 (repeatable)",
    )
    keys_add.set_defaults(key_handler=_cmd_keys_add)
    keys_list = keys_sub.add_parser("schemes")
    keys_list.set_defaults(key_handler=_cmd_keys_schemes)
    keys_test = keys_sub.add_parser(
        "test", help="test a key/scheme against an Unreal pak file",
    )
    keys_test.add_argument("pak", help="path to an encrypted .pak file")
    keys_test.add_argument("--title", help="use this stored entry's scheme/key/params")
    keys_test.add_argument("--aes", help="key to test (hex)")
    keys_test.add_argument(
        "--scheme", default="aes-256",
        help="scheme to test with (only meaningful with --aes)",
    )
    keys_test.set_defaults(key_handler=_cmd_keys_test)
    keys_remove = keys_sub.add_parser("remove")
    keys_remove.add_argument("title")
    keys_remove.set_defaults(key_handler=_cmd_keys_remove)
    keys_sync = keys_sub.add_parser("sync")
    keys_sync.add_argument("--endpoint", action="append", help="community key endpoint URL")
    keys_sync.set_defaults(key_handler=_cmd_keys_sync)
    keys_import = keys_sub.add_parser("import", help="import an FModel Global.AESKeys.json file")
    keys_import.add_argument("path", help="path to Global.AESKeys.json")
    keys_import.set_defaults(key_handler=_cmd_keys_import)

    codec_parser = sub.add_parser("codecs", help="list supported compression codecs")
    codec_parser.set_defaults(handler=_cmd_codecs)

    usmap_parser = sub.add_parser("usmap", help="inspect, validate and rebuild .usmap files")
    usmap_sub = usmap_parser.add_subparsers(dest="usmap_command", required=True)
    usmap_validate = usmap_sub.add_parser("validate", help="parse a usmap and report its contents")
    usmap_validate.add_argument("path", help="usmap file to parse")
    usmap_validate.set_defaults(usmap_handler=_cmd_usmap_validate)
    usmap_repack = usmap_sub.add_parser("repack", help="rebuild a usmap (optionally recompress)")
    usmap_repack.add_argument("path", help="usmap file to rebuild")
    usmap_repack.add_argument("-o", "--out", help="output file (default: <path>.rebuilt.usmap)")
    usmap_repack.add_argument(
        "--compression", choices=["zstd", "brotli", "none"], default="zstd",
        help="output compression (default: zstd)",
    )
    usmap_repack.add_argument(
        "--version", type=int, choices=list(range(5)), default=None,
        help="usmap format version 0-4 (default: keep input version)",
    )
    usmap_repack.set_defaults(usmap_handler=_cmd_usmap_repack)
    usmap_names = usmap_sub.add_parser("names", help="list the usmap name table")
    usmap_names.add_argument("path", help="usmap file to inspect")
    usmap_names.add_argument("--filter", help="only print names containing this substring")
    usmap_names.add_argument("--count", action="store_true", help="only print the name count")
    usmap_names.set_defaults(usmap_handler=_cmd_usmap_names)
    usmap_dump = usmap_sub.add_parser(
        "dump", help="dump the FNamePool of a running UE5 game into a usmap (Windows)",
    )
    usmap_dump.add_argument("-o", "--out", help="output usmap file")
    usmap_dump.add_argument(
        "--process", help="game executable name, e.g. POLARIS-Win64-Shipping",
    )
    usmap_dump.add_argument("--pid", type=int, help="game process id (alternative to --process)")
    usmap_dump.add_argument(
        "--list-processes", action="store_true", help="list running processes and exit",
    )
    usmap_dump.set_defaults(usmap_handler=_cmd_usmap_dump)

    driver_parser = sub.add_parser(
        "drivers", help="manage game drivers (import/export/match)"
    )
    driver_sub = driver_parser.add_subparsers(dest="driver_command", required=True)
    driver_list = driver_sub.add_parser("list", help="list all registered game drivers")
    driver_list.set_defaults(driver_handler=_cmd_drivers_list)
    driver_show = driver_sub.add_parser("show", help="show a driver's details as JSON")
    driver_show.add_argument("name", help="driver name")
    driver_show.set_defaults(driver_handler=_cmd_drivers_show)
    driver_export = driver_sub.add_parser(
        "export", help="export a driver to a JSON file"
    )
    driver_export.add_argument("name", help="driver name")
    driver_export.add_argument("-o", "--out", help="output file (default: <name>.<name>.dualforge-driver.json)")
    driver_export.add_argument(
        "--dir",
        help="export a directory of driver files",
    )
    driver_export.add_argument(
        "--all", action="store_true", help="export all registered drivers",
    )
    driver_export.add_argument(
        "--builtin", action="store_true", help="export only built-in drivers",
    )
    driver_export.set_defaults(driver_handler=_cmd_drivers_export)
    driver_import = driver_sub.add_parser(
        "import", help="import a driver from a JSON file"
    )
    driver_import.add_argument("path", help="path to a .dualforge-driver.json file")
    driver_import.add_argument(
        "--dir", help="import all driver files from a directory",
    )
    driver_import.set_defaults(driver_handler=_cmd_drivers_import)
    driver_match = driver_sub.add_parser(
        "match", help="find the best driver for an archive"
    )
    driver_match.add_argument("archive", help="path to an archive file")
    driver_match.add_argument("--mount", default="", help="pak mount point hint")
    driver_match.add_argument(
        "--engine", choices=["unity", "unreal"], help="filter by engine",
    )
    driver_match.set_defaults(driver_handler=_cmd_drivers_match)
    driver_create = driver_sub.add_parser(
        "create",
        help="auto-build a game driver from an archive, from scratch",
    )
    driver_create.add_argument("archive", help="path to an archive file")
    driver_create.add_argument("--name", help="driver name (default: derived from folder)")
    driver_create.add_argument("--label", help="human-friendly label")
    driver_create.add_argument(
        "-o", "--out", help="output file; if set, saves the driver and registers it",
    )
    driver_create.set_defaults(driver_handler=_cmd_drivers_create)
    return parser


def _cmd_detect(args: argparse.Namespace) -> int:
    detection = detect(args.path)
    if detection is None:
        print(f"unable to identify: {args.path}")
        return 1
    print(detection.summary())
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    formats = None
    if args.format:
        from dualforge.export.convert import DEFAULT_FORMATS, format_choices

        formats = {}
        for type_name in DEFAULT_FORMATS:
            if args.format in format_choices(type_name):
                formats[type_name] = args.format
    driver = None
    if args.driver:
        from dualforge.drivers import registry

        if args.driver == "auto":
            driver = registry.match(args.path)
        else:
            driver = registry.get(args.driver)
        if driver is None:
            print(
                f"no driver matching '{args.driver}' for {args.path}",
                file=sys.stderr,
            )
            return 1
    options = ExtractOptions(
        out_dir=args.out,
        aes_key=args.aes,
        engine=None if args.engine == "auto" else args.engine,
        type_filter=tuple(args.types) if args.types else None,
        files=args.files,
        formats=formats,
        usmap=args.usmap,
        driver=driver,
        progress=lambda i, t, m: print(f"[{i + 1}/{t}] {m}", file=sys.stderr),
    )
    try:
        result = extract_file(args.path, options)
    except (ValueError, Exception) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"detected: {result.detected.engine}/{result.detected.kind}")
    if driver is not None:
        print(f"driver:  {driver.name} ({driver.label})")
    print(f"extracted {result.ok} assets to {args.out}")
    for error in result.errors:
        print(f"warning: {error}", file=sys.stderr)
    return 0 if not result.errors else 2


def _cmd_keys_list(args: argparse.Namespace) -> int:
    store = KeyStore()
    entries = store.list()
    if not entries:
        print("key store is empty")
        return 0
    for entry in entries:
        print(f"{entry.title}\t{entry.engine}\t{entry.aes_key[:16]}...")
    return 0


def _cmd_keys_schemes(args: argparse.Namespace) -> int:
    from dualforge.encryption import registry
    from dualforge.encryption.presets import PRESETS

    print("registered schemes:")
    for name in registry.list_schemes():
        print(f"  {name}")
    print("\ngame presets:")
    for preset in PRESETS:
        print(f"  {preset.name:<20} {preset.label}")
    return 0


def _cmd_keys_add(args: argparse.Namespace) -> int:
    scheme = args.scheme or "aes-256"
    from dualforge.encryption.registry import list_schemes

    known = set(list_schemes())
    from dualforge.encryption.presets import PRESETS

    known |= {p.name for p in PRESETS}
    if scheme not in known:
        print(
            f"warning: unknown scheme '{scheme}'. Known: {', '.join(sorted(known))}",
            file=sys.stderr,
        )
    parameters = {}
    for item in args.param:
        if "=" in item:
            k, v = item.split("=", 1)
            parameters[k.strip()] = v.strip()
    KeyStore().add(
        args.title,
        args.aes_key,
        engine=args.engine,
        scheme=scheme,
        guid=args.guid,
        parameters=parameters,
    )
    print(f"added key for {args.title}")
    return 0


def _cmd_keys_test(args: argparse.Namespace) -> int:
    from dualforge.encryption.brute import validate_key, probe_pak_blocks

    store = KeyStore()
    if args.title:
        entry = store.get_entry(args.title)
        if entry is None:
            print(f"no stored key for {args.title}", file=sys.stderr)
            return 1
        aes_key = entry.aes_key
        scheme = entry.scheme or "aes-256"
        parameters = dict(entry.parameters)
        guid = entry.guid
    else:
        if not args.aes:
            print("provide --title or --aes (and --scheme if non-standard)", file=sys.stderr)
            return 1
        aes_key = args.aes
        scheme = args.scheme or "aes-256"
        parameters = {}
        guid = ""

    raw = Path(args.pak).read_bytes()
    blocks = probe_pak_blocks(raw)
    if not blocks:
        print("could not locate an encrypted index block in the pak footer", file=sys.stderr)
        return 1
    hits = 0
    for block in blocks:
        if validate_key(block, scheme, aes_key, Path(args.pak).name, guid, parameters):
            hits += 1
    if hits:
        print(f"key OK (decrypted {hits}/{len(blocks)} index blocks with scheme '{scheme}')")
        return 0
    print(
        f"key did NOT decrypt the index (scheme '{scheme}'). Check the scheme and "
        f"--param values, or list stored keys with 'dualforge keys list'.",
        file=sys.stderr,
    )
    return 1


def _cmd_keys_remove(args: argparse.Namespace) -> int:
    if KeyStore().remove(args.title):
        print(f"removed key for {args.title}")
        return 0
    print(f"no key found for {args.title}", file=sys.stderr)
    return 1


def _cmd_keys_sync(args: argparse.Namespace) -> int:
    endpoints = args.endpoint or DEFAULT_ENDPOINTS
    try:
        synced = KeyStore().sync(endpoints)
    except Exception as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1
    for endpoint, count in synced.items():
        print(f"{endpoint}: {count} new keys")
    return 0


def _cmd_keys_import(args: argparse.Namespace) -> int:
    try:
        count = KeyStore().import_fmodel_json(args.path)
    except Exception as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 1
    print(f"imported {count} keys from {args.path}")
    return 0


def _cmd_codecs(args: argparse.Namespace) -> int:
    for method in METHODS:
        status = "available" if is_available(method) else "missing"
        print(f"{method:10s} {status}")
    return 0


def _cmd_usmap_validate(args: argparse.Namespace) -> int:
    from dualforge.unreal.usmap import parse_usmap

    try:
        mappings = parse_usmap(open(args.path, "rb").read())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"names:   {len(mappings.names)}")
    print(f"enums:   {len(mappings.enums)}")
    print(f"structs: {len(mappings.structs)}")
    print(f"version: {mappings.version}")
    print(f"versioning: {'yes' if mappings.versioning else 'no'}")
    return 0


def _cmd_usmap_repack(args: argparse.Namespace) -> int:
    from dualforge.unreal.usmap import UsmapCompression, UsmapVersion, build_usmap, parse_usmap

    try:
        mappings = parse_usmap(open(args.path, "rb").read())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    compression = {
        "zstd": UsmapCompression.ZStandard,
        "brotli": UsmapCompression.Brotli,
        "none": UsmapCompression.None_,
    }[args.compression]
    try:
        version = UsmapVersion(args.version) if args.version is not None else mappings.version
        data = build_usmap(mappings, version=version, compression=compression)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = args.out or f"{args.path}.rebuilt.usmap"
    open(out, "wb").write(data)
    print(f"wrote {out} ({len(data)} bytes)")
    return 0


def _cmd_usmap_names(args: argparse.Namespace) -> int:
    from dualforge.unreal.usmap import parse_usmap

    try:
        mappings = parse_usmap(open(args.path, "rb").read())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.count:
        print(len(mappings.names))
        return 0
    for name in mappings.names:
        if not args.filter or args.filter in name:
            print(name)
    return 0


def _cmd_usmap_dump(args: argparse.Namespace) -> int:
    from dualforge.unreal.usmap_dump import (
        UsmapDumpError,
        dump_usmap,
        find_process,
        list_game_processes,
    )

    if args.list_processes:
        for pid, exe in list_game_processes():
            print(f"{pid}\t{exe}")
        return 0
    if not args.out:
        print("error: pass -o/--out <usmap file>", file=sys.stderr)
        return 1
    if args.pid is None and not args.process:
        print("error: pass --process <game.exe> or --pid <id>", file=sys.stderr)
        return 1
    try:
        if args.pid is not None:
            pid = args.pid
        else:
            pid, exe = find_process(args.process)
            print(f"attaching to {exe} (pid {pid})")
        pool = dump_usmap(pid, args.out)
    except (UsmapDumpError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"dumped {len(pool.names)} names from {pool.block_count} blocks -> {args.out}")
    return 0


def _cmd_drivers_list(args: argparse.Namespace) -> int:
    from dualforge.encryption.presets import PRESETS

    from dualforge.drivers import registry

    drivers = registry.list()
    if not drivers:
        print("no game drivers registered")
        return 0
    print(f"{len(drivers)} driver(s):")
    for driver in sorted(drivers, key=lambda d: d.name):
        scheme = driver.encryption_scheme
        egame = f" [{driver.egame}]" if driver.egame else ""
        print(
            f"  {driver.name:<22} {driver.label:<30} "
            f"({driver.engine}/{scheme}){egame}"
        )
    return 0


def _cmd_drivers_show(args: argparse.Namespace) -> int:
    from dualforge.drivers import registry

    driver = registry.get(args.name)
    if driver is None:
        print(f"no driver named '{args.name}'", file=sys.stderr)
        return 1
    print(driver.to_json())
    return 0


def _cmd_drivers_export(args: argparse.Namespace) -> int:
    from dualforge.drivers import registry

    if args.dir:
        from pathlib import Path

        target = Path(args.dir)
        target.mkdir(parents=True, exist_ok=True)
        count = registry.export_all(str(target))
        print(f"exported {count} driver(s) to {target}")
        return 0
    if args.all:
        target = args.out or "drivers"
        from pathlib import Path

        Path(target).mkdir(parents=True, exist_ok=True)
        count = registry.export_all(target)
        print(f"exported {count} driver(s) to {target}")
        return 0
    if args.builtin:
        target = args.out or "drivers"
        from pathlib import Path

        Path(target).mkdir(parents=True, exist_ok=True)
        count = registry.export_builtin(target)
        print(f"exported {count} built-in driver(s) to {target}")
        return 0
    driver = registry.get(args.name)
    if driver is None:
        print(f"no driver named '{args.name}'", file=sys.stderr)
        return 1
    out = args.out or f"{driver.name}.{driver.name}.dualforge-driver.json"
    written = registry.save(driver, out)
    print(f"exported driver to {written}")
    return 0


def _cmd_drivers_import(args: argparse.Namespace) -> int:
    from dualforge.drivers import registry

    if args.dir:
        count = registry.load_dir(args.dir)
        print(f"imported {count} driver(s) from {args.dir}")
        return 0
    try:
        driver = registry.load_file(args.path)
    except Exception as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 1
    print(f"imported driver '{driver.name}' ({driver.label})")
    return 0


def _cmd_drivers_match(args: argparse.Namespace) -> int:
    from dualforge.drivers import registry

    driver = registry.match(args.archive, args.mount, engine=args.engine)
    if driver is None:
        print(f"no driver matches {args.archive}", file=sys.stderr)
        return 1
    print(f"matched: {driver.name} ({driver.label})")
    print(f"  engine             : {driver.engine}")
    print(f"  encryption scheme  : {driver.encryption_scheme}")
    if driver.encryption_params:
        print(f"  scheme params      : {driver.encryption_params}")
    if driver.egame:
        print(f"  CUE4Parse EGame    : {driver.egame}")
    if driver.usmap_required:
        print("  usmap required     : yes")
    if driver.export_formats:
        print(f"  export formats     : {driver.export_formats}")
    if driver.asset_filter:
        print(f"  asset filter       : {driver.asset_filter}")
    return 0


def _cmd_drivers_create(args: argparse.Namespace) -> int:
    from dualforge.drivers import build_driver_from_archive, registry

    # Double-check the archive is real/readable for a clearer error.
    from pathlib import Path

    if not Path(args.archive).is_file():
        print(f"archive not found: {args.archive}", file=sys.stderr)
        return 1
    from dualforge.drivers.driver import GameDriver

    if args.name and registry.get(args.name) is not None:
        print(
            f"a driver named '{args.name}' already exists; pick a different --name",
            file=sys.stderr,
        )
        return 1
    driver = build_driver_from_archive(args.archive, name=args.name, label=args.label)
    if args.out:
        written = registry.save(driver, args.out)
        print(
            f"created and saved driver '{driver.name}' ({driver.label}) -> {written}"
        )
    else:
        print(f"created driver '{driver.name}' ({driver.label})")
    print(driver.to_json())
    return 0


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler:
        return handler(args)
    key_handler = getattr(args, "key_handler", None)
    if key_handler:
        return key_handler(args)
    usmap_handler = getattr(args, "usmap_handler", None)
    if usmap_handler:
        return usmap_handler(args)
    driver_handler = getattr(args, "driver_handler", None)
    if driver_handler:
        return driver_handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
