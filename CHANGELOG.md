**English** · [Русский](#русский)

# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/).
Detailed development history with measurements: [DEVLOG.md](DEVLOG.md).
Each version is described in English first, then in Russian.

## [0.9.2] — 2026-11-12

### English

#### Changed
- **Thorough** speed for **CPU · AV1** now uses SVT-AV1 preset 4 instead of 5: on a 1080p test the file is ~7% smaller than before (~16% smaller than **Normal**) and encoding takes ~1.7× as long as **Normal** ([#1](https://github.com/remrem23/framewring/issues/1)).

#### Added
- **Backups of your data.** Settings, history and the queue are saved with up to 3 backup copies. If a file is damaged or the data folder is deleted, Framewring restores it from the newest good copy on the next start. The installed version keeps the backups in `%LOCALAPPDATA%\Framewring\backup` — separately from the data folder.

#### Fixed
- An unfinished `.part.mp4` is no longer left behind when you quit in the middle of compression or after a crash: it is removed on exit, or on the next start.

### Русский

#### Изменено
- Скорость **«Тщательно»** для **«Процессор · AV1»** теперь использует пресет 4 у SVT-AV1 вместо 5: на тесте 1080p файл на ~7% меньше прежнего (на ~16% меньше, чем **«Обычно»**), а сжатие идёт примерно в 1,7 раза дольше, чем **«Обычно»** ([#1](https://github.com/remrem23/framewring/issues/1)).

#### Добавлено
- **Резервные копии данных.** Настройки, история и очередь сохраняются с резервными копиями (до 3 штук). Если файл повреждён или папку данных удалили, при следующем запуске Framewring восстановит всё из последней целой копии. Установленная версия хранит копии в `%LOCALAPPDATA%\Framewring\backup` — отдельно от папки данных.

#### Исправлено
- Недоделанный `.part.mp4` больше не остаётся, если выйти посреди сжатия или после сбоя: он удаляется при выходе или при следующем запуске.

## [0.9.1] — 2026-11-11

### English

#### Fixed
- **No more files bigger than the original.** Re-encoding a video that is already efficiently compressed (e.g. HEVC at a modest bitrate) could produce a *larger* file and waste hours. Now Framewring watches the output size while compressing: if it's clear after 10–25% of the file that the result won't be smaller, it stops early. If a finished result is not at least 3% smaller, it is deleted. In both cases the original is untouched and the video is marked **Kept as is**; **↻ Retry** (e.g. with **Compact**) stays available.

### Русский

#### Исправлено
- **Больше никаких файлов крупнее оригинала.** Пережатие уже эффективно сжатого видео (например, HEVC с умеренным битрейтом) могло дать *больший* файл и отнять часы. Теперь Framewring следит за размером во время сжатия: если через 10–25% файла видно, что результат не станет меньше, сжатие останавливается сразу. Если готовый результат меньше оригинала не хотя бы на 3%, он удаляется. В обоих случаях оригинал не тронут, а видео помечается **«Оставлен как есть»**; **«↻ Повторить»** (например, с **«Компактным»**) остаётся доступной.

## [0.9.0] — 2026-11-11

### English

First public release.

#### Added
- **Find heavy videos** on all drives: Everything index (seconds) or a multi-threaded folder walk; estimated savings,
  duplicate detection, editing codecs (ProRes, DNxHD) not ticked automatically. After a long search without Everything —
  an unobtrusive hint to install it (can be hidden).
- Compression on an **Nvidia GPU** (AV1, H.265) and on the **CPU** (x265, SVT-AV1); the GPU is recommended by default when available.
- **AMD and Intel GPUs:** modes *AMD GPU · AV1*, *AMD GPU · H.265* (AMF, 10-bit, constant QP) and *Intel GPU · AV1*,
  *Intel GPU · H.265* (Quick Sync, ICQ). Every mode is test-encoded on startup; a failed GPU mode is greyed out with
  the reason only if that vendor's GPU is in the PC, modes for absent vendors are hidden. Recommended order:
  Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → AMD AV1 → Intel AV1 → CPU (AMD AV1 and Intel AV1 stay below
  H.265 until verified on real hardware). AMD H.265 is verified on Ryzen integrated graphics; AMD AV1 and Intel are not
  yet tested on real hardware.
- **Test** on a piece of the video: forecast of size and time, VMAF.
- The queue and the compression **history** survive restarts; **↻ Retry** for failed files; **📂 Compressed / 📂 Original**.
- "Finishing the file" stage with progress; warnings about a disabled page file and low free space.
- **Interface in 7 languages:** English, Russian, German, French, Spanish, Portuguese and Simplified Chinese; language list in the header (defaults to the Windows language).
  Name **Framewring**; version number in the interface.
- **Own app window** (Edge WebView2) instead of a console and a browser tab; closing during compression asks
  "Stop and quit?". Without WebView2 the app opens in the browser and says so. Starting it again brings up the open window.
- **Drag & drop** files and folders onto the window.
- **App-style layout:** settings stay pinned on the left, the file list, search and history scroll separately on the right; the window title bar matches the dark theme.
- **Windows build:** `Framewring.exe` (PyInstaller, Python 3.12) with an icon and version info; FFmpeg bundled;
  third-party license texts shipped in the `licenses` folder.
- **Installer** (Inno Setup): no admin rights, `%LOCALAPPDATA%\Programs\Framewring`, Start menu and optional desktop shortcut,
  uninstall via *Apps*; settings and history are kept on uninstall. The installer closes a running copy and removes stale files on upgrade.
- **Portable zip** (data in `data\` next to the exe). `SHA256SUMS.txt` for both.
- Data folder depends on how the app runs: from source — next to `app.py`; portable — `data\`; installed — `%APPDATA%\Framewring`.
  The exe writes its log to `framewring.log` there.
- **♥ Support the author** opens a window with a link to the official [support page](DONATE.md) on GitHub —
  there are no wallet addresses in the program, so a modified copy cannot swap them.
- **🐞 Report a bug** in the header: opens the GitHub bug-report form with the program version and install type, Windows
  version, graphics cards, FFmpeg version and mode pre-filled (everything is visible before sending; a free GitHub account
  is needed); **📂 Show the log** opens the folder with `framewring.log`.
- **Update check and one-click update:** once per launch the app asks GitHub for the newest version (setting *Check for
  updates on startup*). If there is one, a bar offers *Update* / *What's new* / *Later*. The installed version downloads
  the new setup.exe, verifies its SHA-256 against `SHA256SUMS.txt` of the release, installs silently and restarts, keeping
  settings, queue and history; portable and source versions get *Download* (the release page).
- License: GNU GPL v3.

#### Changed
- **Stop** asks for confirmation.
- The file dialog opens inside the program (no separate Python process).
- Layout fixes for small windows.
- The page-file warning can be hidden with **✕** (remembered).

#### Fixed
- **Never overwrite originals or unrelated files:** a result in the source folder gets a `_compressed` suffix; same-folder detection
  works through junctions and different path spellings; which outputs belong to Framewring is remembered across sessions
  via the history; name collisions are detected case-insensitively.
- **Variable-frame-rate** MKV no longer drops frames (`-fps_mode passthrough`); test VMAF on VFR video fixed.
- VMAF was underestimated (~75 instead of ~96) because frames were matched by time.
- **Security:** the interface token can no longer be read by other local processes (the UI is served at a tokenized URL,
  status requires the token); anti-framing headers. `/api/ping` and `/api/show` refuse requests made from web pages.
- Layout at the minimum window size: the search results list and the history now fit and scroll correctly.
- Links in the interface are easier to read.
- SVT-AV1 crash on low memory; one-off memory errors are retried.
- FFmpeg kept running after the window was closed; two instances shared one port.
- Losing a finished file if an antivirus or a player held it; result name collisions.
- Interlaced video, MKV subtitles, odd resolutions, cover art picked instead of video, file date.

### Русский

Первый публичный выпуск.

#### Добавлено
- **Поиск тяжёлых видео** на дисках: индекс Everything (секунды) или многопоточный обход; оценка экономии, дубликаты,
  монтажные кодеки (ProRes, DNxHD) не отмечаются автоматически. После долгого поиска без Everything — ненавязчивая подсказка
  установить его (можно скрыть).
- Сжатие на **видеокарте Nvidia** (AV1, H.265) и **процессоре** (x265, SVT-AV1); видеокарта рекомендуется по умолчанию, если есть.
- **Видеокарты AMD и Intel:** режимы «Видеокарта AMD · AV1», «Видеокарта AMD · H.265» (AMF, 10 бит, постоянный QP)
  и «Видеокарта Intel · AV1», «Видеокарта Intel · H.265» (Quick Sync, ICQ). При запуске каждый режим проверяется пробным
  кодированием; режим видеокарты, не прошедший проверку, показывается серым с причиной, только если видеокарта этого
  производителя в компьютере есть, режимы отсутствующих производителей скрыты. Порядок рекомендации:
  Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → AMD AV1 → Intel AV1 → процессор (AMD AV1 и Intel AV1 стоят ниже
  H.265, пока не проверены на реальном железе). AMD H.265 проверен на встроенной графике Ryzen; AMD AV1 и Intel на реальном
  железе ещё не проверялись.
- **Тест** на куске видео: прогноз размера и времени, VMAF.
- Очередь и **история** сжатия сохраняются между запусками; «↻ Повторить» для неудачных файлов; «📂 Сжатый / 📂 Оригинал».
- Этап «Дописываю файл» с прогрессом; предупреждения о выключенном файле подкачки и свободном месте.
- **Интерфейс на 7 языках:** русский, английский, немецкий, французский, испанский, португальский и китайский (упрощённый); выбор в шапке (по умолчанию — язык Windows).
  Названия: **Framewring** (англ.), **Framewring Жмых** (рус.); номер версии в интерфейсе.
- **Своё окно программы** (Edge WebView2) вместо консоли и вкладки браузера; при закрытии во время сжатия — вопрос
  «Остановить и выйти?». Без WebView2 программа открывается в браузере и сообщает об этом. Повторный запуск поднимает открытое окно.
- **Перетаскивание** файлов и папок в окно.
- **Раскладка как у приложения:** настройки всегда видны слева, список файлов, поиск и история листаются отдельно справа; полоса заголовка окна — в цвет тёмной темы.
- **Сборка для Windows:** `Framewring.exe` (PyInstaller, Python 3.12) со значком и сведениями о версии; FFmpeg в комплекте;
  тексты лицензий сторонних компонентов — в папке `licenses`.
- **Установщик** (Inno Setup): без прав администратора, `%LOCALAPPDATA%\Programs\Framewring`, ярлык в «Пуске» и по желанию
  на рабочем столе, удаление через «Приложения»; настройки и история при удалении сохраняются. При обновлении установщик
  закрывает запущенную программу и удаляет устаревшие файлы.
- **Портабл-архив** (данные в `data\` рядом с exe). `SHA256SUMS.txt` для обоих.
- Папка данных зависит от способа запуска: из исходников — рядом с `app.py`; портабл — `data\`; установленная — `%APPDATA%\Framewring`.
  Журнал exe-версии — там же, `framewring.log`.
- **«♥ Поддержать автора»** открывает окно со ссылкой на официальную [страницу поддержки](DONATE.md#русский) на GitHub —
  адресов кошельков в программе нет, подменить их в копии нельзя.
- **«🐞 Сообщить об ошибке»** в шапке: открывает форму на GitHub, где уже заполнены версия программы и тип установки,
  версия Windows, видеокарты, версия FFmpeg и режим (всё видно до отправки; нужен бесплатный аккаунт GitHub);
  **«📂 Показать журнал»** открывает папку с `framewring.log`.
- **Проверка обновлений и обновление в один клик:** один раз при запуске программа спрашивает у GitHub номер новейшей
  версии (настройка «Проверять обновления при запуске»). Если она есть, появляется полоса «Обновить» / «Что нового» / «Позже».
  Установленная версия скачивает новый setup.exe, сверяет его SHA-256 с `SHA256SUMS.txt` релиза, тихо устанавливает и
  перезапускается, сохраняя настройки, очередь и историю; портабл-версия и запуск из исходников получают «Скачать» (страница релиза).
- Лицензия: GNU GPL v3.

#### Изменено
- **«Стоп»** спрашивает подтверждение.
- Окно выбора файлов открывается внутри программы (без отдельного процесса Python).
- Вёрстка исправлена для маленьких окон.
- Предупреждение о файле подкачки можно скрыть крестиком **✕** (запоминается).

#### Исправлено
- **Оригиналы и чужие файлы никогда не перезаписываются:** результат в папке оригинала получает суффикс `_compressed`;
  совпадение папок определяется и через junction-ссылки и разное написание пути; какие файлы созданы Framewring,
  запоминается между сеансами по истории; совпадение имён проверяется без учёта регистра.
- Видео с **переменной частотой кадров** (MKV) больше не теряет кадры (`-fps_mode passthrough`); исправлен VMAF теста для такого видео.
- VMAF занижался (~75 вместо ~96) из-за сопоставления кадров по времени.
- **Безопасность:** токен интерфейса больше не может прочитать другой локальный процесс (интерфейс открывается по адресу с токеном,
  статус требует токен); заголовки против встраивания в чужие страницы. `/api/ping` и `/api/show` отклоняют запросы с веб-страниц.
- Вёрстка при минимальном размере окна: список результатов поиска и история теперь помещаются и листаются правильно.
- Ссылки в интерфейсе стало легче читать.
- Падение SVT-AV1 при нехватке памяти; разовые сбои памяти повторяются.
- ffmpeg оставался работать после закрытия окна; два экземпляра делили один порт.
- Потеря готового файла, если его держал антивирус или плеер; коллизии имён результатов.
- Черезстрочное видео, субтитры MKV, нечётное разрешение, обложка вместо видео, дата файла.

[0.9.2]: https://github.com/remrem23/framewring/releases/tag/v0.9.2
[0.9.1]: https://github.com/remrem23/framewring/releases/tag/v0.9.1
[0.9.0]: https://github.com/remrem23/framewring/releases/tag/v0.9.0

---

<a id="русский"></a>
## Русский

Журнал изменений ведётся по формату [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — по [SemVer](https://semver.org/lang/ru/).
Каждая версия описана сначала на английском, затем на русском — см. подраздел **«Русский»** внутри каждой версии выше.
Подробная история разработки — в [DEVLOG.md](DEVLOG.md#русский).
