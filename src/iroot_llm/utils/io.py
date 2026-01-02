import base64
import bz2
import csv
import gzip
import json
import logging
from pathlib import Path

from tqdm import tqdm

try:
    import ujson

    JSON_LIB = ujson
except ImportError:
    JSON_LIB = json

logger = logging.getLogger(__name__)

_open = open

try:
    from smart_open import smart_open
except ImportError:

    def smart_open(fpath, mode="r", **kwargs):
        fpath = Path(fpath)
        if fpath.suffix in (".gz", ".bz2"):
            if mode == "r":
                mode = "rt"
            elif mode == "w":
                mode = "wt"
        if fpath.suffix == ".gz":
            open_ = gzip.open
        elif fpath.suffix == ".bz2":
            open_ = bz2.open
        else:
            open_ = _open
        return open_(fpath, mode, **kwargs)


def read_json_stream(fpath, lines=False, prefix="item", prog=False, **kwargs):
    # ruff: noqa: PLC0415 - lazy import for optional dependency
    import ijson

    json_lib = kwargs.pop("json_lib", JSON_LIB)

    fpath = Path(fpath)
    if not fpath.exists() or not fpath.is_file():
        raise ValueError(f"Invalid input json: {fpath}")

    with smart_open(fpath, "r") as f:
        logger.debug(f"Loading json stream from path: {fpath}")
        if lines is True:
            for line in tqdm(f, disable=not prog):
                yield json_lib.loads(line, **kwargs)
        else:
            yield from ijson.items(f, prefix)


def read_json(fpath, lines=False, prog=False, **kwargs):
    json_lib = kwargs.pop("json_lib", JSON_LIB)
    with smart_open(fpath) as f:
        if lines:
            return [json_lib.loads(line) for line in tqdm(f, disable=not prog)]
        json_lib.load(f)


def to_json(fpath, data, lines=False, **kwargs):
    kwargs.setdefault("ensure_ascii", False)

    json_lib = kwargs.pop("json_lib", JSON_LIB)
    with smart_open(fpath, "w") as f:
        if lines:
            kwargs.pop("indent", None)
            for d in data:
                f.write(json_lib.dumps(d, **kwargs) + "\n")
        else:
            json_lib.dump(f, data, **kwargs)


def to_csv(fpath, data, headers=None):
    if headers is None:
        headers = data[0].keys()

    with smart_open(fpath, "w") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        for d in data:
            writer.writerow(d)


def base64_encode_bytes(raw, as_ascii=True):
    try:
        import pybase64 as base64_lib
    except ImportError:
        logger.warning("pybase64 import failed, fallback to standard base64 function, may cause performance issues")
        base64_lib = base64
    d = base64_lib.b64encode(raw)
    if as_ascii:
        d = d.decode("ascii")
    return d
