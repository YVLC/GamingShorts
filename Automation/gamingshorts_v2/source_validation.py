"""FFprobe admission checks shared by every production-queue entry point."""

import json
import math
from pathlib import Path
import hashlib
import shutil
import struct
import subprocess
import os
import selectors
import tempfile
import time
from functools import lru_cache

from common import config, key

MEDIA = {".mp4", ".mov", ".mkv", ".webm"}


class SourceValidationError(ValueError):
    def __init__(self, message, *, stderr="", returncode=None, tool="ffprobe"):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode
        self.tool = tool


def source_path(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in MEDIA:
        raise SourceValidationError(
            "Queue source must be an existing MP4, MOV, MKV or WebM recording"
        )
    return path


def fingerprint(stat):
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_dev


@lru_cache(maxsize=16)
def _binary_checksum(path, signature):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validator_key(tool):
    executable = shutil.which(tool)
    if not executable:
        raise SourceValidationError(f"Cannot run {tool}: executable not found", tool=tool)
    path = Path(executable).resolve()
    return key(
        {
            "policy": "integrity-v1",
            "tool": tool,
            "path": str(path),
            "binary": _binary_checksum(str(path), fingerprint(path.stat())),
        }
    )


def checked_command(tool, command, timeout):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        stderr = error.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise SourceValidationError(
            f"{tool} timed out after {timeout} seconds:\n{stderr}", stderr=stderr, tool=tool
        ) from error
    except OSError as error:
        raise SourceValidationError(f"Cannot run {tool}: {error}", tool=tool) from error
    if result.returncode or result.stderr:
        raise SourceValidationError(
            f"{tool} rejected the recording (exit {result.returncode}):\n{result.stderr or result.stdout}",
            stderr=result.stderr,
            returncode=result.returncode,
            tool=tool,
        )
    return result


def checked_decode(command, timeout, stall_seconds):
    """Bound both total time and time without advancing frame/timestamp progress."""
    if not all(math.isfinite(value) and value > 0 for value in (timeout, stall_seconds)):
        raise SourceValidationError("Invalid decode deadline configuration", tool="FFmpeg")
    output = bytearray()
    pending = bytearray()
    started = advanced = time.monotonic()
    last_report = started
    latest = {b"frame": -1, b"out_time_us": -1}
    reason = None
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors
            )
        except OSError as error:
            raise SourceValidationError(f"Cannot run FFmpeg: {error}", tool="FFmpeg") from error
        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ)
            while process.poll() is None or selector.get_map():
                current = time.monotonic()
                if current - last_report >= 30:
                    print(f"FFmpeg progress: frame={latest[b'frame']} time_us={latest[b'out_time_us']}", flush=True)
                    last_report = current
                if process.poll() is None:
                    if current - started >= timeout:
                        reason = f"FFmpeg timed out after {timeout} seconds"
                        break
                    if current - advanced >= stall_seconds:
                        reason = f"FFmpeg stalled: no advancing video progress for {stall_seconds} seconds"
                        break
                wait = max(
                    0.01,
                    min(1, timeout - (current - started), stall_seconds - (current - advanced)),
                )
                for event, _ in selector.select(wait):
                    data = os.read(event.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(event.fileobj)
                        continue
                    output.extend(data)
                    if len(output) > 131072:
                        del output[:-65536]
                    pending.extend(data)
                    while b"\n" in pending:
                        line, _, tail = pending.partition(b"\n")
                        pending = bytearray(tail)
                        name, _, value = bytes(line).partition(b"=")
                        if name in latest:
                            try:
                                number = int(value)
                            except ValueError:
                                continue
                            if number > latest[name]:
                                advanced = time.monotonic()
                                latest[name] = number
            if reason:
                process.kill()
            process.wait(timeout=10)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            raise
        finally:
            selector.close()
            process.stdout.close()
        errors.seek(0)
        stderr = errors.read().decode("utf-8", errors="replace")
        stdout = output.decode("utf-8", errors="replace")
        if reason or process.returncode or stderr:
            raise SourceValidationError(
                f"{reason or f'FFmpeg rejected the recording (exit {process.returncode})'}:\n{stderr}",
                stderr=stderr,
                returncode=process.returncode,
                tool="FFmpeg",
            )
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def check_mp4_extents(path, size):
    """Check top-level atom extents without reading mdat payloads into Python."""
    position = 0
    found = set()
    with path.open("rb") as stream:
        while position < size:
            stream.seek(position)
            header = stream.read(8)
            if len(header) != 8:
                raise SourceValidationError(
                    f"Truncated MP4 atom header at byte {position}: {path}", tool="container"
                )
            length, kind = struct.unpack(">I4s", header)
            header_size = 8
            if length == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    raise SourceValidationError(
                        f"Truncated extended MP4 atom: {path}", tool="container"
                    )
                length = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif length == 0:
                length = size - position
            if length < header_size or position + length > size:
                raise SourceValidationError(
                    f"Truncated/invalid MP4 {kind!r} atom at byte {position}: declared end {position + length}, file size {size}: {path}",
                    tool="container",
                )
            found.add(kind)
            position += length
    if not {b"moov", b"mdat"}.issubset(found):
        raise SourceValidationError(
            f"MP4 lacks self-contained moov/mdat media: {path}", tool="container"
        )


def inspect_source(path, *, details=False):
    path = source_path(path)
    before = path.stat()
    command = [
        "ffprobe",
        "-v",
        "error",
        "-err_detect",
        "explode",
        "-count_packets",
        "-show_error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    # Packet scanning is I/O-bound; 60 GB may legitimately take longer than five minutes.
    probe_deadline = max(config().get("source_probe_timeout_seconds", 300), before.st_size / (2 * 1024 * 1024))
    result = checked_command("FFprobe", command, probe_deadline)
    try:
        document = json.loads(result.stdout)
    except (TypeError, ValueError) as error:
        raise SourceValidationError(
            f"FFprobe returned invalid JSON for {path}:\n{result.stdout}"
        ) from error
    if not isinstance(document, dict) or not isinstance(document.get("streams", []), list):
        raise SourceValidationError(
            f"FFprobe returned invalid metadata for {path}:\n{result.stdout}"
        )
    if not isinstance(document.get("format", {}), dict) or any(
        not isinstance(stream, dict) for stream in document.get("streams", [])
    ):
        raise SourceValidationError(
            f"FFprobe returned invalid stream/container metadata for {path}"
        )
    if document.get("error"):
        raise SourceValidationError(f"FFprobe rejected {path}:\n{document['error']}")
    videos = [
        stream
        for stream in document.get("streams", [])
        if stream.get("codec_type") == "video"
        and not (stream.get("disposition") or {}).get("attached_pic")
    ]
    if not videos or not all(
        stream.get("codec_name") not in (None, "unknown")
        and int(stream.get("width", 0)) > 0
        and int(stream.get("height", 0)) > 0
        for stream in videos
    ):
        raise SourceValidationError(f"FFprobe found no usable video stream in {path}")
    if any(int(stream.get("nb_read_packets", 0)) <= 0 for stream in videos):
        raise SourceValidationError(f"FFprobe found an empty video packet stream in {path}")
    for stream in document.get("streams", []):
        if stream.get("codec_type") in ("video", "audio") and stream.get("codec_name") in (
            None,
            "unknown",
        ):
            raise SourceValidationError(f"FFprobe could not identify a media codec in {path}")
    durations = [document.get("format", {}).get("duration")]
    durations.extend(stream.get("duration") for stream in videos)
    valid_duration = False
    for value in durations:
        try:
            seconds = float(value)
            valid_duration |= math.isfinite(seconds) and seconds > 0
        except (TypeError, ValueError):
            continue
    if not valid_duration:
        raise SourceValidationError(f"FFprobe found no finite positive video duration in {path}")
    if "mov" in document.get("format", {}).get("format_name", "").split(","):
        check_mp4_extents(path, before.st_size)
    if fingerprint(before) != fingerprint(path.stat()):
        raise SourceValidationError(f"Recording changed while FFprobe was validating it: {path}")
    return (path, before, document) if details else (path, before)


def decode_source(path, document, *, timeout=None, start=None, seconds=None, stall_seconds=None):
    """Decode all video streams to the null muxer once; never create/modify media."""
    path = source_path(path)
    before = path.stat()
    if start is not None or seconds is not None:
        if start is None or seconds is None or not all(math.isfinite(v) for v in (start, seconds)) or start < 0 or seconds <= 0:
            raise SourceValidationError("Invalid decode checkpoint range", tool="FFmpeg")
    command = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-xerror",
        "-err_detect",
        "explode",
        "-threads",
        "2",
        "-i",
        str(path),
        "-map",
        "0:v",
        "-an",
        "-sn",
        "-dn",
        "-fps_mode",
        "passthrough",
        # Keep native timestamp precision; inverse average FPS rounds VFR PTS together.
        "-enc_time_base",
        "demux",
        "-progress",
        "pipe:1",
        "-nostats",
        "-f",
        "null",
        "-",
    ]
    if start is not None:
        at = command.index("-i")
        command[at:at] = ["-ss", str(start), "-t", str(seconds)]
    declared_duration = float(document.get("format", {}).get("duration", 0) or 0)
    result = checked_decode(
        command,
        timeout or max(config().get("source_decode_timeout_seconds", 7200), declared_duration * config().get("source_decode_realtime_factor", 32)),
        stall_seconds or config().get("source_decode_stall_seconds", 60),
    )
    progress = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if progress.get("progress") != "end" or int(progress.get("frame", "0")) <= 0:
        raise SourceValidationError(
            f"FFmpeg did not complete a video decode: {path}", tool="FFmpeg"
        )
    videos = [
        stream
        for stream in document["streams"]
        if stream.get("codec_type") == "video"
        and not stream.get("disposition", {}).get("attached_pic")
    ]
    primary = videos[0]
    expected = 0.0
    for candidate in (primary.get("duration"), document.get("format", {}).get("duration")):
        try:
            value = float(candidate)
            if math.isfinite(value) and value > 0:
                expected = value
                break
        except (TypeError, ValueError):
            continue
    numerator, _, denominator = primary.get("avg_frame_rate", "0/1").partition("/")
    fps = float(numerator) / (float(denominator) or 1) if denominator else float(numerator)
    tolerance = max(0.25, 2 / fps if fps > 0 else 0.25)
    if seconds is not None:
        expected = seconds
    decoded = float(progress.get("out_time_us", "0")) / 1_000_000
    if decoded + tolerance < expected:
        raise SourceValidationError(
            f"FFmpeg decoded only {decoded:.3f}s of expected {expected:.3f}s: {path}", tool="FFmpeg"
        )
    if start is None and len([stream for stream in document["streams"] if stream.get("codec_type") == "video"]) == 1:
        try:
            declared_frames = int(primary.get("nb_frames", "0"))
        except (TypeError, ValueError):
            declared_frames = 0
        if int(progress["frame"]) < declared_frames:
            raise SourceValidationError(
                f"FFmpeg decoded only {progress['frame']} of {declared_frames} declared video frames: {path}",
                tool="FFmpeg",
            )
    if fingerprint(before) != fingerprint(path.stat()):
        raise SourceValidationError(
            f"Recording changed during FFmpeg decoding: {path}", tool="filesystem"
        )
    return {"duration_seconds": decoded, "frames": int(progress["frame"])}
