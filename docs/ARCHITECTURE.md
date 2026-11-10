**English** · [Русский](#русский)

# Framewring architecture

The whole program is one file, `app.py` (~2,600 lines). It uses only the Python standard library;
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
| Modes (`PRESETS`, `QUALITY`, `SPEED`, `RECOMMEND`, `video_args`) | encoders and their flags; recommendation order |
| Capabilities (`detect_caps`) | which encoders the FFmpeg build has; hardware ones are verified with a 0.5 s trial encode |
| `probe` / `probe_cached` | file parameters via ffprobe; cache keyed by (size, mtime), saved in `probe_cache.json` |
| Jobs (`JOBS`, `add_path`, `out_dir_for`, `out_path_for`) | the file list; output naming that never overwrites an original or a foreign file |
| Scanner (`scan_thread`, `everything_search`, `_scan_walk`, `estimate`) | finding big videos, estimating savings |
| Encoding (`run_ffmpeg`, `encode`, `do_full`, `do_test`) | running ffmpeg, parsing `-progress`, retries, test + VMAF |
| Finishing (`_finish_watch`, `finalize`) | progress of the `+faststart` stage; robust rename of `.part` |
| Queue and history (`queue_saver`, `load_queue`, `add_history`) | survive restarts |
| `worker` | one thread, takes `queued` jobs in order |
| HTTP (`H`, `snapshot`) | API, Host and token checks, security headers |
| `HTML` | the interface (English and Russian): settings, queue, search, history, donate window |
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
  used by a second launch to find and raise the running instance; they reveal nothing.
- Responses carry `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

| Method and path | Purpose |
|---|---|
| `GET /?t=TOKEN` | the interface |
| `GET /api/status?sv=N` | state snapshot; search results are sent only if version `sv` changed |
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
| `POST /api/history` | compression history |
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | drive list, search |
| `POST /api/quit` | quit (browser mode only, where there is no window to close) |

## Data files (in the data folder, never in git)

| File | Contents | Personal data |
|---|---|---|
| `settings.json` | chosen mode, quality, output folder | no |
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

## Build

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, license texts);
`packaging/release.py` — Inno Setup installer (`packaging/framewring.iss`), portable zip, `SHA256SUMS.txt`.

---

<a id="русский"></a>
## Русский

**Архитектура Framewring Жмых**

Вся программа — один файл `app.py` (~2600 строк). Используется только стандартная библиотека Python;
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
| Режимы (`PRESETS`, `QUALITY`, `SPEED`, `RECOMMEND`, `video_args`) | таблица кодеров и их флагов; порядок рекомендации |
| Возможности (`detect_caps`) | какие кодеры есть в сборке FFmpeg; аппаратные проверяются пробным кодированием 0,5 с |
| `probe` / `probe_cached` | параметры файла через ffprobe; кэш по (размер, mtime), сохраняется в `probe_cache.json` |
| Задачи (`JOBS`, `add_path`, `out_dir_for`, `out_path_for`) | список файлов; имя результата, которое никогда не затирает оригинал или чужой файл |
| Сканер (`scan_thread`, `everything_search`, `_scan_walk`, `estimate`) | поиск больших видео, оценка экономии |
| Кодирование (`run_ffmpeg`, `encode`, `do_full`, `do_test`) | запуск ffmpeg, разбор `-progress`, повторы, тест + VMAF |
| Завершение (`_finish_watch`, `finalize`) | прогресс этапа `+faststart`; надёжное переименование `.part` |
| Очередь и история (`queue_saver`, `load_queue`, `add_history`) | переживают перезапуск |
| `worker` | один поток, берёт задачи `queued` по порядку |
| HTTP (`H`, `snapshot`) | API, проверка Host и токена, заголовки безопасности |
| `HTML` | интерфейс (английский и русский): настройки, очередь, поиск, история, окно доната |
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
  по ним второй запуск находит и поднимает работающий экземпляр; ничего не раскрывают.
- В ответах: `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.

| Метод и путь | Назначение |
|---|---|
| `GET /?t=ТОКЕН` | интерфейс |
| `GET /api/status?sv=N` | снимок состояния; результаты поиска отдаются, только если изменилась версия `sv` |
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
| `POST /api/history` | журнал сжатия |
| `POST /api/drives`, `/api/scan`, `/api/scan_cancel` | список дисков, поиск |
| `POST /api/quit` | выход (только в режиме браузера, где нет окна, которое можно закрыть) |

### Файлы данных (в папке данных, в git не попадают)

| Файл | Содержимое | Личные данные |
|---|---|---|
| `settings.json` | выбранный режим, качество, папка вывода | нет |
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

### Сборка

`packaging/build.py` — PyInstaller onedir (`Framewring.exe`, `_internal\`, `ffmpeg\`, тексты лицензий);
`packaging/release.py` — установщик Inno Setup (`packaging/framewring.iss`), портабл-zip, `SHA256SUMS.txt`.
