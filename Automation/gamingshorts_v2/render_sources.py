"""Explicit original-media resolution, fragment maps and source-sized framing."""

from fractions import Fraction
from pathlib import Path
from quality_checks import production_source, rate
from common import digest, key, read, save
from quality_checks import measure_cadence, compare_cadence
import shutil
import os
import subprocess
import math


def tracking_path(points, duration):
    if not isinstance(points,list) or not 1<=len(points)<=120:raise ValueError('Tracking needs 1-120 keyframes')
    cleaned=[];last=-1
    for point in points:
        at=float(point['at']);x=float(point['x']);cut=point.get('cut',False)
        if not math.isfinite(at+x) or not 0<=at<=duration or at<=last or not 0<=x<=1 or not isinstance(cut,bool):raise ValueError('Invalid subject tracking keyframe')
        cleaned.append({'at':at,'x':x,'cut':cut});last=at
    if cleaned[0]['at']!=0:raise ValueError('Tracking must start at zero')
    return cleaned


def tracked_filters(source,cfg):
    w,h=int(cfg['width']),int(cfg['height']);sw,sh=source['width'],source['height']
    top=float(source.get('trim_top',0));bottom=float(source.get('trim_bottom',0))
    if not math.isfinite(top+bottom) or not 0<=top<=.25 or not 0<=bottom<=.25 or top+bottom>.3:
        raise ValueError('Invalid source edge trim')
    active_h=sh*(1-top-bottom)
    crop_h=min(active_h,sw*h/w);crop_w=crop_h*w/h
    crop_y=sh*top+(active_h-crop_h)/2
    if max(w/crop_w,h/crop_h)>1.5:raise ValueError('Tracking crop would excessively enlarge source pixels')
    points=tracking_path(source.get('tracking',[{'at':0,'x':.5}]),source['duration'])
    positions=[max(0,min(sw-crop_w,sw*p['x']-crop_w/2)) for p in points]
    expression=f'{positions[-1]:.6f}'
    for i in range(len(points)-2,-1,-1):
        a,b=points[i],points[i+1]
        value=f'{positions[i]:.6f}' if b['cut'] else f'({positions[i]:.6f}+({positions[i+1]-positions[i]:.6f})*(t-{a["at"]:.6f})/{b["at"]-a["at"]:.6f})'
        expression=f'if(lt(t,{b["at"]:.6f}),{value},{expression})'
    graph=(f"crop={crop_w:.6f}:{crop_h:.6f}:x='{expression}':y={crop_y:.6f},"
           f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1')
    # Match a stable source/crop sample, excluding the caption band. A camera
    # cut resets the crop rather than adding an artificial pan between shots.
    caption_y=float(source.get('caption_y',.82));ry,rh=(.40,.55) if caption_y<.4 else (.05,.60)
    probe_seconds=min(3.,source['duration'])
    cuts=[p['at'] for p in points[1:] if p['cut'] and p['at']>0]
    if cuts:probe_seconds=min(probe_seconds,max(.25,cuts[0]-.02))
    return graph,{'mode':'tracked_cover','full_frame':True,'background':None,
        'source_width':sw,'source_height':sh,'foreground':'original pixels; uniform scale; keyframed subject tracking',
        'tracking':points,'source_roi':(positions[0]/sw,(crop_y+ry*crop_h)/sh,crop_w/sw,rh*crop_h/sh),
        'output_roi':(0,ry,1,rh),'cadence_sample_seconds':probe_seconds}


def resolve(manifest, clip, probe):
    start = float(clip["start"])
    seconds = float(clip["duration"])
    source = Path(manifest["source"])
    sha = manifest["source_sha256"]
    offset = 0.0
    if manifest.get("source_bundle"):
        segments = [
            s
            for s in manifest["source_bundle"]["segments"]
            if float(s["timeline_start"]) <= start + 0.00001
            and start + seconds <= float(s["timeline_end"]) + 0.00001
        ]
        if len(segments) != 1:
            raise ValueError("Clip must lie within one verified original fragment")
        segment = segments[0]
        source = Path(segment["path"])
        sha = segment["sha256"]
        offset = float(segment["timeline_start"]) - float(segment.get("media_start", 0))
    production_source(source)
    metadata = probe(source)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    local = start - offset
    if local < -0.001 or local + seconds > float(metadata["format"]["duration"]) + 0.04:
        raise ValueError("Selected timestamp exceeds original media fragment")
    fps = rate(video.get("avg_frame_rate")) or rate(video.get("r_frame_rate"))
    if not fps:
        raise ValueError("Unknown source frame cadence")
    return {
        "path": source,
        "sha256": sha,
        "start": max(0.0, local),
        "duration": seconds,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
        "timeline_start": start,
    }


def delivery_rate(sources, cap):
    # An explicit export cap may reduce cadence; it can never fabricate a higher
    # source rate. Keep rational rates, including 60000/1001.
    return min([Fraction(str(cap))] + [source["fps"] for source in sources])


def picture_filters(source, cfg, framing="auto"):
    w, h = int(cfg["width"]), int(cfg["height"])
    if framing=='tracked_cover':return tracked_filters(source,cfg)
    if framing=='dialogue_portrait':
        # A larger portrait picture, with space below for faithful source text.
        # Focus is framing only; it never changes source chronology or cadence.
        panel_h=round(h*.64/2)*2;top=round(h*.025/2)*2
        # Source dialogue is faithfully re-typeset below. Exclude its original
        # lower UI strip from both picture and decorative background so cropped
        # subtitle fragments never compete with the accessible text.
        crop_h=round(source['height']*.78/2)*2
        crop_w=min(float(source['width']),crop_h*w/panel_h)
        focus=float(source.get('focus_x',.43))
        if not 0<=focus<=1:raise ValueError('Invalid dialogue focus position')
        x=max(0.,min(float(source['width'])-crop_w,float(source['width'])*focus-crop_w/2))
        if max(w/crop_w,panel_h/crop_h)>1.5:raise ValueError('Dialogue framing would excessively enlarge original pixels')
        graph=(f'crop=iw:{crop_h}:0:0,split[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase:flags=bilinear,'
            f'crop={w}:{h},boxblur=24:2[blur];[fg]crop={crop_w:.6f}:ih:{x:.6f}:0,scale={w}:{panel_h}:flags=lanczos[sharp];'
            f'[blur][sharp]overlay=0:{top},setsar=1')
        return graph,{'mode':framing,'source_width':source['width'],'source_height':source['height'],
            'foreground':'original pixels; uniform scale','background':'decorative blur outside the picture only',
            'source_roi':(x/source['width'],0,crop_w/source['width'],crop_h/source['height']),'output_roi':(0,top/h,1,panel_h/h),'focus_x':focus,
            'source_subtitle_strip':'excluded; verified exact text displayed once below'}
    crop_width = source["height"] * w / h
    enlargement = max(w / min(source["width"], crop_width), h / source["height"])
    mode = framing
    if mode == "auto":
        mode = "blur_contain" if enlargement > 1.25 else "cover"
    if mode not in ("cover", "blur_contain"):
        raise ValueError("Unknown framing mode")
    if mode == "cover" and enlargement > 1.5:
        raise ValueError(f"Cover crop would enlarge source {enlargement:.2f}x; use blur_contain")
    if mode == "cover":
        graph = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1"
    else:
        graph = (
            f"split[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase:flags=bilinear,"
            f"crop={w}:{h},boxblur=24:2[blur];[fg]scale=w='min({w},iw)':h='min({h},ih)':force_original_aspect_ratio=decrease:flags=lanczos"
            f"[sharp];[blur][sharp]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    return graph, {
        "mode": mode,
        "source_width": source["width"],
        "source_height": source["height"],
        "cover_enlargement": enlargement,
        "foreground": "original pixels; uniform scale",
        "background": "decorative blur only" if mode == "blur_contain" else None,
    }


def encode_shot(project, out, number, source, cfg, graph, fps, framing, runner, probe, duration):
    """Source-aware cache admission; duration and a checksum alone are insufficient."""
    target = Path(out) / f"shot_{number:02d}.mp4"
    identity = key(
        {
            "policy": digest(__file__),
            "qc": digest(Path(__file__).with_name("quality_checks.py")),
            "source": source["sha256"],
            "start": source["start"],
            "duration": source["duration"],
            "filter": graph,
            "fps": str(fps),
            "encoder": cfg.get("encoder", "libx264"),
            "preset": cfg.get("x264_preset", "medium"),
            "crf": cfg["crf"],
            "font": digest(cfg["font"]),
            "caption_assets": {
                asset.name: digest(asset)
                for asset in Path(out).iterdir()
                if asset.is_file()
                and asset.name.startswith(
                    (f"caption_{number}_", f"cta_{number}_", f"karaoke_{number:02d}.")
                )
            },
        }
    )
    cache = Path(project) / "VideoCache" / identity
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / "shot.mp4"
    proof = cache / "proof.json"
    seconds = framing.get('cadence_sample_seconds',min(3.0, source["duration"]))
    if framing['mode'] in ('dialogue_portrait','tracked_cover'):
        original_roi=framing['source_roi'];output_roi=framing['output_roi']
    elif framing["mode"] == "cover":
        crop_width = min(1.0, source["height"] * cfg["width"] / cfg["height"] / source["width"])
        original_roi = ((1 - crop_width) / 2, 0.05, crop_width, 0.60)
        output_roi = (0, 0.05, 1, 0.60)
    else:
        foreground_scale=min(1.,cfg['width']/source['width'],cfg['height']/source['height'])
        foreground_height=source['height']*foreground_scale/cfg['height']
        foreground_width=source['width']*foreground_scale/cfg['width']
        original_roi = None
        output_roi = ((1-foreground_width)/2, (1 - foreground_height) / 2, foreground_width, foreground_height)
    source_profile = None
    if proof.exists():
        saved = read(proof)
        source_profile = saved.get("source_cadence")
    if not source_profile:
        source_profile = measure_cadence(
            source["path"], source["start"], seconds, source["fps"], roi=original_roi
        )
    expected = dict(source_profile)
    if expected.get("active_updates_per_second"):
        expected["active_updates_per_second"] = min(
            float(fps), expected["active_updates_per_second"]
        )
    reused = False
    output_profile = None
    if cached.is_file() and proof.is_file():
        saved = read(proof)
        try:
            metadata = probe(cached)
            video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
            if (
                digest(cached) == saved.get("sha256")
                and abs(duration(cached) - source.get('output_duration',source["duration"])) < 0.1
                and (video["width"], video["height"]) == (cfg["width"], cfg["height"])
                and abs(float(rate(video["avg_frame_rate"])) - float(fps)) < 0.1
            ):
                output_profile = measure_cadence(cached, 0, seconds, fps, roi=output_roi)
                if compare_cadence(expected, output_profile)["status"] != "failed":
                    shutil.copy2(cached, target)
                    reused = True
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
            pass
    if not reused:
        encoder = cfg.get("encoder", "libx264")
        if encoder not in ("libx264", "h264_qsv"):
            raise ValueError("Unsupported encoder")
        encargs = (
            ["-threads", "2", "-preset", cfg.get("x264_preset", "medium"), "-crf", cfg["crf"]]
            if encoder == "libx264"
            else ["-preset", "veryfast", "-global_quality", cfg.get("qsv_quality", 22)]
        )
        runner(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-threads",
                "2",
                "-ss",
                source["start"],
                "-i",
                source["path"],
                "-t",
                source.get('output_duration',source["duration"]),
                "-an",
                "-vf",
                graph,
                "-fps_mode",
                "vfr",
                "-c:v",
                encoder,
                *encargs,
                "-pix_fmt",
                "yuv420p",
                "-video_track_timescale",
                "90000",
                target,
            ],
            cwd=out,
            logfile=Path(out) / "ffmpeg.log",
        )
        output_profile = measure_cadence(target, 0, seconds, fps, roi=output_roi)
        comparison = compare_cadence(expected, output_profile)
        if comparison["status"] == "failed":
            raise RuntimeError(comparison["error"])
        temporary = cache / "shot.partial.mp4"
        shutil.copyfile(target, temporary)
        os.replace(temporary, cached)
        save(
            proof,
            {
                "sha256": digest(cached),
                "source_sha256": source["sha256"],
                "source_cadence": source_profile,
                "output_cadence": output_profile,
                "framing": framing,
                "fps": str(fps),
            },
        )
    return target, {
        "source": str(source["path"]),
        "source_start": source["start"],
        "timeline_start": source["timeline_start"],
        "duration": source.get('output_duration',source["duration"]),
        "source_duration":source['duration'],
        "intentional_reading_hold":source.get('output_duration',source['duration'])-source['duration'],
        "source_cadence": source_profile,
        "shot_cadence": output_profile,
        "cadence_comparison": compare_cadence(expected, output_profile),
        "framing": framing,
        "reused": reused,
        "output_roi": output_roi,
        "cadence_sample_seconds":seconds,
    }
