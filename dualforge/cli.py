from __future__ import annotations

import argparse
import sys

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
    extract_parser.set_defaults(handler=_cmd_extract)

    keys_parser = sub.add_parser("keys", help="manage the AES key database")
    keys_sub = keys_parser.add_subparsers(dest="key_command", required=True)
    keys_list = keys_sub.add_parser("list")
    keys_list.set_defaults(key_handler=_cmd_keys_list)
    keys_add = keys_sub.add_parser("add")
    keys_add.add_argument("title")
    keys_add.add_argument("aes_key")
    keys_add.add_argument("--engine", default="unreal")
    keys_add.set_defaults(key_handler=_cmd_keys_add)
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
    options = ExtractOptions(
        out_dir=args.out,
        aes_key=args.aes,
        engine=None if args.engine == "auto" else args.engine,
        type_filter=tuple(args.types) if args.types else None,
        files=args.files,
        formats=formats,
        usmap=args.usmap,
        progress=lambda i, t, m: print(f"[{i + 1}/{t}] {m}", file=sys.stderr),
    )
    try:
        result = extract_file(args.path, options)
    except (ValueError, Exception) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"detected: {result.detected.engine}/{result.detected.kind}")
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


def _cmd_keys_add(args: argparse.Namespace) -> int:
    KeyStore().add(args.title, args.aes_key, engine=args.engine)
    print(f"added key for {args.title}")
    return 0


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
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
