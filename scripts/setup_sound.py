# -*- coding: utf-8 -*-
"""검사가 끝나면 소리로 알리도록 Claude Code 설정에 훅을 넣는다.

쓰임:
  python setup_sound.py            # 지금 상태만 보여 준다 (아무것도 안 바꾼다)
  python setup_sound.py --on       # 답변이 끝날 때 소리 (Stop 훅)
  python setup_sound.py --on --notify   # 물어볼 때도 소리 (Notification 훅)
  python setup_sound.py --off      # 이 도구가 넣은 훅만 뺀다
  python setup_sound.py --sound <파일.wav>   # 쓸 소리 파일 지정

왜 따로 두나
  소리 알림은 **스킬이 아니라 설정 파일(settings.json)에 사는 물건**이다.
  스킬 폴더만 복사하면 따라오지 않는다. 그래서 새 컴퓨터에서는 이 도구를
  한 번 돌려야 한다.

무엇을 건드리나
  `~/.claude/settings.json` 의 `hooks` 항목만 건드린다. 다른 설정은 그대로
  둔다. **고치기 전에 `settings.json.bak` 으로 복사본을 남긴다.**
  이미 소리를 내는 훅이 있으면 **덮어쓰지 않고 그대로 둔다.**

되돌리기
  `--off` 를 쓰거나, `settings.json.bak` 을 되돌려 놓으면 된다.
"""
import io
import os
import sys
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MARK = "claude-paper-sound"   # 이 도구가 넣은 훅임을 알아보는 표식


def opt(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def settings_path():
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "settings.json")


def find_sound(given=None):
    """쓸 소리 파일을 고른다. 없으면 None (그때는 삑 소리로 대신한다)."""
    if given and os.path.exists(given):
        return os.path.abspath(given)
    # 스킬에 딸려 온 소리 (다른 컴퓨터에서도 이건 항상 있다)
    packed = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "assets", "done.wav")
    packed = os.path.normpath(packed)
    home = os.path.expanduser("~")
    mine = os.path.join(home, ".claude", "sounds")
    if os.path.isdir(mine):
        for f in sorted(os.listdir(mine)):
            if f.lower().endswith((".wav", ".aiff", ".oga", ".ogg", ".mp3")):
                return os.path.join(mine, f)
    if os.path.exists(packed):
        return packed
    if sys.platform == "win32":
        for f in ("Windows Notify System Generic.wav", "notify.wav",
                  "Windows Ding.wav", "chimes.wav"):
            p = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"),
                             "Media", f)
            if os.path.exists(p):
                return p
    elif sys.platform == "darwin":
        p = "/System/Library/Sounds/Glass.aiff"
        if os.path.exists(p):
            return p
    else:
        for p in ("/usr/share/sounds/freedesktop/stereo/complete.oga",
                  "/usr/share/sounds/alsa/Front_Center.wav"):
            if os.path.exists(p):
                return p
    return None


def hook_entry(sound):
    """운영체제에 맞는 훅 하나를 만든다. 표식(MARK)을 붙여 나중에 찾는다."""
    if sys.platform == "win32":
        if sound:
            ps = ("$ErrorActionPreference='SilentlyContinue';"
                  " # " + MARK + chr(10) +
                  "(New-Object Media.SoundPlayer '" + sound + "').PlaySync()")
        else:
            ps = ("# " + MARK + chr(10) + "[console]::beep(880,180)")
        return {"type": "command", "command": "powershell",
                "args": ["-NoProfile", "-Command", ps],
                "async": True, "timeout": 10}
    if sys.platform == "darwin":
        cmd = ("afplay '%s' # %s" % (sound, MARK)) if sound \
            else ("printf '\\a' # %s" % MARK)
    else:
        if sound and sound.endswith((".oga", ".ogg")):
            cmd = "paplay '%s' # %s" % (sound, MARK)
        elif sound:
            cmd = "aplay -q '%s' # %s" % (sound, MARK)
        else:
            cmd = "printf '\\a' # %s" % MARK
    return {"type": "command", "command": cmd, "async": True, "timeout": 10}


def has_sound_hook(cfg, event):
    """그 자리에 이미 소리를 내는 훅이 있는가."""
    keys = ("soundplayer", "afplay", "aplay", "paplay", "beep", ".wav",
            "\\a", "powershell")
    blob = json.dumps(cfg.get("hooks", {}).get(event, []), ensure_ascii=False)
    return any(k.lower() in blob.lower() for k in keys)


def show(cfg, path):
    print("설정 파일: %s" % path)
    print("")
    for ev, what in (("Stop", "답변이 끝날 때"), ("Notification", "물어볼 때")):
        n = len(cfg.get("hooks", {}).get(ev, []))
        mark = " (이 도구가 넣은 것)" if MARK in json.dumps(
            cfg.get("hooks", {}).get(ev, []), ensure_ascii=False) else ""
        state = "소리 남" if has_sound_hook(cfg, ev) else "없음"
        print("- %-12s %-10s : %s%s  (훅 %d개)" % (ev, what, state, mark, n))
    print("")
    print("켜려면  : python setup_sound.py --on")
    print("물어볼 때도 : python setup_sound.py --on --notify")
    print("끄려면  : python setup_sound.py --off")


def main():
    path = settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg = {}
    if os.path.exists(path):
        try:
            cfg = json.load(open(path, encoding="utf-8"))
        except ValueError as e:
            print("설정 파일이 깨져 있다. 고치지 않고 멈춘다: %s" % e)
            return

    if "--off" not in sys.argv and "--on" not in sys.argv:
        show(cfg, path)
        return

    shutil.copyfile(path, path + ".bak") if os.path.exists(path) else None
    cfg.setdefault("hooks", {})

    if "--off" in sys.argv:
        gone = 0
        for ev in ("Stop", "Notification"):
            keep = []
            for group in cfg["hooks"].get(ev, []):
                if MARK in json.dumps(group, ensure_ascii=False):
                    gone += 1
                    continue
                keep.append(group)
            if keep:
                cfg["hooks"][ev] = keep
            elif ev in cfg["hooks"]:
                del cfg["hooks"][ev]
        if not cfg["hooks"]:
            del cfg["hooks"]
        json.dump(cfg, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("이 도구가 넣은 훅 %d개를 뺐다. 남의 훅은 그대로 뒀다." % gone)
        print("복사본: %s.bak" % path)
        return

    sound = find_sound(opt("--sound"))
    events = ["Stop"] + (["Notification"] if "--notify" in sys.argv else [])
    added, kept = [], []
    for ev in events:
        if has_sound_hook(cfg, ev):
            kept.append(ev)
            continue
        cfg["hooks"].setdefault(ev, []).append({"hooks": [hook_entry(sound)]})
        added.append(ev)
    json.dump(cfg, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("설정 파일: %s" % path)
    print("소리 파일: %s" % (sound or "없음 (삑 소리로 대신한다)"))
    if added:
        print("넣은 것: %s" % ", ".join(added))
    if kept:
        print("이미 소리가 나고 있어 건드리지 않은 것: %s" % ", ".join(kept))
    print("복사본: %s.bak" % path)
    print("")
    print("**Claude Code를 껐다 켜야 적용된다.**")


if __name__ == "__main__":
    main()
