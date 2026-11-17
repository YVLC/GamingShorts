# Cairn — Rainbow v1 (direct free Garret speech)

This pack contains the **already generated** 20.11-second Garret — Bold & Persuasive WAV reference and **real six-line timestamps**, from one `heygen-voice-1-turbo-free` HeyGen speech call in ChatGPT. No further synthesis is required. It does **not** include high-resolution video; your WSL2 server will render from the original recording. Only the `rainbow_v1` plan is covered.

Copy/extract the folder `Cairn_Rainbow_Garret_DirectVoice` to `D:\GamingShorts\ChatGPTPlans\`.

Run in Ubuntu:

```bash
python3 /mnt/d/GamingShorts/ChatGPTPlans/Cairn_Rainbow_Garret_DirectVoice/install_saved_voice.py
python3 /mnt/d/GamingShorts/ChatGPTPlans/Cairn_Rainbow_Garret_DirectVoice/install_saved_voice.py --apply
cd /mnt/d/GamingShorts/Automation/gamingshorts_v2
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_rainbow_v1" --stop-after voice
```

**Important:** `--stop-after voice` should *reuse* `voice_result.json`, download the original generated audio file, and split it into the six scenes. If the remote HeyGen WAV URL has expired, it will stop; do not rerun speech synthesis or use `--retry-voice` without reviewing first. The audio may have small natural gaps between narration lines. Listen before rendering or publishing.

When ready, render with:

```bash
python3 start.py --project "/mnt/d/GamingShorts/Projects/V2/videoplayback_2_c8aec7b5_chatgpt_rainbow_v1"
```

Rendering requires existing licensed music configured on your server, may be CPU intensive and checks the original source hash. Publishing remains manual/approval-gated. Minor-spoiler cards should be checked visually.
