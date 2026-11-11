**English** · [Русский](#русский)

# Framewring architecture

The program is `app.py` (~2,900 lines) plus the interface strings in `i18n.py` and `locales/`. It uses only the Python standard library;
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
| Queue and history (`queue_saver`, `load_queue`, `add_history`) | survive restarts |
| `worker` | one thread, takes `queued` jobs in order |
| HTTP (`H`, `snapshot`) | API, Host and token checks, security headers |
| `HTML` | the interface (7 languages, strings from `i18n.py` + `locales/`): settings, queue, search, history, donate window, bug-report window, update bar |
| Updates (`UPDATE`, `install_kind`, `check_update`, `install_update`) | once per launch asks GitHub for the latest release; one-click update of the installed version (see *Updates* below) |
| Bug report (`report_url`) | URL of the GitHub issue form with version, Windows, GPU names, FFmpeg version and mode pre-filled |
| `run_window`, `_setup_log`, `main` | single instance per machine, data loading, threads, own window or browser, log file for the exe |

## Job lifecycle

`probing` → `ready` → `queued` → `running` → `done` | `skipped` | `tested` | `error` | `cancelled`

Full compression (`do_full`):
1. output name (`out_path_for`); skip if the result already exists and "Skip already compressed files" is on;
2. free-space check based on `estimate`;
3. `ffmpeg … -fps_mode passthrough -movflags +faststart` into `name.part.mp4`
   (filters: deinterlace, even dimensions; subtitles; audio copied when the container allows);
4. on a memory error — up to 3 attempts (for SVT-AV1 with a lower `lp`);
5. `finalize`: rename with waiting, original's date, history entry.

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
| `av1` | CPU · AV1 | `libsvtav1` | CRF 27 / 30 / 33 |

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
| `GET /api/status?sv=N` | state snapshot; search results are sent only if version `sv` changed; `update` (`latest`, `state`, `pct`, `err`) and `install_kind` (`installer` / `portable` / `source`) |
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
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | drive list, search |
| `POST /api/quit` | quit (browser mode only, where there is no window to close) |

## Data files (in the data folder, never in git)

| File | Contents | Personal data |
|---|---|---|
| `settings.json` | chosen mode, quality, output folder, options (incl. `update_check`) | no |
| `queue.json` | job list | **video paths** |
| `history.json` | compression history | **video paths** |
| `probe_cache.json` | video parameters | **video paths** |
| `framewring.log` | exe log (written only when there is no console) | **video paths** |
| `webview\` | window engine cache (WebView2) | no |

Data folder: from source — next to `app.py`; portable — `data\` next to the exe; installed — `%APPDATA%\Framewring`.
Writes are atomic: to a temporary file, then `os.replace`.

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
  Checked end-to-end: 0.8.0 → 0.9.0 in about 20 s.
- The installer (`packaging/framewring.iss`) has `[Code] IsSelfUpdate`, true when `/FWUPDATE=1` is passed; the `[Run]` entry
  that starts `Framewring.exe` after a silent install is guarded by it, so the app is relaunched only after a self-update,
  not after a silent install run by an administrator.

## Build

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, license texts);
`packaging/release.py` — Inno Setup installer (`packaging/framewring.iss`), portable zip, `SHA256SUMS.txt`.

---

<a id="русский"></a>
## Русский

**Архитектура Framewring Жмых**

Программа — это `app.py` (~2900 строк) плюс строки интерфейса в `i18n.py` и `locales/`. Используется только стандартная библиотека Python;
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
| Очередь и история (`queue_saver`, `load_queue`, `add_history`) | переживают перезапуск |
| `worker` | один поток, берёт задачи `queued` по порядку |
| HTTP (`H`, `snapshot`) | API, проверка Host и токена, заголовки безопасности |
| `HTML` | интерфейс (7 языков, строки из `i18n.py` + `locales/`): настройки, очередь, поиск, история, окно доната, окно «Сообщить об ошибке», полоса обновления |
| Обновления (`UPDATE`, `install_kind`, `check_update`, `install_update`) | раз за запуск спрашивает у GitHub последний релиз; обновление установленной версии в один клик (см. «Обновления» ниже) |
| Сообщение об ошибке (`report_url`) | адрес формы issue на GitHub с заполненными версией, Windows, видеокартами, версией FFmpeg и режимом |
| `run_window`, `_setup_log`, `main` | один экземпляр на машину, загрузка данных, потоки, своё окно или браузер, журнал для exe |

### Жизненный цикл задачи

`probing` → `ready` → `queued` → `running` → `done` | `skipped` | `tested` | `error` | `cancelled`

Полное сжатие (`do_full`):
1. имя результата (`out_path_for`); пропуск, если он уже есть и включено «Пропускать уже сжатые файлы»;
2. проверка свободного места по оценке `estimate`;
3. `ffmpeg … -fps_mode passthrough -movflags +faststart` в `имя.part.mp4`
   (фильтры: деинтерлейс, чётные размеры; субтитры; копирование звука, если формат допускает);
4. при ошибке памяти — до 3 попыток (для SVT-AV1 — со сниженным `lp`);
5. `finalize`: переименование с ожиданием, дата оригинала, запись в историю.

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
| `av1` | Процессор · AV1 | `libsvtav1` | CRF 27 / 30 / 33 |

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
| `GET /api/status?sv=N` | снимок состояния; результаты поиска отдаются, только если изменилась версия `sv`; `update` (`latest`, `state`, `pct`, `err`) и `install_kind` (`installer` / `portable` / `source`) |
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
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | список дисков, поиск |
| `POST /api/quit` | выход (только в режиме браузера, где нет окна, которое можно закрыть) |

### Файлы данных (в папке данных, в git не попадают)

| Файл | Содержимое | Личные данные |
|---|---|---|
| `settings.json` | выбранный режим, качество, папка вывода, опции (в т.ч. `update_check`) | нет |
| `queue.json` | список задач | **пути к видео** |
| `history.json` | журнал сжатия | **пути к видео** |
| `probe_cache.json` | параметры видео | **пути к видео** |
| `framewring.log` | журнал exe-версии (пишется, только когда нет консоли) | **пути к видео** |
| `webview\` | кэш движка окна (WebView2) | нет |

Папка данных: из исходников — рядом с `app.py`; портабл — `data\` рядом с exe; установленная — `%APPDATA%\Framewring`.
Запись атомарная: во временный файл, затем `os.replace`.

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
  в `%APPDATA%\Framewring`. Проверено целиком: 0.8.0 → 0.9.0 примерно за 20 с.
- В установщике (`packaging/framewring.iss`) есть `[Code] IsSelfUpdate` — истина, если передан `/FWUPDATE=1`; запись `[Run]`,
  которая запускает `Framewring.exe` после тихой установки, проверяет его, поэтому программа перезапускается только после
  самообновления, а не после тихой установки администратором.

### Сборка

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, тексты лицензий);
`packaging/release.py` — установщик Inno Setup (`packaging/framewring.iss`), портабл-zip, `SHA256SUMS.txt`.
