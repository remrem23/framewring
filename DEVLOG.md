**English** · [Русский](#русский)

# Framewring devlog

A chronological record of the development: what was done, why, and what the measurements showed.
Dates are YYYY-MM-DD. All measurements were taken on the author's machine:
16-thread CPU, 31 GB RAM (page file disabled), RTX 5070 Ti,
FFmpeg 8.1.1 (Gyan build), Windows 11, 3 NVMe SSDs + 4 HDDs.

---

## 2026-11-08 — the big pass: bugs, speed, search, usability

### 1. Review of the original version and first fixes

**AV1 crashing on 3440×1440.** By default SVT-AV1 reserves ~6.6 GB
(measured: lp5 6.63 GB, lp4 5.28, lp3 3.91, lp2 2.93). The free commit limit was
~6.8 GB, so the encoder sometimes worked and sometimes failed with `allocate memory failed`.
Fix: the `lp` parallelism level is chosen from the free memory
(`GlobalMemoryStatusEx`); on a memory error the encode is retried automatically with a lower `lp`.

**VMAF was underestimated: ~75 instead of ~96.** The test piece is cut into MKV (timestamps
rounded to 1 ms), the result is MP4 (exact 1/30 s). libvmaf matched frames by
time, and every third frame was compared with its neighbour (per frame: 96, 94, **35**, 96, 94,
**33**…). This pushed users towards unnecessarily high quality and bigger files.
Fix: frames are matched by number (`setpts=N/(30*TB)`); on the same files VMAF became 95–98.

**NVENC "Normal" was 2–3× slower than necessary.** Measured on 2560×1440:

| Setting | Time | Size | VMAF |
|---|---|---|---|
| p7 + fullres | 7.7 s | 26,263 KB | 85.5 |
| p6 + fullres (old "Normal") | 7.1 s | 26,285 KB | 85.6 |
| **p5 + qres (new "Normal")** | **3.4 s** | 26,289 KB | 85.6 |
| p4 + disabled | 3.1 s | 26,286 KB | 85.3 |

On 3440×1440 this is ~58 → ~190 frames/s at the same size and quality.
Hardware decoding gave no speed-up for CPU codecs (x265: 10.2 s without, 11.2 s with `-hwaccel cuda`), so it is not enabled.

**Other fixes in this pass:**
- ffmpeg kept running in the background after the console window was closed → Windows Job Object (`KILL_ON_JOB_CLOSE`), `PR_SET_PDEATHSIG` on Linux. Verified by hard-killing the process.
- "Stop" did not stop a test during cutting and VMAF → all stages go through a shared cancellable launcher.
- `clip.mkv` and `clip.mov` in one folder were both written to `clip.mp4` → names `clip_mkv.mp4` / `clip_mov.mp4`; same-named files in a common output folder → `(2)`.
- Odd resolution (1921×1081) crashed the encoder → cropped to even.
- `-map 0:v:0` could pick cover art instead of the video → `0:V:0`.
- Garbage in `settings.json` crashed compression → values are validated.
- The UI re-rendered the whole list every second: clicks got lost and the progress bar did not animate → targeted DOM updates. File names are escaped (XSS via a file name).
- Files can be queued while compression is running; parallel ffprobe when adding a folder; parallel GPU check at startup.

### 2. Finding heavy videos on the drives

The "Find heavy videos" button: walk the drives, ffprobe the candidates, rough estimate of the size
after compression, choose with checkboxes, add to the queue.
- Skipped: system folders, installed games (their videos must not be touched), OneDrive "online-only" files (reading would download them), junctions.
- Duplicates (same name and size in different places) are flagged; one copy of each group is ticked automatically. On the author's machine duplicates took **395 GB**.
- Editing codecs (ProRes, DNxHD…) are not ticked automatically.
- First pass over 7 drives: 435 videos totalling 1.43 TB, expected savings ~880 GB.

**The port bug.** On Windows a second instance bound to the same port 8765 (`SO_REUSEADDR`
in `HTTPServer`), and the browser reached one instance or the other at random. Fix:
`SO_EXCLUSIVEADDRUSE`; launching again opens the instance that is already running.

### 3. Second bug pass

Confirmed with experiments on small clips, then fixed:
- **Interlaced video** (`.mts` camcorders, TV) was compressed with combing → `bwdif` deinterlacing (50i → 50p); the same filter chain is applied to the original for VMAF (result 96.6).
- **MKV subtitles were silently lost** → text subtitles are carried over as `mov_text`; picture subtitles (PGS) produce a warning.
- **The finished file was open in a player** → it used to fail after hours of work; now the app waits and saves under another name.
- **No free-space check** → checked before starting, with a "tight" warning.
- **File date** → the compressed file gets the original's modification date.
- "Skip already compressed" did not work when a file was re-added in the same session.
- A disconnected network drive froze the drive list → 2 s timeout.

**Faster search:**

| Method | Time (7 drives, ~512k folders) |
|---|---|
| Original walk, sequential | ~176 s (cold cache ~3 min) |
| Multi-threaded walk (8 threads SSD, 3 HDD) | 31 s (6 drives, warm cache) |
| **Everything index via IPC** | **0.04 s per query**, ~5 s for the whole search |

- Everything (voidtools) is queried through `WM_COPYDATA` (QUERY2), without a DLL or es.exe. If it is installed but closed (only the service runs), the app starts it in the tray for the search and closes it. The result matched the full walk: the same 435 files.
- **Without Everything the multi-threaded walk is used automatically.** A "via Everything" checkbox turns the index off.
- Drive type (SSD/HDD) is detected without admin rights (`IOCTL_STORAGE_QUERY_PROPERTY`, SeekPenalty).
- Skipping dot-folders, Unreal caches and Python packages: on a drive with 421k folders a noticeable share were such caches (UE-Cache — 57k, .pnpm-store — 34k).
- ffprobe cache on disk: a repeated search went from 27 s to 5 s.

### 4. Usability and reliability

- **Mode recommendation:** the GPU by default (Nvidia AV1 → Nvidia H.265 → Mac → CPU). Measured: NVENC AV1 ~205 frames/s vs ~30–35 for x265/SVT-AV1 on 3440×1440; the CPU usually gives a 10–20% smaller file. A choice the user saved is not overridden.
- **"Finishing the file" stage.** After 100% ffmpeg rewrites the whole file for `+faststart` and stays silent (3.4 GB on an HDD — 17 s, 7 GB — about a minute). Progress is now computed from the process's written-bytes counter (`GetProcessIoCounters`), with percent, time and an animated bar.
- **Incident:** after an hour of compressing a 76.6 GB → 7.3 GB file, renaming `.part.mp4` failed with `WinError 32` (the file was held by an antivirus or Explorer). The file was intact and was restored by hand. Fix: rename with waiting up to 10 minutes, then a fallback name, then "done, rename it yourself" — work is never lost again.
- **Incident:** `Failed to transfer data to output frame: -12 / Cannot allocate memory` at minute 21. The file was fine (decoding the same spot again worked). Cause: the page file was disabled — commit limit = RAM (31 GB), 8 GB free while 18 GB of physical memory was free. Fix: up to 3 retries on memory errors (the third with CPU decoding) and a UI warning when the page file is off.
- **The task list is saved** (`queue.json`, every 2 s): close the window and everything is there on the next launch. A "↻ Retry" button for errors and cancelled tasks.
- **Compression history** (`history.json`): a separate log independent of the list. At the time of writing: 12 files, 129.8 → 36.7 GB, 93.1 GB freed.
- "📂 Compressed" and "📂 Original" buttons on finished files and in the history.
- A "♥ Support the author" button with USDT wallets (TRC-20, TON) (later removed, see below).

### Name

**Framewring** was chosen (*wring* — to squeeze out: "wringing the frames"): short, and free in search results and on GitHub.

### Summary of the day

The project was prepared for publication: devlog, documentation, local git.

---

## 2026-11-10 — 11-11 — release build, review, English interface

### 1. Version, name and data folder
- Version **0.9.0**, the name in the interface, `CHANGELOG.md`.
- The data folder depends on how the app runs: from source — next to `app.py` (as before);
  portable (a `portable.txt` file next to the exe) — `data\`; installed — `%APPDATA%\Framewring`,
  because a program cannot write into its own install folder.

### 2. Windows exe and own window
- `packaging/build.py`: PyInstaller onedir, icon, FFmpeg (Gyan full build) next to the exe together with its GPL license and source links.
- **Own window** on the Edge engine (WebView2, via pywebview) instead of a console plus a browser tab. Closing during compression asks
  "Stop and quit?". If WebView2 is missing, the app falls back to the browser and says so. Starting it again brings up the open window.
- File dialogs now open inside the process: the exe cannot start a separate `python -c` the way the source version did.
- Without a console, output goes to `framewring.log` in the data folder.
- Size of the first build: 486 MB uncompressed, of which ~454 MB is FFmpeg full build (ffmpeg.exe and ffprobe.exe, 227 MB each).
  A shared or "essentials" FFmpeg build could shrink it — only if it still has libvmaf, SVT-AV1, x265 and NVENC.

### 3. Installer and portable
- `packaging/framewring.iss` (Inno Setup): installs for the current user without admin rights into `%LOCALAPPDATA%\Programs\Framewring`,
  Start menu shortcut, optional desktop shortcut, uninstall via *Apps*; settings and history are kept on uninstall.
- `packaging/release.py` builds the installer (126 MB), the portable zip (188 MB) and `SHA256SUMS.txt`.
  Verified: silent install, launch, uninstall (data stays), portable writes to `data\`.

### 4. Donations via GitHub, Everything hint
- There are no wallet addresses in the program any more. "♥ Support the author" opens a window with a link to
  [DONATE.md](DONATE.md) in the official repository, which only the owner can change, and shows the official address
  of the program. A modified copy cannot quietly swap the addresses. The interface may open only three URLs:
  the repository, the support page and voidtools.com.
- After a long search (> 20 s) without Everything an unobtrusive hint suggests installing it; it can be hidden.
- License: GNU GPL v3.

### 5. Multi-agent review and fixes
Before the release the code was reviewed by several independent automated reviewers; the findings were checked and fixed:
- **Never overwrite originals or unrelated files.** A result written into the source folder gets a `_compressed` suffix; "same folder" is detected
  with `samefile` (works through junctions and different path spellings); which outputs belong to Framewring is remembered
  across sessions via the history; name collisions are checked case-insensitively.
- **Variable frame rate.** VFR MKV recordings were losing frames — now `-fps_mode passthrough`; the test VMAF for VFR video is fixed too.
- **Interface token.** Other local processes could read the token; now the UI is served at a tokenized URL, `/api/status` requires the token,
  and anti-framing headers are sent.
- If WebView2 is missing, the browser fallback comes with a notice.
- **Stop** asks for confirmation; layout fixes for small windows.
- The installer closes a running copy and removes stale files when upgrading.
- The build moved to Python 3.12; the exe got version information; third-party license texts are shipped in a `licenses` folder
  (see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)).

### 6. English interface
- The whole interface is available in 7 languages (English, Russian, German, French, Spanish, Portuguese and Simplified Chinese); a language list in the header, by default following the Windows language.
- **Drag & drop:** files and folders can be dropped onto the window.
- All public documents are now in English first, with the full Russian text below.

### 7. AMD and Intel GPUs
- New modes *AMD GPU · AV1* / *AMD GPU · H.265* (FFmpeg AMF: `av1_amf`, `hevc_amf`) and *Intel GPU · AV1* / *Intel GPU · H.265*
  (Quick Sync: `av1_qsv`, `hevc_qsv`). AMD uses a constant QP (shown as "QP"): 22/24/27 for
  *Maximum / Balanced / Compact* in H.265 (AV1 on AMF uses a 0–255 scale, 88/100/116 ≈ 4× that); Intel uses ICQ (shown as "ICQ"). Nvidia keeps CUDA decoding; AMD and Intel modes decode on the CPU.
- **Measured on real hardware** — the graphics built into a Ryzen 7 9700X, *AMD GPU · H.265*: test VMAF **99.1**,
  a 176 MB 1080p clip → **13.5 MB**, 10-bit output. Calibration: AMF QP 22/24/27 ≈ NVENC CQ 22/24/27 in both size and VMAF,
  so the quality levels mean the same thing on both vendors.
- **AMF 8-bit output was broken:** VMAF ~56 against ~99 for 10-bit on the same clip — so AMD modes always encode 10-bit.
- Every mode is test-encoded on startup; only working ones can be picked. A failed GPU mode is shown greyed out with the reason
  only if that vendor's GPU is present (read from the display adapters in the registry); modes for absent vendors are hidden.
- Recommendation order at first: Nvidia AV1 → AMD AV1 → Intel AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → CPU
  (changed in the final review, see below).
- **Not verified yet:** *AMD GPU · AV1* (needs Radeon RX 7000+) and the Intel modes have not been run on real hardware;
  only the startup test-encode protects them. Reports welcome.

### 8. Final review
Before publishing, four independent reviewers went over the program and the documents in parallel. Fixed after it:
- **Layout at the minimum window size:** the search results list and the history now fit and scroll correctly;
  links are easier to read; the page-file warning can be hidden with ✕ (remembered).
- **Updates:** once per launch the app asks GitHub for the newest version (can be turned off). The installed version
  updates in one click: it downloads the new setup.exe, verifies its SHA-256 against `SHA256SUMS.txt`, installs silently
  and restarts; the installer relaunches the app only after such a self-update (`/FWUPDATE=1`). Verified end-to-end:
  **0.8.0 → 0.9.0 in ~20 s**, settings, queue and history kept.
- **🐞 Report a bug:** opens the GitHub issue form with version, Windows, graphics cards, FFmpeg version and mode pre-filled,
  and can show the log.
- **Recommendation order changed** to Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → AMD AV1 → Intel AV1 → CPU:
  the unverified AMD AV1 and Intel AV1 should not be recommended over a verified H.265.
- `/api/ping` and `/api/show` (used by a second launch) now refuse requests that come from a web page.


## 2026-11-12 — 0.9.1 – 0.9.3: no bloated files, backups, replacing originals

### 1. No results bigger than the original (0.9.1)
Re-encoding an already efficient video (e.g. HEVC at a modest bitrate) could produce a *larger* file after hours of work.
Now the output size is watched during compression: if after 10–25% of the file it is clear the result won't be smaller,
ffmpeg is stopped; a finished result that is not at least 3% smaller is deleted. The video gets the new status
**Kept as is** (original untouched, **↻ Retry** available). Checked: an efficient HEVC was stopped at 17% with no files left;
an ordinary clip went 302 → 100 MB as before. (In 0.9.3 the early stop was reworked to compare with the bytes already
read — see section 6.)

### 2. SVT-AV1 preset 4 for “Thorough” (0.9.2, [#1](https://github.com/remrem23/framewring/issues/1))
6-second synthetic 1080p clip (with noise), *CPU · AV1*, CRF 30 (*Balanced*):

| SVT-AV1 preset | Time | Size |
|---|---|---|
| 6 (*Normal*) | 4.2 s | 5.52 MB |
| 5 (old *Thorough*) | 5.2 s | 4.98 MB |
| 4 (new *Thorough*) | 7.1 s | 4.61 MB |

Preset 4 gives a file ~16% smaller than *Normal* and ~7% smaller than the old *Thorough* at ~1.7× the time of *Normal*
(VMAF 98.2) — worth it for a mode chosen when every gigabyte counts.

### 3. Backups and `.part.mp4` cleanup (0.9.2)
- Settings, history and the queue are written with up to 3 backup copies (the queue at most once every 5 minutes) and are
  restored on start if a file is damaged or the data folder is gone. The installed version keeps them in
  `%LOCALAPPDATA%\Framewring\backup`, away from `%APPDATA%\Framewring`.
- The `.part.mp4` path is stored in the job: removed on exit mid-compression and on the next start after a crash
  (only files ending in `.part.mp4`).
- Installer and update checks in Windows Sandbox.

### 4. Replacing originals (0.9.3)
Compressing alone frees no space, and asking people to delete originals by hand is both tedious and risky. **⇄ Replace originals**
does it, but only for the files the user ticks (nothing is pre-selected) and only after a full check:
- the compressed file is decoded from start to end with no errors; duration and audio-track count must match the original;
- the original's size and date must be the same as at compression (`src_sig`), checked again right before replacing;
- the compressed file is moved next to the original under a temporary name, the **original goes to the Recycle Bin**
  (`SHFileOperationW` + `FOF_ALLOWUNDO`), then the new file takes the original's name with `.mp4`;
- anything failing before the Recycle Bin step leaves everything as it was;
- blocked: not smaller, original changed, a file missing, name taken by another file, drives without a Recycle Bin
  (network/removable — Windows would delete permanently), already replaced; warnings: no Test, Test VMAF < 93,
  editing source, saving < 20%.

Tested: mp4 → mp4 in place; mkv → mp4 next to it; name collision refused; a corrupted compressed file caught
by the decode; a changed original refused; a failed Recycle Bin step fully rolled back.

Also in 0.9.3: a short **How it works** hint on first run, and history **Export… / Import…** (JSON in *Documents*;
import merges and skips duplicates).

### 5. Independent review of Replace
Since Replace is the only feature that removes originals, an adversarial reviewer went through it looking for any way to lose
a file. It found 10 issues: the Recycle Bin quota (a file bigger than the bin's free space is deleted permanently by Windows);
`subst` drives (deleting through the drive letter bypassed the bin); old entries without fingerprints; the compressed file's
identity not verified (it could have been swapped); history indexes shifting after an import; the final rename able to
overwrite; a truncated video passing the check when the audio was full length; lost tracks (subtitles, telemetry,
attachments) not warned about; no guard against replacing a file that is being compressed; no recovery after a crash
mid-replacement. All fixed: `bin_check` (bin settings, policies, free space), the real path for `subst`/mapped drives,
`out_sig`, stable entry keys, rename that never overwrites, a separate full video decode that must reach the end,
`stream_counts` warnings, a `busy` block, the intent recorded in history and `replace_recover()` on start, plus a check that
the original really is in the bin.

Covered by 12 test scenarios: bin too small → blocked; bin turned off → blocked; `subst` drive → real path used; entry
without fingerprints → blocked; compressed file swapped → blocked; history import during a replacement → refused, keys stay
valid; target name taken at the final step → no overwrite; truncated video with full audio → caught; missing subtitle/data
tracks → warned; file in the queue → blocked; crash before the Recycle Bin → rolled back; crash after it → finished.

### 6. Second pass before release (0.9.3)
- **Early stop without false alarms.** Comparing the output with the elapsed percentage stopped videos with a complex
  beginning and a static rest (the output grows fast at first, then barely). Now `_gain_watch` compares the output with the
  bytes of the original that ffmpeg has already read (`GetProcessIoCounters`) — the same part of the video: it stops when
  output ≥ 110% of what was read after ≥ 10% read, or ≥ 102% after ≥ 30%; without read counters (outside Windows) only when
  the output already reaches 97% of the original. The final check (not ≥ 3% smaller → deleted) is unchanged.
- **Checksum.** Size and date can't prove the compressed file is the same file, so a SHA-256 is computed right after
  compression (*Computing the checksum*) and checked again before replacing; entries without it count as old entries.
- **Stricter verification:** the compressed file's audio must be as long as the original's; the duration tolerance is now
  max(1 s, min(3 s, 0.1% of the length)); the Test VMAF is used only if the Test had the same mode and quality as the
  compression.
- **Long paths:** with a path longer than ~250 characters Windows deleted the original permanently instead of recycling it
  (verified), so such files are blocked.
- **Imported history entries** lose their fingerprints and checksum on import and are blocked with their own message.
- **Replace window:** the per-file button highlights its file and pre-ticks it only without warnings; ticking files with
  warnings asks for confirmation; rows show the compressed file's path; results are done / ⚠ warning (original in the bin,
  but not found there or the new file kept its temporary name) / error; only an empty `compressed` folder is removed.
- **Startup and data:** a damaged queue or history entry is skipped instead of preventing start; history writes are
  serialized (no lost updates between compression and replacement); the single-instance mutex is taken before anything
  else; history export goes to the real *Documents* folder (incl. OneDrive) with a timestamped name.

---

## 2026-11-13 — 0.9.4: experimental modes, Share result, builds in GitHub Actions

### 1. Experimental marks for untested modes
Only *AMD GPU · H.265* and the Nvidia and CPU modes have been verified on real hardware. *AMD GPU · AV1*, *Intel GPU · H.265*,
*Intel GPU · AV1* and *Mac GPU · H.265* passed the startup test-encode, but nobody had seen them work on real videos, yet they
could be marked *recommended* and chosen automatically. Now these modes carry an **experimental** label with a hint asking
to share a Test result, and they are no longer recommended or chosen automatically while a tested mode works: on a PC with
only Intel graphics the CPU mode is the recommended one for new users; users who already saved a mode keep it. An experimental
mode can still be picked by hand. A mode confirmed on real hardware loses the label in a later version.

### 2. 📤 Share result
Under a **Test** result there is a new button. It first shows exactly what will be sent, then opens a new ready-filled GitHub
form (*Test result*) with the test numbers (clip length and sizes, forecast, VMAF, times), the video's parameters (codec,
interlacing, resolution, frame rate, bitrate, duration, size, audio codecs), the mode, quality and speed, Windows, CPU, GPU and
driver version, and the FFmpeg and Framewring versions. File names, paths and the user name are never included, and nothing
is sent until the person presses *Submit* on GitHub. This is how the experimental modes get confirmed.

### 3. Builds and tests in GitHub Actions
Releases are now built by GitHub Actions on a clean Windows machine from the public source code, and the installer and
the portable zip get a build provenance attestation (`gh attestation verify <file> -R remrem23/framewring`).
Automatic tests run on every build: safe replacement of originals, history, and real compression on the CPU (x265 and SVT-AV1) —
without a video card and without Everything. A separate `tests.yml` runs them on pushes to `main` and on pull requests.

### 4. Smaller changes
- The **♥ Support the author** window mentions Ko-fi (card, PayPal) next to USDT.
- Housekeeping: the comments in the packaging scripts, the installer script and the CI workflows are translated to English; commit messages are in
  English from now on (see [CONTRIBUTING.md](CONTRIBUTING.md)).
- Still open before 1.0: install via `winget`, a release candidate for testers, and confirmation of the experimental modes
  (see [ROADMAP.md](ROADMAP.md)).

---

<a id="русский"></a>
## Русский

**Девлог Framewring Жмых**

Хронология разработки: что сделано, почему и что показали замеры.
Даты в формате ГГГГ-ММ-ДД. Все замеры сделаны на машине автора:
CPU на 16 потоков, 31 ГБ ОЗУ (файл подкачки выключен), RTX 5070 Ti,
FFmpeg 8.1.1 (сборка Gyan), Windows 11, 3 NVMe SSD + 4 HDD.

### 2026-11-08 — большой проход: баги, скорость, поиск, удобство

#### 1. Ревью исходной версии и первые исправления

**Падение AV1 на 3440×1440.** SVT-AV1 по умолчанию резервирует ~6,6 ГБ
(замер: lp5 6,63 ГБ, lp4 5,28, lp3 3,91, lp2 2,93). Свободного commit-лимита было
~6,8 ГБ, поэтому кодер то работал, то падал с `allocate memory failed`.
Решение: уровень параллельности `lp` подбирается по свободной памяти
(`GlobalMemoryStatusEx`), при ошибке памяти — автоматический повтор с меньшим `lp`.

**VMAF занижался с ~96 до ~75.** Тестовый кусок вырезается в MKV (метки времени
округлены до 1 мс), результат — MP4 (точные 1/30 с). libvmaf сопоставлял кадры по
времени, и каждый третий кадр сравнивался с соседним (по кадрам: 96, 94, **35**, 96, 94,
**33**…). Из-за этого программа подталкивала к завышенному качеству и большим файлам.
Решение: кадры сопоставляются по номеру (`setpts=N/(30*TB)`); на тех же файлах VMAF стал 95–98.

**NVENC «Обычно» был в 2–3 раза медленнее, чем нужно.** Замер на 2560×1440:

| Настройка | Время | Размер | VMAF |
|---|---|---|---|
| p7 + fullres | 7,7 с | 26 263 КБ | 85,5 |
| p6 + fullres (было «Обычно») | 7,1 с | 26 285 КБ | 85,6 |
| **p5 + qres (стало «Обычно»)** | **3,4 с** | 26 289 КБ | 85,6 |
| p4 + disabled | 3,1 с | 26 286 КБ | 85,3 |

На 3440×1440 это ~58 → ~190 кадров/с при том же размере и качестве.
Аппаратное декодирование для кодеков на процессоре ускорения не дало (x265: 10,2 с без, 11,2 с с `-hwaccel cuda`), поэтому не включено.

**Прочее в этом проходе:**
- ffmpeg оставался работать в фоне после закрытия окна консоли → Windows Job Object (`KILL_ON_JOB_CLOSE`), на Linux `PR_SET_PDEATHSIG`. Проверено жёстким убийством процесса.
- «Стоп» не останавливал тест на этапах нарезки и VMAF → все этапы идут через общий запуск с отменой.
- `клип.mkv` и `клип.mov` в одной папке писались в один `клип.mp4` → имена `клип_mkv.mp4` / `клип_mov.mp4`; одноимённые файлы в общей папке вывода → `(2)`.
- Нечётное разрешение (1921×1081) роняло кодер → обрезка до чётного.
- `-map 0:v:0` мог взять обложку вместо видео → `0:V:0`.
- Мусор в `settings.json` ронял сжатие → проверка значений.
- Интерфейс перерисовывал весь список каждую секунду: клики терялись, полоса прогресса не анимировалась → точечное обновление DOM. Экранирование имён файлов (XSS через имя файла).
- Файлы можно ставить в очередь во время сжатия; параллельный ffprobe при добавлении папки; параллельная проверка видеокарты при старте.

#### 2. Поиск тяжёлых видео на дисках

Кнопка «Найти тяжёлые видео»: обход дисков, ffprobe кандидатов, грубая оценка размера
после сжатия, выбор галочками, добавление в очередь.
- Пропускаются системные папки, установленные игры (их ролики трогать нельзя), файлы OneDrive «только в облаке» (чтение скачало бы их), junction-ссылки.
- Дубликаты (то же имя и размер в разных местах) помечаются; автоматически отмечается одна копия из группы. На машине автора дубли заняли **395 ГБ**.
- Монтажные кодеки (ProRes, DNxHD…) не отмечаются автоматически.
- Результат первого прохода по 7 дискам: 435 видео на 1,43 ТБ, ожидаемая экономия ~880 ГБ.

**Баг с портом.** На Windows второй экземпляр садился на тот же порт 8765 (`SO_REUSEADDR`
у `HTTPServer`), и браузер попадал то в один экземпляр, то в другой. Решение:
`SO_EXCLUSIVEADDRUSE`; повторный запуск открывает уже работающую программу.

#### 3. Второй проход по багам

Подтверждено экспериментами на маленьких клипах, затем исправлено:
- **Черезстрочное видео** (камеры `.mts`, ТВ) жалось с «гребёнкой» → деинтерлейс `bwdif` (50i → 50p), та же цепочка фильтров применяется к оригиналу при VMAF (результат 96,6).
- **Субтитры из MKV терялись молча** → текстовые переносятся как `mov_text`; про субтитры-картинки (PGS) — предупреждение.
- **Готовый файл открыт в плеере** → раньше ошибка после часов работы, теперь ожидание и сохранение под другим именем.
- **Нет проверки свободного места** → проверка до старта, предупреждение «впритык».
- **Дата файла** → сжатый файл получает дату изменения оригинала.
- «Пропускать уже сжатые» не срабатывал при повторном добавлении в том же сеансе.
- Отключённый сетевой диск подвешивал список дисков → таймаут 2 с.

**Ускорение поиска:**

| Способ | Время (7 дисков, ~512 тыс. папок) |
|---|---|
| Исходный обход, последовательно | ~176 с (холодный кэш ~3 мин) |
| Многопоточный обход (8 потоков SSD, 3 HDD) | 31 с (6 дисков, тёплый кэш) |
| **Индекс Everything через IPC** | **0,04 с запрос**, ~5 с весь поиск |

- Everything (voidtools) опрашивается через `WM_COPYDATA` (QUERY2), без DLL и es.exe. Если установлен, но закрыт (работает только служба), программа запускает его в трей на время поиска и закрывает. Результат совпал с полным обходом: те же 435 файлов.
- **Если Everything нет — автоматически используется многопоточный обход.** Галочка «через Everything» позволяет отключить индекс.
- Тип диска (SSD/HDD) определяется без прав администратора (`IOCTL_STORAGE_QUERY_PROPERTY`, SeekPenalty).
- Пропуск папок с точкой, кэшей Unreal, Python-пакетов: на диске с 421 тыс. папок заметная часть приходилась на такие кэши (UE-Cache — 57 тыс., .pnpm-store — 34 тыс.).
- Кэш ffprobe на диске: повторный поиск 27 с → 5 с.

#### 4. Удобство и надёжность

- **Рекомендация режима:** видеокарта по умолчанию (Nvidia AV1 → Nvidia H.265 → Mac → процессор). Замер: NVENC AV1 ~205 кадров/с против ~30–35 у x265/SVT-AV1 на 3440×1440; процессор даёт файл обычно на 10–20% меньше. Сохранённый выбор пользователя не перебивается.
- **Этап «Дописываю файл».** После 100% ffmpeg переписывает весь файл ради `+faststart` и молчит (3,4 ГБ на HDD — 17 с, 7 ГБ — около минуты). Теперь прогресс считается по счётчику записанных процессом байт (`GetProcessIoCounters`), с процентами, временем и анимированной полосой.
- **Инцидент:** после часа сжатия файла 76,6 ГБ → 7,3 ГБ переименование `.part.mp4` упало с `WinError 32` (файл держал антивирус или проводник). Файл был целым, восстановлен вручную. Решение: переименование с ожиданием до 10 минут, затем запасное имя, затем «готово, переименуй сам» — работа больше не теряется.
- **Инцидент:** `Failed to transfer data to output frame: -12 / Cannot allocate memory` на 21-й минуте. Файл исправен (повторное декодирование того же места прошло). Причина — выключен файл подкачки: commit-лимит = ОЗУ (31 ГБ), свободно 8 ГБ при 18 ГБ физически свободной памяти. Решение: до 3 повторов при ошибке памяти (третья попытка — с декодированием на процессоре) и предупреждение в интерфейсе, если подкачка выключена.
- **Список задач сохраняется** (`queue.json`, раз в 2 с): закрыл окно — при следующем запуске всё на месте. Кнопка «↻ Повторить» у ошибок и отменённых.
- **История сжатия** (`history.json`): отдельный журнал, не зависит от списка. На момент записи: 12 файлов, 129,8 → 36,7 ГБ, освобождено 93,1 ГБ.
- Кнопки «📂 Сжатый» и «📂 Оригинал» у готовых файлов и в истории.
- Кнопка «♥ Поддержать автора» с кошельками USDT (TRC-20, TON) (позже убрана, см. ниже).

#### Название для английской версии

Выбрано **Framewring** (*wring* — «отжимать»): отсылка к «жмыху», свободно по поиску и на GitHub.
Русская версия называется **Framewring Жмых**, английская — **Framewring**.

#### Итог дня

Проект подготовлен к публикации: девлог, документация, локальный git.

### 2026-11-10 — 11-11 — релизная сборка, ревью, английский интерфейс

#### 1. Версия, название и папка данных
- Версия **0.9.0**, название в интерфейсе, `CHANGELOG.md`.
- Папка данных зависит от способа запуска: из исходников — рядом с `app.py` (как раньше);
  портабл (рядом с exe лежит `portable.txt`) — `data\`; установленная — `%APPDATA%\Framewring`,
  потому что в папку установки программа писать не может.

#### 2. Exe и своё окно
- `packaging/build.py`: PyInstaller onedir, значок, FFmpeg (сборка Gyan full) рядом с exe вместе с лицензией GPL и ссылками на исходники.
- **Своё окно** на движке Edge (WebView2, через pywebview) вместо консоли и вкладки браузера. При закрытии во время сжатия —
  вопрос «Остановить и выйти?». Если WebView2 нет, программа открывается в браузере и сообщает об этом. Повторный запуск поднимает открытое окно.
- Окна выбора файлов открываются внутри процесса: из exe нельзя запустить отдельный `python -c`, как делала версия из исходников.
- Без консоли вывод пишется в `framewring.log` в папке данных.
- Размер первой сборки: 486 МБ без сжатия, из них ~454 МБ — FFmpeg full build (ffmpeg.exe и ffprobe.exe по 227 МБ).
  Сократить можно shared- или essentials-сборкой FFmpeg — только если в ней есть libvmaf, SVT-AV1, x265 и NVENC.

#### 3. Установщик и портабл
- `packaging/framewring.iss` (Inno Setup): установка для текущего пользователя без прав администратора в `%LOCALAPPDATA%\Programs\Framewring`,
  ярлык в «Пуске», по желанию на рабочем столе, удаление через «Приложения»; настройки и история при удалении сохраняются.
- `packaging/release.py` собирает установщик (126 МБ), портабл-zip (188 МБ) и `SHA256SUMS.txt`.
  Проверено: тихая установка, запуск, удаление (данные остаются), портабл пишет в `data\`.

#### 4. Донат через GitHub, подсказка про Everything
- Адресов кошельков в программе больше нет. «♥ Поддержать автора» открывает окно со ссылкой на
  [DONATE.md](DONATE.md#русский) в официальном репозитории (менять его может только владелец) и показывает официальный адрес программы.
  Изменённая копия не может незаметно подменить реквизиты. Интерфейс может открыть только три адреса:
  репозиторий, страницу поддержки и voidtools.com.
- После долгого поиска (> 20 с) без Everything — ненавязчивая подсказка установить его; её можно скрыть.
- Лицензия: GNU GPL v3.

#### 5. Ревью несколькими агентами и исправления
Перед релизом код проверили несколько независимых автоматических ревьюеров; находки проверены и исправлены:
- **Никогда не перезаписывать оригинал или чужой файл.** Результат в папке оригинала получает суффикс `_compressed`; «та же папка»
  определяется через `samefile` (работает и через junction-ссылки, и при разном написании пути); какие файлы созданы Framewring,
  запоминается между сеансами по истории; совпадение имён проверяется без учёта регистра.
- **Переменная частота кадров.** VFR-записи в MKV теряли кадры — теперь `-fps_mode passthrough`; VMAF теста для таких видео тоже исправлен.
- **Токен интерфейса.** Другие локальные процессы могли его прочитать; теперь интерфейс открывается по адресу с токеном,
  `/api/status` требует токен, добавлены заголовки против встраивания в чужие страницы.
- Если нет WebView2 — переход в браузер с объяснением.
- **«Стоп»** спрашивает подтверждение; вёрстка исправлена для маленьких окон.
- Установщик при обновлении закрывает запущенную программу и удаляет устаревшие файлы.
- Сборка переведена на Python 3.12; у exe появились сведения о версии; тексты лицензий сторонних компонентов лежат в папке `licenses`
  (см. [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md#русский)).

#### 6. Английский интерфейс
- Весь интерфейс доступен на 7 языках (русский, английский, немецкий, французский, испанский, португальский и китайский (упрощённый)); выбор языка в шапке, по умолчанию — язык Windows.
  Заголовок окна по-английски — **Framewring**, по-русски — **Framewring Жмых**.
- **Перетаскивание:** файлы и папки можно бросить прямо в окно.
- Все публичные документы теперь сначала на английском, ниже — полный русский текст.

#### 7. Видеокарты AMD и Intel
- Новые режимы «Видеокарта AMD · AV1» / «Видеокарта AMD · H.265» (AMF в FFmpeg: `av1_amf`, `hevc_amf`) и «Видеокарта Intel · AV1» /
  «Видеокарта Intel · H.265» (Quick Sync: `av1_qsv`, `hevc_qsv`). У AMD постоянный QP (в интерфейсе — «QP»): 22/24/27
  для «Максимальное / Баланс / Компактное» в H.265 (AV1 у AMF — шкала 0–255, 88/100/116 ≈ 4× от этого); у Intel — ICQ (в интерфейсе — «ICQ»). Nvidia по-прежнему декодирует через CUDA; режимы AMD и Intel
  декодируют на процессоре.
- **Замер на реальном железе** — графика, встроенная в Ryzen 7 9700X, «Видеокарта AMD · H.265»: VMAF теста **99,1**,
  ролик 1080p 176 МБ → **13,5 МБ**, на выходе 10 бит. Калибровка: AMF QP 22/24/27 ≈ NVENC CQ 22/24/27 и по размеру, и по VMAF —
  уровни качества значат одно и то же у обоих производителей.
- **8-битный вывод AMF был сломан:** VMAF ~56 против ~99 у 10 бит на том же ролике — поэтому режимы AMD всегда кодируют в 10 бит.
- При запуске каждый режим проверяется пробным кодированием; выбрать можно только работающие. Режим видеокарты, не прошедший
  проверку, показывается серым с причиной, только если видеокарта этого производителя есть (по видеоадаптерам в реестре);
  режимы отсутствующих производителей скрыты.
- Порядок рекомендации сначала: Nvidia AV1 → AMD AV1 → Intel AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → процессор
  (изменён на финальном ревью, см. ниже).
- **Ещё не проверено:** «Видеокарта AMD · AV1» (нужна Radeon RX 7000+) и режимы Intel на реальном железе не запускались;
  их страхует только пробное кодирование при запуске. Отчёты приветствуются.

#### 8. Финальное ревью
Перед публикацией программу и документы параллельно проверили четыре независимых ревьюера. По итогам исправлено:
- **Вёрстка при минимальном размере окна:** список результатов поиска и история теперь помещаются и листаются правильно;
  ссылки стало легче читать; предупреждение о файле подкачки можно скрыть крестиком ✕ (запоминается).
- **Обновления:** один раз при запуске программа спрашивает у GitHub номер новейшей версии (можно отключить). Установленная
  версия обновляется в один клик: скачивает новый setup.exe, сверяет SHA-256 с `SHA256SUMS.txt`, тихо устанавливает
  и перезапускается; установщик перезапускает программу только после такого самообновления (`/FWUPDATE=1`). Проверено
  целиком: **0.8.0 → 0.9.0 примерно за 20 с**, настройки, очередь и история сохранились.
- **«🐞 Сообщить об ошибке»:** открывает форму issue на GitHub с заполненными версией, Windows, видеокартами, версией FFmpeg
  и режимом и умеет показать журнал.
- **Порядок рекомендации изменён** на Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → AMD AV1 → Intel AV1 → процессор:
  непроверенные AMD AV1 и Intel AV1 не должны рекомендоваться раньше проверенного H.265.
- `/api/ping` и `/api/show` (ими пользуется второй запуск) теперь отклоняют запросы с веб-страниц.

### 2026-11-12 — 0.9.1 – 0.9.3: без раздутых файлов, резервные копии, замена оригиналов

#### 1. Никаких результатов крупнее оригинала (0.9.1)
Пережатие уже эффективного видео (например, HEVC с умеренным битрейтом) могло после часов работы дать файл *больше*
оригинала. Теперь размер результата отслеживается во время сжатия: если через 10–25% файла видно, что меньше не выйдет,
ffmpeg останавливается; готовый результат, который не меньше оригинала хотя бы на 3%, удаляется. Видео получает новый статус
**«Оставлен как есть»** (оригинал не тронут, «↻ Повторить» доступна). Проверено: эффективный HEVC остановлен на 17%, файлов
не осталось; обычный ролик, как и раньше, сжат 302 → 100 МБ. (В 0.9.3 ранняя остановка переделана: сравнение с уже
прочитанными байтами — см. раздел 6.)

#### 2. Пресет 4 у SVT-AV1 для «Тщательно» (0.9.2, [#1](https://github.com/remrem23/framewring/issues/1))
Синтетический ролик 1080p на 6 секунд (с шумом), «Процессор · AV1», CRF 30 («Баланс»):

| Пресет SVT-AV1 | Время | Размер |
|---|---|---|
| 6 («Обычно») | 4,2 с | 5,52 МБ |
| 5 (прежнее «Тщательно») | 5,2 с | 4,98 МБ |
| 4 (новое «Тщательно») | 7,1 с | 4,61 МБ |

Пресет 4 даёт файл примерно на 16% меньше, чем «Обычно», и на ~7% меньше прежнего «Тщательно» при времени ~1,7× от «Обычно»
(VMAF 98,2) — оправдано для режима, который выбирают, когда важен каждый гигабайт.

#### 3. Резервные копии и уборка `.part.mp4` (0.9.2)
- Настройки, история и очередь пишутся с резервными копиями (до 3; очередь — не чаще раза в 5 минут) и восстанавливаются
  при запуске, если файл повреждён или папки данных нет. Установленная версия хранит их в `%LOCALAPPDATA%\Framewring\backup`,
  отдельно от `%APPDATA%\Framewring`.
- Путь к `.part.mp4` запоминается в задаче: файл удаляется при выходе посреди сжатия и при следующем запуске после сбоя
  (только файлы на `.part.mp4`).
- Проверка установщика и обновлений в «Песочнице Windows».

#### 4. Замена оригиналов (0.9.3)
Само сжатие места не освобождает, а удалять оригиналы вручную и долго, и рискованно. «⇄ Заменить оригиналы» делает это,
но только для файлов, отмеченных пользователем (заранее ничего не отмечено), и только после полной проверки:
- сжатый файл декодируется от начала до конца без ошибок; длительность и число звуковых дорожек совпадают с оригиналом;
- размер и дата оригинала такие же, как при сжатии (`src_sig`), — это проверяется ещё раз прямо перед заменой;
- сжатый файл переносится к оригиналу под временным именем, **оригинал уходит в корзину** (`SHFileOperationW` + `FOF_ALLOWUNDO`),
  затем новый файл получает имя оригинала с `.mp4`;
- любой сбой до шага с корзиной оставляет всё как было;
- запреты: не меньше оригинала, оригинал изменён, файла нет, имя занято другим файлом, диск без корзины (сетевой/съёмный —
  Windows удалила бы насовсем), уже заменён; предупреждения: не было «Теста», VMAF теста < 93, монтажный исходник, выигрыш < 20%.

Проверено тестами: mp4 → mp4 на месте; mkv → mp4 рядом; отказ при совпадении имени; повреждённый сжатый файл
пойман декодированием; изменённый оригинал отклонён; сбой на шаге с корзиной полностью откатывается.

Ещё в 0.9.3: короткая подсказка «Как это работает» при первом запуске и «Экспорт… / Импорт…» истории (JSON в «Документах»;
импорт добавляет записи и пропускает дубли).

#### 5. Независимое ревью замены
Замена — единственная функция Жмыха, которая убирает оригиналы, поэтому её прошёл ревьюер-«противник», искавший любой способ
потерять файл. Он нашёл 10 проблем: квота корзины (файл больше свободного места корзины Windows удаляет насовсем); диски `subst`
(удаление через букву диска шло мимо корзины); старые записи без отпечатков; подлинность сжатого файла не проверялась (его
могли подменить); сдвиг номеров в истории после импорта; финальное переименование могло перезаписать файл; обрезанное видео
проходило проверку, если звук был полной длины; о потерянных дорожках (субтитры, телеметрия, вложения) не предупреждали;
не было защиты от замены файла, который сейчас сжимается; не было восстановления после сбоя посреди замены. Всё исправлено:
`bin_check` (настройки корзины, политики, свободное место), настоящий путь для `subst` и подключённых дисков, `out_sig`,
устойчивые ключи записей, переименование без перезаписи, отдельное полное декодирование видео до конца, предупреждения
`stream_counts`, запрет `busy`, намерение в истории и `replace_recover()` при запуске, плюс проверка, что оригинал
действительно в корзине.

Покрыто 12 тестовыми сценариями: корзина мала → запрет; корзина отключена → запрет; диск `subst` → берётся настоящий путь;
запись без отпечатков → запрет; сжатый файл подменён → запрет; импорт истории во время замены → отказ, ключи не сбиваются;
целевое имя занято на последнем шаге → без перезаписи; обрезанное видео при полном звуке → поймано; нет дорожек
субтитров/данных → предупреждение; файл в очереди → запрет; сбой до корзины → откат; сбой после корзины → доделано.

#### 6. Второй проход перед релизом (0.9.3)
- **Ранняя остановка без ложных срабатываний.** Сравнение результата с прошедшим процентом останавливало видео со сложным
  началом и статичным продолжением (сначала результат растёт быстро, потом почти не растёт). Теперь `_gain_watch` сравнивает
  результат с объёмом оригинала, который ffmpeg уже прочитал (`GetProcessIoCounters`), — с тем же участком видео:
  остановка, если результат ≥ 110% прочитанного при прочитанных ≥ 10%, или ≥ 102% при ≥ 30%; без счётчиков чтения
  (не в Windows) — только когда результат уже достиг 97% оригинала. Итоговая проверка (меньше не хотя бы на 3% → удаляется)
  не изменилась.
- **Контрольная сумма.** Размер и дата не доказывают, что сжатый файл тот же самый, поэтому сразу после сжатия считается
  SHA-256 («Считаю контрольную сумму»), и перед заменой она сверяется ещё раз; записи без неё считаются записями старой версии.
- **Проверка строже:** звук сжатого файла должен быть не короче звука оригинала; допуск длительности теперь
  max(1 с, min(3 с, 0,1% длины)); VMAF теста учитывается, только если тест был с теми же режимом и качеством, что и сжатие.
- **Длинные пути:** при пути длиннее ~250 символов Windows удаляла оригинал насовсем, мимо корзины (проверено), поэтому такие
  файлы заблокированы.
- **Импортированные записи истории** при импорте теряют отпечатки и контрольную сумму и блокируются со своим сообщением.
- **Окно замены:** кнопка у файла подсвечивает его и отмечает, только если нет предупреждений; при выборе файлов
  с предупреждениями программа переспрашивает; в строках виден путь к сжатому файлу; итог — готово / предупреждение ⚠
  (оригинал в корзине, но его там не нашли или новый файл остался с временным именем) / ошибка; убирается только пустая
  папка `compressed`.
- **Запуск и данные:** испорченная запись очереди или истории пропускается и не мешает запуску; записи истории идут по одной
  (обновления из сжатия и замены не теряются); мьютекс единственного экземпляра берётся раньше всего остального; экспорт
  истории — в настоящую папку «Документы» (в т.ч. OneDrive) под именем с датой и временем.

### 2026-11-13 — 0.9.4: экспериментальные режимы, «Поделиться результатом», сборка в GitHub Actions

#### 1. Пометка «экспериментальный» у непроверенных режимов
На реальном железе проверены только «Видеокарта AMD · H.265», режимы Nvidia и процессора. «Видеокарта AMD · AV1»,
«Видеокарта Intel · H.265», «Видеокарта Intel · AV1» и «Видеокарта Mac · H.265» проходили пробное кодирование при запуске,
но на настоящих видео их работу никто не видел, а получать пометку «рекомендую» и выбираться автоматически они могли.
Теперь у этих режимов стоит пометка **«экспериментальный»** с подсказкой поделиться результатом «Теста», и пока работает
проверенный режим, они не рекомендуются и не выбираются сами: на компьютере только с графикой Intel новым пользователям
рекомендуется режим на процессоре; у тех, кто уже сохранил режим, он остаётся. Выбрать экспериментальный режим вручную
по-прежнему можно. Режим, подтверждённый на реальном железе, теряет пометку в одной из следующих версий.

#### 2. «📤 Поделиться результатом»
Под результатом «Теста» появилась кнопка. Сначала она показывает, что именно отправится, затем открывает новую заполненную
форму на GitHub (*Test result*): цифры теста (длина и размеры куска, прогноз, VMAF, время), параметры видео (кодек,
чересстрочность, разрешение, частота кадров, битрейт, длительность, размер, аудиокодеки), режим, качество и скорость,
Windows, процессор, видеокарта и версия драйвера, версии FFmpeg и Framewring. Имена файлов, пути и имя пользователя
не попадают в форму никогда, и ничего не отправится, пока человек не нажмёт *Submit* на GitHub. Так подтверждаются
экспериментальные режимы.

#### 3. Сборка и тесты в GitHub Actions
Релизы теперь собирает GitHub Actions на чистой Windows из открытого исходного кода, а установщик и портабл-архив получают
подтверждение происхождения (`gh attestation verify <файл> -R remrem23/framewring`). При каждой сборке идут автоматические
тесты: безопасная замена оригиналов, история и настоящее сжатие на процессоре (x265 и SVT-AV1) — без видеокарты
и без Everything. Отдельный `tests.yml` запускает их при push в `main` и в pull request.

#### 4. Мелочи
- В окне **«♥ Поддержать автора»** упомянут Ko-fi (карта, PayPal) рядом с USDT.
- Порядок в репозитории: комментарии в скриптах сборки, установщике и CI-сценариях переведены на английский; сообщения коммитов
  отныне пишутся по-английски (см. [CONTRIBUTING.md](CONTRIBUTING.md#русский)).
- До 1.0 остаются: установка через `winget`, релиз-кандидат для тестировщиков и подтверждение экспериментальных режимов
  (см. [ROADMAP.md](ROADMAP.md#русский)).
