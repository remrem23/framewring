**English** · [Русский](#русский)

# Framewring architecture

The program is `app.py` (~3,400 lines) plus the interface strings in `i18n.py` and `locales/`. It uses only the Python standard library;
[pywebview](https://pywebview.flowrl.com/) is optional and gives the app its own window.
It is a local HTTP server on `127.0.0.1:8765` (if busy — the next free port up to 8799)
plus a web interface embedded in the same file (the `HTML` string). Compression is done by an external FFmpeg.

```
app window (WebView2)  or  browser   ──HTTP/JSON──►  server (ThreadingHTTPServer)
       HTML/JS from app.py                                │
              ┌───────────────────────────────────────────┼─────────────────────────────┐
              ▼                                           ▼                             ▼
        worker (queue)                              drive scanner                    persistence
     ffmpeg / ffprobe / VMAF           Everything IPC  or  folder walk   queue.json, history.json,
                                                                        settings.json, probe_cache.json
```

## Main parts of `app.py` (in file order)

| Part | What it does |
|---|---|
| Data folder (`_data_dir`) | source: next to `app.py`; portable (`portable.txt` next to the exe): `data\`; installed: `%APPDATA%\Framewring` |
| FFmpeg lookup (`find_tool`) | `ffmpeg/bin/`, `ffmpeg/`, the folder itself — next to the exe / `app.py`, then inside the bundle; then `PATH` |
| Child processes (`spawn`) | no window, below-normal priority, Windows Job Object — ffmpeg dies together with the app |
| Memory (`avail_mem`, `svt_lp_for`, `pagefile_off`) | SVT-AV1 parallelism, detection of a disabled page file |
| Modes (`PRESETS`, `HW_VENDOR`, `QUALITY`, `SPEED`, `RECOMMEND`, `video_args`) | encoders and their flags; GPU mode → vendor; recommendation order (see *Encoding modes* below) |
| GPU vendors (`gpu_vendors`) | which GPUs are installed: reads `DriverDesc` of the display adapters from the registry (`HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-…}`) instead of WMI, which can be very slow |
| Capabilities (`detect_caps`) | which encoders the FFmpeg build has; hardware ones are verified in parallel with a 0.5 s trial encode using the real flags; per mode `ok`, `why` and `show` |
| `probe` / `probe_cached` | file parameters via ffprobe; cache keyed by (size, mtime), saved in `probe_cache.json` |
| Jobs (`JOBS`, `add_path`, `out_dir_for`, `out_path_for`) | the file list; output naming that never overwrites an original or a foreign file |
| Scanner (`scan_thread`, `everything_search`, `_scan_walk`, `estimate`) | finding big videos, estimating savings |
| Encoding (`run_ffmpeg`, `encode`, `do_full`, `do_test`) | running ffmpeg, parsing `-progress`, retries, test + VMAF |
| Finishing (`_finish_watch`, `finalize`) | progress of the `+faststart` stage; robust rename of `.part` |
| Data files (`write_json`, `read_json`, `_backup`, `BACKUP_DIR`) | atomic writes with up to 3 backup copies, one write at a time (`_WRITE_LOCK`); reading falls back to the newest good backup |
| Queue and history (`queue_saver`, `load_queue`, `_restore_job`, `load_history`, `add_history`) | survive restarts; a damaged queue or history entry is skipped instead of preventing start; `load_queue` removes a leftover `.part.mp4` of an interrupted job |
| Replace originals (`REPLACE`, `src_sig`, `file_sha256`, `_hkey`, `_real_path`, `has_recycle_bin`, `bin_check`, `recycle`, `in_recycle_bin`, `stream_counts`, `verify_output`, `_check_entry`, `replace_candidates`, `_replace_one`, `replace_recover`, `replace_run`) | puts verified compressed files in place of the originals the user ticked; originals go to the Recycle Bin; an interrupted replacement is finished or rolled back on start (see *Replacing originals* below) |
| `worker` | one thread, takes `queued` jobs in order |
| HTTP (`H`, `snapshot`) | API, Host and token checks, security headers |
| `HTML` | the interface (7 languages, strings from `i18n.py` + `locales/`): settings, queue, search, history (with export/import), *Replace originals* window (`openReplace`, `renderReplace`), first-run *How it works* hint (`renderIntro`, hidden via `localStorage` `fw_intro`), donate window, bug-report window, update bar |
| Updates (`UPDATE`, `install_kind`, `check_update`, `install_update`) | once per launch asks GitHub for the latest release; one-click update of the installed version (see *Updates* below) |
| Bug report (`report_url`) | URL of the GitHub issue form with version, Windows, GPU names, FFmpeg version and mode pre-filled |
| `run_window`, `_setup_log`, `_hold_mutex`, `main` | single instance per machine (the named mutex `FramewringRunning` is taken before anything else, so a second copy exits even if the first hasn't opened its server yet), data loading, threads, own window or browser, log file for the exe |

## Job lifecycle

`probing` → `ready` → `queued` → `running` → `done` | `skipped` | `kept` | `tested` | `error` | `cancelled`

`kept` — the result would not be smaller: compression is stopped early by `_gain_watch`, or a finished result that is not at least 3% smaller (`NO_GAIN = 0.97`) is deleted.
`_gain_watch` checks every 2 s and compares the output size with the bytes of the original that ffmpeg has already **read**
(`proc_io` → `GetProcessIoCounters`), i.e. the same part of the video — not with the elapsed percentage, which misled on
videos with a complex beginning and a static rest. It stops ffmpeg when output ≥ 110% of what was read after ≥ 10% of the
file is read, or ≥ 102% after ≥ 30%; without read counters (outside Windows) only when the output already reaches 97% of the
original. The job note says where it stopped and the projected size.
A replaced job gets `replaced: true` and `out_path` pointing to the new file in the original's folder.

Full compression (`do_full`):
1. output name (`out_path_for`); skip if the result already exists and "Skip already compressed files" is on;
2. free-space check based on `estimate`;
3. the original's signature `src_sig` = `[size, int(mtime)]` is stored in the job;
   `ffmpeg … -fps_mode passthrough -movflags +faststart` into `name.part.mp4` (its path is kept in the job and in `CUR`,
   so it is removed on exit mid-compression and on the next start after a crash — only files ending in `.part.mp4`)
   (filters: deinterlace, even dimensions; subtitles; audio copied when the container allows);
4. on a memory error — up to 3 attempts (for SVT-AV1 with a lower `lp`);
5. `finalize`: rename with waiting, original's date; then `out_sig` and the SHA-256 of the compressed file (`file_sha256`,
   phase *Computing the checksum*) and the history entry (with `src_sig`, `out_sig`, `out_hash`, `src_codec` and the test's
   `vmaf` — only if the Test was made with the same mode and quality as this compression, otherwise `null`).

Output naming never replaces an original or a foreign file: in the default `compressed` subfolder the original name is kept
(`name_mkv.mp4` / `name_mov.mp4` if two sources share a name); if the output folder is the source folder
(detected with `os.path.samefile`, so junctions and different spellings are caught) a `_compressed` suffix is added;
in a shared output folder a file not known from the history is treated as someone else's and a number is added.
Name comparisons are case-insensitive.

Test (`do_test`): a piece is cut without re-encoding (`_tests/…_original_cut.mkv`, starting at 40% of the duration),
compressed with the same settings, and VMAF is computed (frames matched by number; above 1080p — at 1080p).

## Encoding modes

| Preset | Mode in the UI | FFmpeg encoder | Rate control (Maximum / Balanced / Compact) |
|---|---|---|---|
| `nvenc_av1` | Nvidia GPU · AV1 | `av1_nvenc` | VBR with CQ 27 / 30 / 33 |
| `nvenc_hevc` | Nvidia GPU · H.265 | `hevc_nvenc` | VBR with CQ 22 / 24 / 27 |
| `amf_av1` | AMD GPU · AV1 | `av1_amf` | constant QP on the 0–255 scale, 88 / 100 / 116 |
| `amf_hevc` | AMD GPU · H.265 | `hevc_amf` | constant QP 22 / 24 / 27 |
| `qsv_av1` | Intel GPU · AV1 | `av1_qsv` | ICQ 24 / 27 / 30 |
| `qsv_hevc` | Intel GPU · H.265 | `hevc_qsv` | ICQ 22 / 24 / 27 |
| `vt_hevc` | Mac GPU · H.265 | `hevc_videotoolbox` | `-q:v` 70 / 62 / 55 |
| `x265` | CPU · H.265 | `libx265` | CRF 20 / 22 / 24 |
| `av1` | CPU · AV1 | `libsvtav1` | CRF 27 / 30 / 33; SVT-AV1 preset 4 / 6 / 8 for Thorough / Normal / Faster |

- All modes output 10-bit. For AMF this matters: 8-bit output was broken in a measurement (VMAF ~56 vs ~99 for 10-bit).
  AMF QP 22/24/27 was calibrated against NVENC CQ 22/24/27 (same size and VMAF on the same clip).
- Decoding: Nvidia modes use CUDA decoding (`-hwaccel cuda`); AMD, Intel and CPU modes decode on the CPU.
- `RECOMMEND`: `nvenc_av1` → `nvenc_hevc` → `amf_hevc` → `qsv_hevc` → `amf_av1` → `qsv_av1` → `vt_hevc` → `x265` → `av1`;
  the first mode with `ok` becomes `CAPS["recommended"]`. `amf_av1` and `qsv_av1` stay below the H.265 modes until they are
  verified on real hardware.
- `detect_caps` sets per mode: `ok` — the trial encode passed; `why` — the reason if not; `show` — whether the UI lists the mode:
  CPU modes always, a GPU mode if it works or if a GPU of its vendor (`HW_VENDOR`) is found by `gpu_vendors()`.
  So a failing mode is greyed out with the reason only on a PC that has that vendor's GPU; other vendors' modes are hidden.
- `amf_av1` (Radeon RX 7000+, Ryzen 7040/8040-series graphics — Radeon 780M/880M) and the `qsv_*` modes have not been verified on real hardware yet; `amf_hevc` was checked on
  Ryzen 7 9700X integrated graphics.

## Finding heavy videos

1. For local NTFS drives (if enabled) — a query to Everything via `WM_COPYDATA`
   (`EVERYTHING_IPC_COPYDATA_QUERY2W`). If Everything is installed but closed,
   it is started in the tray for the search (`-startup`) and closed afterwards (`-exit`).
2. Otherwise (no Everything, network/removable drive, not NTFS) — a multi-threaded walk:
   8 threads on SSD, 3 on HDD (`is_ssd` via `IOCTL_STORAGE_QUERY_PROPERTY`).
3. Filters: `SKIP_DIRS`, folders starting with `$` and `.`, OneDrive cloud files, `.part.mp4`.
4. Candidates go straight to ffprobe (6 threads); results appear as they come.

## HTTP API

- Every request checks `Host` (`127.0.0.1` / `localhost`) — protection against DNS rebinding.
- A random token is generated at startup. The page is served only at `/?t=<token>` (the app opens this URL itself);
  all other `GET` and `POST` requests require the `X-Token` header. Exceptions: `GET /api/ping` and `POST /api/show`,
  used by a second launch to find and raise the running instance; they reveal nothing and refuse requests that carry
  `Origin`, `Sec-Fetch-Site` or `Referer` (i.e. requests made from a web page).
- Responses carry `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

| Method and path | Purpose |
|---|---|
| `GET /?t=TOKEN` | the interface |
| `GET /api/status?sv=N` | state snapshot; search results are sent only if version `sv` changed; `update` (`latest`, `state`, `pct`, `err`), `install_kind` (`installer` / `portable` / `source`) and `replace` (`running`, `ver`, `items`: history entry key → `state` `queued` / `verify` / `replace` / `done` / `warn` / `error`, `pct`, `err`) |
| `GET /api/ping`, `POST /api/show` | second launch: "is Framewring here?" / raise the window |
| `POST /api/pick` `{kind}` | system file/folder dialog |
| `POST /api/add` `{paths}` | add files or folders |
| `POST /api/settings` `{…}` | change settings (values are validated) |
| `POST /api/start` `{mode: test/full}` | queue everything eligible |
| `POST /api/retry` `{id}` | queue one job |
| `POST /api/cancel` | stop the current job and clear the queue |
| `POST /api/remove` `{id}`, `/api/clear` | remove a job / all finished ones |
| `POST /api/open` `{id, which}` or `{hist, which}` | show a file in Explorer (`which`: compressed by default, `src`, `test`) |
| `POST /api/url` `{url}` | open one of the allowed pages (repository, support page, voidtools.com) |
| `POST /api/report` | open the bug-report issue form in the browser, pre-filled by `report_url` |
| `POST /api/open_log` | show `framewring.log` in Explorer (error if there is no log — source runs have none) |
| `POST /api/update_page` | open the release page of the new version |
| `POST /api/update_install` | download + verify + silent install of the new version (installed version only) |
| `POST /api/history` | compression history |
| `POST /api/hist_export` | write the history to `Documents\Framewring-history-YYYY-MM-DD_HH-MM-SS.json` (`_documents_dir`: the real Documents known folder via `SHGetKnownFolderPath`, incl. one moved to OneDrive; `~\Documents` or the home folder as a fallback; the timestamp means an earlier export is never overwritten) and show it in Explorer; returns `{path}` |
| `POST /api/hist_import` `{path?}` | merge a history file (file dialog if no `path`); entries need `src` and `out`; each imported entry loses `replace_tmp`, `replace_copy`, `src_sig`, `out_sig`, `out_hash`, `verify_failed` and gets `imported: true` (it can't be used to replace — `rep.b.imported`); duplicates (same `src`, `out`, `t`) are skipped; refused while a replacement runs; returns `{added}` |
| `POST /api/replace_list` | candidates for replacing: one per original, from the history; each with `key` (time + source path), `name`, `src`, `out`, `size`, `out_size`, `warn[]`, `block[]`, `state` |
| `POST /api/replace` `{keys}` | replace the originals of these history entries (one at a time, in the background); unknown keys are refused (`rep.err.blocked`); progress in `/api/status` → `replace` |
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | drive list, search |
| `POST /api/quit` | quit (browser mode only, where there is no window to close) |

## Data files (in the data folder, never in git)

| File | Contents | Personal data |
|---|---|---|
| `settings.json` | chosen mode, quality, output folder, options (incl. `update_check`) | no |
| `queue.json` | job list | **video paths** |
| `history.json` | compression history; per entry `t`, `src`, `out`, `name`, `size`, `out_size`, `duration`, `preset`, `quality`, `speed`, `secs`, and since 0.9.3 `src_sig` (`[size, mtime]` of the original at compression), `out_sig` (the same for the compressed file), `out_hash` (SHA-256 of the compressed file), `src_codec`, `vmaf` (from the Test, if it used the same mode and quality), `replaced`, `replaced_t`, `verify_failed`, `imported` (entry came from **Import…**); while a replacement is in progress also `replace_tmp`, `replace_copy` | **video paths** |
| `probe_cache.json` | video parameters | **video paths** |
| `framewring.log` | exe log (written only when there is no console) | **video paths** |
| `webview\` | window engine cache (WebView2) | no |

Data folder: from source — next to `app.py`; portable — `data\` next to the exe; installed — `%APPDATA%\Framewring`.
Writes are atomic: to a temporary file, then `os.replace`. `write_json` holds `_WRITE_LOCK`, so writes are serialized: the
history can be updated at the same time by compression and by a replacement without one update overwriting the other.
History changes (`add_history`, `_set_hist`, import) build the JSON text under `LOCK` from the current list.

**Loading.** `read_json` falls back to a backup if the file is missing or damaged. `load_history` keeps only entries that
are objects with string `src` and `out`; `load_queue` restores each entry separately (`_restore_job`) and skips one that
fails, so a single damaged entry never prevents start.

**Backups** (`write_json` → `_backup`): `settings.json`, `history.json` and `queue.json` are also copied to `BACKUP_DIR` as
`<name>.1.json` (newest) … `<name>.3.json`; an unchanged text is not copied again, the queue (saved every 2 s) at most once
every 5 minutes. `BACKUP_DIR` is `backup\` in the data folder, but for the installed exe it is `%LOCALAPPDATA%\Framewring\backup`,
so even a deleted `%APPDATA%\Framewring` is restored. `read_json` takes the file itself, or else the newest backup that parses
and has the expected type.

## Replacing originals

Only for history entries the user ticked in the dialog. Nothing is pre-selected; **⇄ Replace original** on a job
(`openReplace(src, out)`) highlights that file's row and pre-ticks it only if it has neither blocks nor warnings. `doReplace`
always asks for confirmation first, listing the ticked files (`rep.confirm`) and those with warnings (`rep.confirm_warn`). Each row shows the
original's folder and the compressed file's path (`→ out`).

Entries are identified by a stable key `_hkey(h)` = `"t|normalised src"` (not by the index in the list, which shifts e.g.
after an import); `_hist_find(key)` looks it up, `_set_hist(key, …)` updates the entry and saves `history.json`.
`/api/hist_import` is refused (`rep.err.busy`) while a replacement runs.

`replace_candidates()` goes through the history from newest to oldest, one line per original, and runs `_check_entry(h)`
(a fresh check of the files on disk), which fills:

- `block` (can't be ticked): `rep.b.replaced`, `src_missing`, `out_missing`; `imported` (the entry came from
  `/api/hist_import` — it can't be verified; compressing again makes it replaceable); `old_entry` (no `src_sig`, `out_sig`
  or `out_hash` — an entry from an older version can't be verified; compressing again with ↻ Retry makes it replaceable);
  `src_changed` (`src_sig` differs from the one stored at compression); `out_changed` (`out_sig` = `[size, mtime]` of the
  compressed file stored in the history differs — the file was changed or swapped); `not_smaller` (`out_size >= size`);
  `long_path` (the real path of the original, `name.framewring-new.mp4` or `name.mp4` is ≥ 250 characters: Windows deletes
  such a file permanently instead of recycling it — verified); `busy` (a job with this path is `queued` / `probing` /
  `running`); `bin_check(src, size)` → `no_bin` / `bin_off` / `bin_small`; `collision` (the target `name.mp4` exists and is
  not the original); `leftover` (`name.framewring-new.mp4` from an unfinished replacement exists); `check_failed` (the
  check itself raised an error — one bad entry doesn't break the dialog);
- `warn`: `rep.w.no_test` (no VMAF — no Test, or the Test used a different mode or quality than the compression), `vmaf` (< 93), `edit` (source codec in `EDIT_CODECS`: ProRes, DNxHD, CineForm, FFV1, …),
  `lost_video` / `lost_subs` / `lost_data` / `lost_att` (`stream_counts` via `ffprobe`: the original has more extra video
  tracks (cover art not counted), subtitle, data (GoPro telemetry, timecode) or attachment streams than the compressed file),
  `small` (saving < 20%, only when there are no blocks).

`bin_check(path, size)` returns `None` only if every check says a file of this size will go to the Recycle Bin (the final
word is still Windows', hence `FOF_WANTNUKEWARNING` and `in_recycle_bin` below), otherwise the reason:

- `has_recycle_bin` works on the real path `_real_path` (a `subst` drive → its folder via `QueryDosDeviceW`, a mapped network
  drive → `\\server\…`, junctions/symlinks via `realpath`): only `GetDriveTypeW == DRIVE_FIXED` passes, UNC paths never do;
- the volume GUID (`GetVolumeNameForVolumeMountPointW`) selects `HKCU\…\Explorer\BitBucket\Volume\{GUID}`: `NukeOnDelete`
  → `bin_off`; `MaxCapacity` (MB) is the bin size; the `Policies\Explorer` values `NoRecycleFiles` and `RecycleBinSize` (%)
  in HKLM/HKCU override them; with no setting found, 5% of the drive is assumed;
- used space from `SHQueryRecycleBinW`; if `size` > capacity − used → `bin_small` (Windows would delete permanently).

`replace_run(keys)` refuses to start twice, then in a background thread runs `_replace_one` for each key; an error in one
file is recorded in its item and the next one goes on. `_replace_one`:

1. `_check_entry` — no blocks; then `file_sha256(out)` must equal `out_hash` stored at compression — any changed byte
   fails it (`verify.hash`, the entry gets `verify_failed`);
2. `verify_output`: `ffprobe` of the compressed file — duration within max(1 s, min(3 s, 0.1% of the length)) of the
   original, same number of audio tracks; then the video track is decoded completely (`ffmpeg -v error -i out -map 0:V:0
   -f null -`, progress from `-progress`) and must reach the original's duration minus the tolerance (`verify.short` —
   catches a truncated video even if the audio is full length); then the audio of the compressed file is decoded separately
   (`-map 0:a`), and the original's audio is decoded too: the compressed audio must not be shorter than the original's minus
   the tolerance (`verify.audio_short`). Any stderr output or a non-zero exit code fails it (the entry gets `verify_failed`);
3. `_check_entry` again right before moving (the check may have taken long);
4. the intent is recorded in the history: `replace_tmp` (the temporary path) and `replace_copy` (cross-volume);
5. the compressed file goes to `name.framewring-new.mp4` in the original's folder: on the same volume `os.rename` (never
   overwrites — fails if the name is taken); otherwise `copy2` and a byte-by-byte comparison (`filecmp.cmp(shallow=False)`);
   the size must equal `out_sig[0]`. On failure it is moved back / the copy is removed and the intent cleared;
6. `bin_check` once more with the current size, then `recycle(src)` — `SHFileOperationW` on the **real path** with
   `FO_DELETE | FOF_ALLOWUNDO | FOF_WANTNUKEWARNING` (silent, no error UI; if Windows still decided to delete permanently it
   would ask instead of doing it silently); success only if the call returns 0, nothing was aborted and the file is gone.
   On failure the temporary file is moved back (or the copy removed) — nothing has changed (`rep.err.rollback` if that fails);
7. `in_recycle_bin(src, t0)` reads the `$I` records in `$Recycle.Bin` of that drive (original path and deletion time from
   inside the record, formats v1 and v2), polling up to ~4.5 s;
8. `os.rename(tmp, name.mp4)` (never overwrites); if this fails, the item ends as `warn` with `rep.err.final` naming the
   temporary file (the original is already in the Recycle Bin);
9. a cross-volume source copy is removed; the compressed file's folder is removed only if it is named `compressed` and is
   empty (a custom output folder never); the history entry gets `replaced`, `replaced_t`, new `out`, `out_size`, `out_sig`,
   and the intent is cleared; the job gets `replaced` and `out_path`. If step 7 didn't find the original in the bin, the item
   ends as `warn` with `rep.err.not_in_bin`.

Item states: `done`; `warn` (`_ItemError(after=True)`: the original is in the Recycle Bin, but it was not found there or the
new file kept its temporary name — shown as *⚠ …*); `error` (the original was not replaced).

The Recycle Bin is never assumed: `bin_check` and `long_path` are checked beforehand (bin present, turned on, enough free
space, path not too long); if Windows would still delete permanently, `FOF_WANTNUKEWARNING` makes it ask first; afterwards
`in_recycle_bin` confirms the original is there and the item warns if not.

`replace_recover()` runs on start (after `load_history`) for every entry with `replace_tmp`: if the temporary file exists and
the original is still in place, it is rolled back (copy removed or moved back to `out`); if the original is already gone (in
the Recycle Bin), the temporary file becomes `name.mp4` and the entry is marked `replaced`. If there is no temporary file,
the entry is marked `replaced` when the original is gone and `name.mp4` has the size from `out_sig`, or the intent is
simply cleared when the original is still there.

Tested: mp4 → mp4 in place; mkv → mp4 next to it; name collision refused; a corrupted compressed file caught by the decode;
a changed original refused; a failed Recycle Bin step fully rolled back; plus the 12 scenarios of the independent review
(see DEVLOG, 2026-11-12).

## Platform specifics

- **Windows:** Job Object, `SetThreadExecutionState` (prevent sleep), `SO_EXCLUSIVEADDRUSE`, Everything IPC, SSD detection,
  page-file warning, own window via pywebview (WebView2) with file dialogs and drag & drop; tkinter dialogs in browser mode.
- **macOS:** `caffeinate`, VideoToolbox H.265, file dialogs via `osascript`. Barely tested.
- **Linux:** `prctl(PR_SET_PDEATHSIG)`, `/proc/meminfo`, `zenity`. Barely tested.

## Updates

- `check_update` runs once per launch (4 s after start) unless the setting `update_check` is off. It makes one request to
  `api.github.com` for the latest release of `remrem23/framewring`; drafts, pre-releases and versions not newer than the
  running one are ignored. Only the `-setup.exe` and `SHA256SUMS.txt` assets of that release on
  `github.com/remrem23/framewring/releases/download/` are accepted. Nothing about the user's files is sent.
- The result is kept in `UPDATE` and reported in `/api/status` as `update` (`latest`, `state`: `""` / `download` / `install` /
  `error`, `pct`, `err`) together with `install_kind`. The interface shows the bar *"Framewring X is available."* with
  *Update* / *What's new* / *Later* (*Later* hides that version in `localStorage`); for `portable` and `source` the first
  button is *Download* (`/api/update_page`).
- `install_update` (only for `install_kind() == "installer"`): downloads `SHA256SUMS.txt` and the setup into
  `%TEMP%\FramewringUpdate`, compares the SHA-256, releases the single-instance mutex, starts the setup detached with
  `/SILENT /SP- /NOCANCEL /NORESTART /FWUPDATE=1` and quits. Settings, queue and history stay in `%APPDATA%\Framewring`.
  Checked end-to-end in a test before the first release: updating 0.8.0 → 0.9.0 took about 20 s.
- The installer (`packaging/framewring.iss`) has `[Code] IsSelfUpdate`, true when `/FWUPDATE=1` is passed; the `[Run]` entry
  that starts `Framewring.exe` after a silent install is guarded by it, so the app is relaunched only after a self-update,
  not after a silent install run by an administrator.

## Build

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, license texts);
`packaging/release.py` — Inno Setup installer (`packaging/framewring.iss`), portable zip, `SHA256SUMS.txt`.

Releases are built by GitHub Actions (`.github/workflows/build.yml`) on a clean `windows-2025` machine: Python 3.12.10,
exact package versions from `packaging/requirements-build.txt`, FFmpeg from `packaging/ffmpeg.json` (Gyan build, checked by
SHA-256 in `packaging/get_ffmpeg.py`), then `build.py`, a start check (`/api/ping`), `release.py` and a build provenance
attestation for the setup and the zip. Run manually, it uploads the files as a workflow artifact; a `vX.Y.Z` tag (must match
`__version__`) also creates a draft release, which is published by hand. A published release is never overwritten.

---

<a id="русский"></a>
## Русский

**Архитектура Framewring Жмых**

Программа — это `app.py` (~3400 строк) плюс строки интерфейса в `i18n.py` и `locales/`. Используется только стандартная библиотека Python;
[pywebview](https://pywebview.flowrl.com/) — по желанию, даёт программе своё окно.
Это локальный HTTP-сервер на `127.0.0.1:8765` (при занятости — следующий свободный порт до 8799)
плюс веб-интерфейс, встроенный в тот же файл (строка `HTML`). Сжатие делает внешний FFmpeg.

```
окно программы (WebView2)  или  браузер   ──HTTP/JSON──►  сервер (ThreadingHTTPServer)
       HTML/JS из app.py                                     │
              ┌──────────────────────────────────────────────┼─────────────────────────────┐
              ▼                                              ▼                             ▼
        worker (очередь)                               сканер дисков                 сохранение
     ffmpeg / ffprobe / VMAF             Everything IPC  или  обход папок   queue.json, history.json,
                                                                           settings.json, probe_cache.json
```

### Основные части `app.py` (по порядку в файле)

| Часть | Что делает |
|---|---|
| Папка данных (`_data_dir`) | из исходников: рядом с `app.py`; портабл (`portable.txt` рядом с exe): `data\`; установленная: `%APPDATA%\Framewring` |
| Поиск FFmpeg (`find_tool`) | `ffmpeg/bin/`, `ffmpeg/`, сама папка — рядом с exe / `app.py`, затем внутри сборки; затем `PATH` |
| Дочерние процессы (`spawn`) | без окна, пониженный приоритет, Windows Job Object — ffmpeg завершается вместе с программой |
| Память (`avail_mem`, `svt_lp_for`, `pagefile_off`) | подбор параллельности SVT-AV1, обнаружение выключенного файла подкачки |
| Режимы (`PRESETS`, `HW_VENDOR`, `QUALITY`, `SPEED`, `RECOMMEND`, `video_args`) | таблица кодеров и их флагов; режим видеокарты → производитель; порядок рекомендации (см. «Режимы сжатия» ниже) |
| Производители видеокарт (`gpu_vendors`) | какие видеокарты стоят: читает `DriverDesc` видеоадаптеров из реестра (`HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-…}`) вместо WMI, который бывает очень медленным |
| Возможности (`detect_caps`) | какие кодеры есть в сборке FFmpeg; аппаратные проверяются параллельно пробным кодированием 0,5 с с настоящими флагами; для каждого режима `ok`, `why` и `show` |
| `probe` / `probe_cached` | параметры файла через ffprobe; кэш по (размер, mtime), сохраняется в `probe_cache.json` |
| Задачи (`JOBS`, `add_path`, `out_dir_for`, `out_path_for`) | список файлов; имя результата, которое никогда не затирает оригинал или чужой файл |
| Сканер (`scan_thread`, `everything_search`, `_scan_walk`, `estimate`) | поиск больших видео, оценка экономии |
| Кодирование (`run_ffmpeg`, `encode`, `do_full`, `do_test`) | запуск ffmpeg, разбор `-progress`, повторы, тест + VMAF |
| Завершение (`_finish_watch`, `finalize`) | прогресс этапа `+faststart`; надёжное переименование `.part` |
| Файлы данных (`write_json`, `read_json`, `_backup`, `BACKUP_DIR`) | атомарная запись с резервными копиями (до 3), по одной записи за раз (`_WRITE_LOCK`); при чтении испорченного файла — последняя целая копия |
| Очередь и история (`queue_saver`, `load_queue`, `_restore_job`, `load_history`, `add_history`) | переживают перезапуск; испорченная запись очереди или истории пропускается и не мешает запуску; `load_queue` удаляет оставшийся `.part.mp4` прерванной задачи |
| Замена оригиналов (`REPLACE`, `src_sig`, `file_sha256`, `_hkey`, `_real_path`, `has_recycle_bin`, `bin_check`, `recycle`, `in_recycle_bin`, `stream_counts`, `verify_output`, `_check_entry`, `replace_candidates`, `_replace_one`, `replace_recover`, `replace_run`) | ставит проверенные сжатые файлы на место отмеченных пользователем оригиналов; оригиналы — в корзину; прерванная замена доделывается или откатывается при запуске (см. «Замена оригиналов» ниже) |
| `worker` | один поток, берёт задачи `queued` по порядку |
| HTTP (`H`, `snapshot`) | API, проверка Host и токена, заголовки безопасности |
| `HTML` | интерфейс (7 языков, строки из `i18n.py` + `locales/`): настройки, очередь, поиск, история (с экспортом и импортом), окно «Заменить оригиналы» (`openReplace`, `renderReplace`), подсказка «Как это работает» при первом запуске (`renderIntro`, скрывается через `localStorage` `fw_intro`), окно доната, окно «Сообщить об ошибке», полоса обновления |
| Обновления (`UPDATE`, `install_kind`, `check_update`, `install_update`) | раз за запуск спрашивает у GitHub последний релиз; обновление установленной версии в один клик (см. «Обновления» ниже) |
| Сообщение об ошибке (`report_url`) | адрес формы issue на GitHub с заполненными версией, Windows, видеокартами, версией FFmpeg и режимом |
| `run_window`, `_setup_log`, `_hold_mutex`, `main` | один экземпляр на машину (именованный мьютекс `FramewringRunning` берётся раньше всего остального, поэтому вторая копия выходит, даже если первая ещё не открыла сервер), загрузка данных, потоки, своё окно или браузер, журнал для exe |

### Жизненный цикл задачи

`probing` → `ready` → `queued` → `running` → `done` | `skipped` | `kept` | `tested` | `error` | `cancelled`

`kept` — результат не вышел бы меньше: сжатие останавливает раньше `_gain_watch` или готовый результат, который не меньше хотя бы на 3% (`NO_GAIN = 0.97`), удаляется.
`_gain_watch` раз в 2 с сравнивает размер результата с объёмом оригинала, который ffmpeg уже **прочитал**
(`proc_io` → `GetProcessIoCounters`), то есть с тем же участком видео, — а не с прошедшим процентом, который обманывал на
видео со сложным началом и статичным продолжением. ffmpeg останавливается, когда результат ≥ 110% прочитанного при
прочитанных ≥ 10% файла или ≥ 102% при ≥ 30%; без счётчиков чтения (не в Windows) — только когда результат уже достиг 97%
оригинала. В заметке задачи — где остановлено и прогноз размера.
У заменённой задачи `replaced: true`, а `out_path` указывает на новый файл в папке оригинала.

Полное сжатие (`do_full`):
1. имя результата (`out_path_for`); пропуск, если он уже есть и включено «Пропускать уже сжатые файлы»;
2. проверка свободного места по оценке `estimate`;
3. в задаче запоминается подпись оригинала `src_sig` = `[размер, int(mtime)]`;
   `ffmpeg … -fps_mode passthrough -movflags +faststart` в `имя.part.mp4` (путь хранится в задаче и в `CUR`, поэтому файл
   удаляется при выходе посреди сжатия и при следующем запуске после сбоя — только файлы на `.part.mp4`)
   (фильтры: деинтерлейс, чётные размеры; субтитры; копирование звука, если формат допускает);
4. при ошибке памяти — до 3 попыток (для SVT-AV1 — со сниженным `lp`);
5. `finalize`: переименование с ожиданием, дата оригинала; затем `out_sig` и SHA-256 сжатого файла (`file_sha256`,
   этап «Считаю контрольную сумму») и запись в историю (с `src_sig`, `out_sig`, `out_hash`, `src_codec` и `vmaf` теста —
   только если тест сделан с теми же режимом и качеством, что и это сжатие, иначе `null`).

Имя результата никогда не затирает оригинал или чужой файл: в подпапке `compressed` по умолчанию сохраняется имя оригинала
(`имя_mkv.mp4` / `имя_mov.mp4`, если у двух исходников одно имя); если папка вывода — папка оригинала
(определяется через `os.path.samefile`, так что junction-ссылки и другое написание пути тоже ловятся), добавляется суффикс `_compressed`;
в общей папке вывода файл, которого нет в истории, считается чужим, и к имени добавляется номер.
Имена сравниваются без учёта регистра.

Тест (`do_test`): вырезается кусок без пережатия (`_tests/…_original_cut.mkv`, начиная с 40% длительности),
сжимается теми же настройками, считается VMAF (кадры сопоставляются по номеру, выше 1080p — в 1080p).

### Режимы сжатия

| Пресет | Режим в интерфейсе | Кодер FFmpeg | Управление качеством (Максимальное / Баланс / Компактное) |
|---|---|---|---|
| `nvenc_av1` | Видеокарта Nvidia · AV1 | `av1_nvenc` | VBR с CQ 27 / 30 / 33 |
| `nvenc_hevc` | Видеокарта Nvidia · H.265 | `hevc_nvenc` | VBR с CQ 22 / 24 / 27 |
| `amf_av1` | Видеокарта AMD · AV1 | `av1_amf` | постоянный QP по шкале 0–255, 88 / 100 / 116 |
| `amf_hevc` | Видеокарта AMD · H.265 | `hevc_amf` | постоянный QP 22 / 24 / 27 |
| `qsv_av1` | Видеокарта Intel · AV1 | `av1_qsv` | ICQ 24 / 27 / 30 |
| `qsv_hevc` | Видеокарта Intel · H.265 | `hevc_qsv` | ICQ 22 / 24 / 27 |
| `vt_hevc` | Видеокарта Mac · H.265 | `hevc_videotoolbox` | `-q:v` 70 / 62 / 55 |
| `x265` | Процессор · H.265 | `libx265` | CRF 20 / 22 / 24 |
| `av1` | Процессор · AV1 | `libsvtav1` | CRF 27 / 30 / 33; пресет SVT-AV1 4 / 6 / 8 для «Тщательно» / «Обычно» / «Быстрее» |

- Все режимы выдают 10 бит. Для AMF это важно: 8-битный вывод в замере был сломан (VMAF ~56 против ~99 у 10 бит).
  QP 22/24/27 у AMF откалиброван по NVENC CQ 22/24/27 (тот же размер и VMAF на том же ролике).
- Декодирование: режимы Nvidia декодируют через CUDA (`-hwaccel cuda`); режимы AMD, Intel и процессора — на процессоре.
- `RECOMMEND`: `nvenc_av1` → `nvenc_hevc` → `amf_hevc` → `qsv_hevc` → `amf_av1` → `qsv_av1` → `vt_hevc` → `x265` → `av1`;
  первый режим с `ok` становится `CAPS["recommended"]`. `amf_av1` и `qsv_av1` стоят ниже режимов H.265, пока не проверены
  на реальном железе.
- `detect_caps` задаёт для каждого режима: `ok` — пробное кодирование прошло; `why` — причина, если нет; `show` — показывать ли
  режим в интерфейсе: процессор — всегда, видеокарту — если работает или если `gpu_vendors()` нашёл видеокарту её производителя
  (`HW_VENDOR`). Поэтому неработающий режим показывается серым с причиной только там, где такая видеокарта есть; режимы
  других производителей скрыты.
- `amf_av1` (Radeon RX 7000+, графика Ryzen серий 7040/8040 — Radeon 780M/880M) и режимы `qsv_*` на реальном железе ещё не проверялись; `amf_hevc` проверен на встроенной
  графике Ryzen 7 9700X.

### Поиск тяжёлых видео

1. Для локальных NTFS-дисков (и если включено) — запрос к Everything через `WM_COPYDATA`
   (`EVERYTHING_IPC_COPYDATA_QUERY2W`). Если программа Everything установлена, но закрыта,
   она запускается в трей на время поиска (`-startup`) и закрывается (`-exit`).
2. Иначе (нет Everything, сетевой/съёмный диск, не NTFS) — многопоточный обход:
   8 потоков на SSD, 3 на HDD (`is_ssd` через `IOCTL_STORAGE_QUERY_PROPERTY`).
3. Фильтры: `SKIP_DIRS`, папки на `$` и `.`, облачные файлы OneDrive, `.part.mp4`.
4. Кандидаты сразу уходят в ffprobe (6 потоков); результаты появляются по ходу.

### HTTP API

- Любой запрос проверяет `Host` (`127.0.0.1` / `localhost`) — защита от DNS rebinding.
- При запуске генерируется случайный токен. Страница отдаётся только по адресу `/?t=<токен>` (его открывает сама программа);
  все остальные `GET` и `POST` требуют заголовок `X-Token`. Исключения — `GET /api/ping` и `POST /api/show`:
  по ним второй запуск находит и поднимает работающий экземпляр; они ничего не раскрывают и отклоняют запросы
  с заголовками `Origin`, `Sec-Fetch-Site` или `Referer` (то есть пришедшие с веб-страницы).
- В ответах: `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

| Метод и путь | Назначение |
|---|---|
| `GET /?t=ТОКЕН` | интерфейс |
| `GET /api/status?sv=N` | снимок состояния; результаты поиска отдаются, только если изменилась версия `sv`; `update` (`latest`, `state`, `pct`, `err`), `install_kind` (`installer` / `portable` / `source`) и `replace` (`running`, `ver`, `items`: ключ записи истории → `state` `queued` / `verify` / `replace` / `done` / `warn` / `error`, `pct`, `err`) |
| `GET /api/ping`, `POST /api/show` | второй запуск: «здесь уже работает Framewring?» / показать окно |
| `POST /api/pick` `{kind}` | системное окно выбора файлов/папки |
| `POST /api/add` `{paths}` | добавить файлы или папки |
| `POST /api/settings` `{…}` | изменить настройки (значения проверяются) |
| `POST /api/start` `{mode: test/full}` | поставить в очередь всё подходящее |
| `POST /api/retry` `{id}` | поставить в очередь одну задачу |
| `POST /api/cancel` | остановить текущую задачу и очистить очередь |
| `POST /api/remove` `{id}`, `/api/clear` | убрать задачу / все готовые |
| `POST /api/open` `{id, which}` или `{hist, which}` | показать файл в проводнике (`which`: сжатый по умолчанию, `src`, `test`) |
| `POST /api/url` `{url}` | открыть одну из разрешённых страниц (репозиторий, страница поддержки, voidtools.com) |
| `POST /api/report` | открыть в браузере форму issue «сообщить об ошибке», заполненную `report_url` |
| `POST /api/open_log` | показать `framewring.log` в проводнике (ошибка, если журнала нет — при запуске из исходников его нет) |
| `POST /api/update_page` | открыть страницу релиза новой версии |
| `POST /api/update_install` | скачать, проверить и тихо установить новую версию (только установленная версия) |
| `POST /api/history` | журнал сжатия |
| `POST /api/hist_export` | записать историю в `Документы\Framewring-history-ГГГГ-ММ-ДД_ЧЧ-ММ-СС.json` (`_documents_dir`: настоящая известная папка «Документы» через `SHGetKnownFolderPath`, в т.ч. перенесённая в OneDrive; запасные варианты — `~\Documents` или домашняя папка; из-за времени в имени прежний экспорт никогда не перезаписывается) и показать в проводнике; возвращает `{path}` |
| `POST /api/hist_import` `{path?}` | добавить историю из файла (без `path` — окно выбора); у записей должны быть `src` и `out`; у каждой импортированной записи убираются `replace_tmp`, `replace_copy`, `src_sig`, `out_sig`, `out_hash`, `verify_failed` и ставится `imported: true` (по ней нельзя заменить — `rep.b.imported`); дубли (те же `src`, `out`, `t`) пропускаются; во время замены отклоняется; возвращает `{added}` |
| `POST /api/replace_list` | кандидаты на замену: по одному на оригинал, из истории; у каждого `key` (время + путь к оригиналу), `name`, `src`, `out`, `size`, `out_size`, `warn[]`, `block[]`, `state` |
| `POST /api/replace` `{keys}` | заменить оригиналы этих записей истории (по одному, в фоне); неизвестные ключи отклоняются (`rep.err.blocked`); ход — в `/api/status` → `replace` |
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | список дисков, поиск |
| `POST /api/quit` | выход (только в режиме браузера, где нет окна, которое можно закрыть) |

### Файлы данных (в папке данных, в git не попадают)

| Файл | Содержимое | Личные данные |
|---|---|---|
| `settings.json` | выбранный режим, качество, папка вывода, опции (в т.ч. `update_check`) | нет |
| `queue.json` | список задач | **пути к видео** |
| `history.json` | журнал сжатия; у записи `t`, `src`, `out`, `name`, `size`, `out_size`, `duration`, `preset`, `quality`, `speed`, `secs`, а с 0.9.3 — `src_sig` (`[размер, mtime]` оригинала при сжатии), `out_sig` (то же для сжатого файла), `out_hash` (SHA-256 сжатого файла), `src_codec`, `vmaf` (из «Теста», если он был с теми же режимом и качеством), `replaced`, `replaced_t`, `verify_failed`, `imported` (запись пришла из «Импорта…»); пока идёт замена — ещё `replace_tmp`, `replace_copy` | **пути к видео** |
| `probe_cache.json` | параметры видео | **пути к видео** |
| `framewring.log` | журнал exe-версии (пишется, только когда нет консоли) | **пути к видео** |
| `webview\` | кэш движка окна (WebView2) | нет |

Папка данных: из исходников — рядом с `app.py`; портабл — `data\` рядом с exe; установленная — `%APPDATA%\Framewring`.
Запись атомарная: во временный файл, затем `os.replace`. `write_json` держит `_WRITE_LOCK`, поэтому записи идут по одной:
история может обновляться одновременно из сжатия и из замены, и одно обновление не затирает другое. Изменения истории
(`add_history`, `_set_hist`, импорт) собирают JSON-текст под `LOCK` из текущего списка.

**Загрузка.** Если файла нет или он испорчен, `read_json` берёт резервную копию. `load_history` оставляет только записи-объекты
со строковыми `src` и `out`; `load_queue` восстанавливает каждую запись отдельно (`_restore_job`) и пропускает ту, что не
читается, поэтому одна испорченная запись никогда не мешает запуску.

**Резервные копии** (`write_json` → `_backup`): `settings.json`, `history.json` и `queue.json` дополнительно копируются в
`BACKUP_DIR` как `<имя>.1.json` (самая свежая) … `<имя>.3.json`; неизменившийся текст повторно не копируется, очередь
(сохраняется каждые 2 с) — не чаще раза в 5 минут. `BACKUP_DIR` — `backup\` в папке данных, а у установленной exe-версии —
`%LOCALAPPDATA%\Framewring\backup`, поэтому восстанавливается даже удалённая `%APPDATA%\Framewring`. `read_json` берёт сам файл,
а если он не читается — самую свежую копию, которая разбирается и имеет нужный тип.

### Замена оригиналов

Только для записей истории, которые пользователь отметил в окне. Заранее ничего не отмечено; «⇄ Заменить оригинал» у задачи
(`openReplace(src, out)`) подсвечивает строку этого файла и отмечает его, только если у него нет ни запретов, ни
предупреждений. `doReplace` всегда сначала спрашивает подтверждение со списком отмеченных файлов (`rep.confirm`) и файлов с предупреждениями (`rep.confirm_warn`).
В каждой строке — папка оригинала и путь к сжатому файлу (`→ out`).

Записи опознаются по устойчивому ключу `_hkey(h)` = `"t|нормализованный src"` (а не по номеру в списке, который сдвигается,
например, после импорта); `_hist_find(key)` ищет запись, `_set_hist(key, …)` меняет её и сохраняет `history.json`.
`/api/hist_import` во время замены отклоняется (`rep.err.busy`).

`replace_candidates()` проходит историю от новых к старым, по одной строке на оригинал, и вызывает `_check_entry(h)`
(свежая проверка файлов на диске), которая заполняет:

- `block` (отметить нельзя): `rep.b.replaced`, `src_missing`, `out_missing`; `imported` (запись пришла из
  `/api/hist_import` — её не проверить; после повторного сжатия файл можно заменить); `old_entry` (нет `src_sig`, `out_sig`
  или `out_hash` — запись старой версии не проверить; после повторного сжатия «↻ Повторить» файл можно заменить);
  `src_changed` (`src_sig` не совпадает с запомненным при сжатии); `out_changed` (не совпадает `out_sig` = `[размер, mtime]`
  сжатого файла из истории — файл изменили или подменили); `not_smaller` (`out_size >= size`); `long_path` (настоящий путь
  оригинала, `имя.framewring-new.mp4` или `имя.mp4` — 250 символов и больше: такой файл Windows удаляет насовсем, мимо
  корзины, — проверено); `busy` (задача с этим путём `queued` / `probing` / `running`); `bin_check(src, size)` → `no_bin` /
  `bin_off` / `bin_small`; `collision` (целевой `имя.mp4` уже есть и это не оригинал); `leftover` (лежит
  `имя.framewring-new.mp4` от незавершённой замены); `check_failed` (сама проверка упала с ошибкой — одна плохая запись
  не ломает окно);
- `warn`: `rep.w.no_test` (нет VMAF — не было теста или тест был с другими режимом или качеством, чем сжатие), `vmaf` (< 93), `edit` (кодек оригинала из `EDIT_CODECS`: ProRes, DNxHD, CineForm, FFV1, …),
  `lost_video` / `lost_subs` / `lost_data` / `lost_att` (`stream_counts` через `ffprobe`: у оригинала больше дополнительных
  видеодорожек (обложки не считаются), субтитров, дорожек данных (телеметрия GoPro, таймкод) или вложений, чем у сжатого),
  `small` (выигрыш < 20%, только если нет запретов).

`bin_check(path, size)` возвращает `None`, только если все проверки говорят, что файл такого размера попадёт в корзину
(последнее слово всё равно за Windows, поэтому ниже есть `FOF_WANTNUKEWARNING` и `in_recycle_bin`), иначе — причину:

- `has_recycle_bin` смотрит на настоящий путь `_real_path` (диск `subst` → его папка через `QueryDosDeviceW`, подключённый
  сетевой диск → `\\сервер\…`, junction/символические ссылки — через `realpath`): проходит только `GetDriveTypeW == DRIVE_FIXED`,
  UNC-пути — никогда;
- GUID тома (`GetVolumeNameForVolumeMountPointW`) выбирает `HKCU\…\Explorer\BitBucket\Volume\{GUID}`: `NukeOnDelete` →
  `bin_off`; `MaxCapacity` (МБ) — размер корзины; значения `NoRecycleFiles` и `RecycleBinSize` (%) из `Policies\Explorer`
  в HKLM/HKCU имеют приоритет; если настроек нет, берётся 5% диска;
- занятое место — из `SHQueryRecycleBinW`; если `size` > ёмкость − занято → `bin_small` (Windows удалила бы насовсем).

`replace_run(keys)` не запускается дважды; в фоновом потоке вызывает `_replace_one` для каждого ключа; ошибка в одном файле
записывается в его элемент, и замена идёт дальше. `_replace_one`:

1. `_check_entry` — запретов нет; затем `file_sha256(out)` должен совпасть с `out_hash`, запомненным при сжатии, — любой
   изменённый байт означает провал (`verify.hash`, у записи появляется `verify_failed`);
2. `verify_output`: `ffprobe` сжатого файла — длительность в пределах max(1 с, min(3 с, 0,1% длины)) от оригинала, то же
   число звуковых дорожек; затем видеодорожка декодируется целиком (`ffmpeg -v error -i out -map 0:V:0 -f null -`, прогресс
   из `-progress`) и должна дойти до длительности оригинала за вычетом допуска (`verify.short` — ловит обрезанное видео, даже
   если звук полной длины); затем отдельно декодируется звук сжатого файла (`-map 0:a`), а также звук оригинала: звук сжатого
   не должен быть короче звука оригинала за вычетом допуска (`verify.audio_short`). Любой вывод в stderr или ненулевой код
   выхода — провал (у записи появляется `verify_failed`);
3. `_check_entry` ещё раз прямо перед переносом (проверка могла идти долго);
4. в историю записывается намерение: `replace_tmp` (временный путь) и `replace_copy` (перенос между томами);
5. сжатый файл становится `имя.framewring-new.mp4` в папке оригинала: на том же томе — `os.rename` (никогда не перезаписывает:
   если имя занято — ошибка); иначе `copy2` и побайтовая сверка (`filecmp.cmp(shallow=False)`); размер должен совпасть
   с `out_sig[0]`. При неудаче файл возвращается / копия удаляется, намерение снимается;
6. ещё раз `bin_check` с текущим размером, затем `recycle(src)` — `SHFileOperationW` по **настоящему пути** с
   `FO_DELETE | FOF_ALLOWUNDO | FOF_WANTNUKEWARNING` (тихо, без окон ошибок; если Windows всё же решит удалить насовсем, она
   спросит, а не сделает молча); успех — только если вызов вернул 0, ничего не прервано и файла больше нет. При неудаче
   временный файл возвращается на место (или копия удаляется) — ничего не изменилось (`rep.err.rollback`, если и это не вышло);
7. `in_recycle_bin(src, t0)` читает `$I`-записи в `$Recycle.Bin` этого диска (исходный путь и время удаления — из самой записи,
   форматы v1 и v2), повторяя до ~4,5 с;
8. `os.rename(tmp, имя.mp4)` (не перезаписывает); если этот шаг не удался, элемент заканчивается как `warn` с
   `rep.err.final`, где указан временный файл (оригинал уже в корзине);
9. исходная копия с другого тома удаляется; папка сжатого файла убирается, только если она называется `compressed` и пуста
   (выбранная пользователем папка вывода — никогда); запись истории получает `replaced`, `replaced_t`, новые `out`,
   `out_size`, `out_sig`, намерение снимается; задача — `replaced` и `out_path`. Если на шаге 7 оригинал в корзине не нашёлся,
   элемент заканчивается как `warn` с `rep.err.not_in_bin`.

Состояния элемента: `done`; `warn` (`_ItemError(after=True)`: оригинал в корзине, но его там не нашли или новый файл остался
с временным именем — показывается как «⚠ …»); `error` (оригинал не заменён).

Корзина никогда не подразумевается: `bin_check` и `long_path` проверяются заранее (корзина есть, включена, в ней хватает места,
путь не слишком длинный); если Windows всё же собралась бы удалить насовсем, из-за `FOF_WANTNUKEWARNING` она сначала спросит;
после этого `in_recycle_bin` проверяет, что оригинал в корзине, и элемент предупреждает, если нет.

`replace_recover()` запускается при старте (после `load_history`) для каждой записи с `replace_tmp`: если временный файл есть,
а оригинал на месте — откат (копия удаляется или файл возвращается в `out`); если оригинала уже нет (он в корзине) — временный
файл становится `имя.mp4`, запись помечается `replaced`. Если временного файла нет, запись помечается `replaced`, когда
оригинала нет, а у `имя.mp4` размер из `out_sig`, или намерение просто снимается, если оригинал на месте.

Проверено тестами: mp4 → mp4 на месте; mkv → mp4 рядом; отказ при совпадении имени; повреждённый сжатый файл пойман
декодированием; изменённый оригинал отклонён; сбой на шаге с корзиной полностью откатывается; плюс 12 сценариев независимого
ревью (см. DEVLOG, 2026-11-12).

### Особенности платформ

- **Windows:** Job Object, `SetThreadExecutionState` (не уснуть), `SO_EXCLUSIVEADDRUSE`, Everything IPC, определение SSD,
  предупреждение о файле подкачки, своё окно через pywebview (WebView2) с окнами выбора файлов и перетаскиванием; в режиме браузера — окна выбора через tkinter.
- **macOS:** `caffeinate`, VideoToolbox H.265, выбор файлов через `osascript`. Почти не тестировалось.
- **Linux:** `prctl(PR_SET_PDEATHSIG)`, `/proc/meminfo`, `zenity`. Почти не тестировалось.

### Обновления

- `check_update` запускается раз за запуск (через 4 с после старта), если не выключена настройка `update_check`. Это один
  запрос к `api.github.com` за последним релизом `remrem23/framewring`; черновики, пре-релизы и версии не новее текущей
  игнорируются. Принимаются только файлы `-setup.exe` и `SHA256SUMS.txt` этого релиза с
  `github.com/remrem23/framewring/releases/download/`. Ничего о файлах пользователя не передаётся.
- Результат хранится в `UPDATE` и отдаётся в `/api/status` как `update` (`latest`, `state`: `""` / `download` / `install` /
  `error`, `pct`, `err`) вместе с `install_kind`. Интерфейс показывает полосу «Доступна версия Framewring X.» с кнопками
  «Обновить» / «Что нового» / «Позже» («Позже» скрывает эту версию через `localStorage`); для `portable` и `source` первая
  кнопка — «Скачать» (`/api/update_page`).
- `install_update` (только при `install_kind() == "installer"`): скачивает `SHA256SUMS.txt` и установщик в
  `%TEMP%\FramewringUpdate`, сверяет SHA-256, отпускает мьютекс единственного экземпляра, запускает установщик отдельным
  процессом с `/SILENT /SP- /NOCANCEL /NORESTART /FWUPDATE=1` и завершается. Настройки, очередь и история остаются
  в `%APPDATA%\Framewring`. Проверено целиком в тесте перед первым релизом: обновление 0.8.0 → 0.9.0 заняло примерно 20 с.
- В установщике (`packaging/framewring.iss`) есть `[Code] IsSelfUpdate` — истина, если передан `/FWUPDATE=1`; запись `[Run]`,
  которая запускает `Framewring.exe` после тихой установки, проверяет его, поэтому программа перезапускается только после
  самообновления, а не после тихой установки администратором.

### Сборка

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, тексты лицензий);
`packaging/release.py` — установщик Inno Setup (`packaging/framewring.iss`), портабл-zip, `SHA256SUMS.txt`.

Релизы собирает GitHub Actions (`.github/workflows/build.yml`) на чистой машине `windows-2025`: Python 3.12.10, точные
версии пакетов из `packaging/requirements-build.txt`, FFmpeg из `packaging/ffmpeg.json` (сборка Gyan, сверка SHA-256 в
`packaging/get_ffmpeg.py`), затем `build.py`, проверка запуска (`/api/ping`), `release.py` и подтверждение происхождения
(build provenance) для установщика и архива. При ручном запуске файлы выкладываются как артефакт запуска; метка `vX.Y.Z`
(должна совпадать с `__version__`) вдобавок создаёт черновик релиза, который публикуется вручную. Опубликованный релиз
никогда не перезаписывается.
