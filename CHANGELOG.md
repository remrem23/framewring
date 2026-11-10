**English** · [Русский](#русский)

# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/).
Detailed development history with measurements: [DEVLOG.md](DEVLOG.md).
Each version is described in English first, then in Russian.

## [0.9.0] — 2026-11-11

First public release.

### English

#### Added
- **Find heavy videos** on all drives: Everything index (seconds) or a multi-threaded folder walk; estimated savings,
  duplicate detection, editing codecs (ProRes, DNxHD) not ticked automatically. After a long search without Everything —
  an unobtrusive hint to install it (can be hidden).
- Compression on an **Nvidia GPU** (AV1, H.265) and on the **CPU** (x265, SVT-AV1); the GPU is recommended by default when available.
- **Test** on a piece of the video: forecast of size and time, VMAF.
- The queue and the compression **history** survive restarts; **↻ Retry** for failed files; **📂 Compressed / 📂 Original**.
- "Finishing the file" stage with progress; warnings about a disabled page file and low free space.
- **English interface** alongside Russian, with an **RU | EN** switch (defaults to the Windows language).
  Names: **Framewring** (English), **Framewring Жмых** (Russian); version number in the interface.
- **Own app window** (Edge WebView2) instead of a console and a browser tab; closing during compression asks
  "Stop and quit?". Without WebView2 the app opens in the browser and says so. Starting it again brings up the open window.
- **Drag & drop** files and folders onto the window.
- **Windows build:** `Framewring.exe` (PyInstaller, Python 3.12) with an icon and version info; FFmpeg bundled;
  third-party license texts shipped in the `licenses` folder.
- **Installer** (Inno Setup): no admin rights, `%LOCALAPPDATA%\Programs\Framewring`, Start menu and optional desktop shortcut,
  uninstall via *Apps*; settings and history are kept on uninstall. The installer closes a running copy and removes stale files on upgrade.
- **Portable zip** (data in `data\` next to the exe). `SHA256SUMS.txt` for both.
- Data folder depends on how the app runs: from source — next to `app.py`; portable — `data\`; installed — `%APPDATA%\Framewring`.
  The exe writes its log to `framewring.log` there.
- **♥ Support the author** opens a window with a link to the official [support page](DONATE.md) on GitHub —
  there are no wallet addresses in the program, so a modified copy cannot swap them.
- License: GNU GPL v3.

#### Changed
- **Stop** asks for confirmation.
- The file dialog opens inside the program (no separate Python process).
- Layout fixes for small windows.

#### Fixed
- **Never overwrite originals or unrelated files:** a result in the source folder gets a `_compressed` suffix; same-folder detection
  works through junctions and different path spellings; which outputs belong to Framewring is remembered across sessions
  via the history; name collisions are detected case-insensitively.
- **Variable-frame-rate** MKV no longer drops frames (`-fps_mode passthrough`); test VMAF on VFR video fixed.
- VMAF was underestimated (~75 instead of ~96) because frames were matched by time.
- **Security:** the interface token can no longer be read by other local processes (the UI is served at a tokenized URL,
  status requires the token); anti-framing headers.
- SVT-AV1 crash on low memory; one-off memory errors are retried.
- FFmpeg kept running after the window was closed; two instances shared one port.
- Losing a finished file if an antivirus or a player held it; result name collisions.
- Interlaced video, MKV subtitles, odd resolutions, cover art picked instead of video, file date.

### Русский

#### Добавлено
- **Поиск тяжёлых видео** на дисках: индекс Everything (секунды) или многопоточный обход; оценка экономии, дубликаты,
  монтажные кодеки (ProRes, DNxHD) не отмечаются автоматически. После долгого поиска без Everything — ненавязчивая подсказка
  установить его (можно скрыть).
- Сжатие на **видеокарте Nvidia** (AV1, H.265) и **процессоре** (x265, SVT-AV1); видеокарта рекомендуется по умолчанию, если есть.
- **Тест** на куске видео: прогноз размера и времени, VMAF.
- Очередь и **история** сжатия сохраняются между запусками; «↻ Повторить» для неудачных файлов; «📂 Сжатый / 📂 Оригинал».
- Этап «Дописываю файл» с прогрессом; предупреждения о выключенном файле подкачки и свободном месте.
- **Английский интерфейс** рядом с русским, переключатель **RU | EN** (по умолчанию — язык Windows).
  Названия: **Framewring** (англ.), **Framewring Жмых** (рус.); номер версии в интерфейсе.
- **Своё окно программы** (Edge WebView2) вместо консоли и вкладки браузера; при закрытии во время сжатия — вопрос
  «Остановить и выйти?». Без WebView2 программа открывается в браузере и сообщает об этом. Повторный запуск поднимает открытое окно.
- **Перетаскивание** файлов и папок в окно.
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
- Лицензия: GNU GPL v3.

#### Изменено
- **«Стоп»** спрашивает подтверждение.
- Окно выбора файлов открывается внутри программы (без отдельного процесса Python).
- Вёрстка исправлена для маленьких окон.

#### Исправлено
- **Оригиналы и чужие файлы никогда не перезаписываются:** результат в папке оригинала получает суффикс `_compressed`;
  совпадение папок определяется и через junction-ссылки и разное написание пути; какие файлы созданы Framewring,
  запоминается между сеансами по истории; совпадение имён проверяется без учёта регистра.
- Видео с **переменной частотой кадров** (MKV) больше не теряет кадры (`-fps_mode passthrough`); исправлен VMAF теста для такого видео.
- VMAF занижался (~75 вместо ~96) из-за сопоставления кадров по времени.
- **Безопасность:** токен интерфейса больше не может прочитать другой локальный процесс (интерфейс открывается по адресу с токеном,
  статус требует токен); заголовки против встраивания в чужие страницы.
- Падение SVT-AV1 при нехватке памяти; разовые сбои памяти повторяются.
- ffmpeg оставался работать после закрытия окна; два экземпляра делили один порт.
- Потеря готового файла, если его держал антивирус или плеер; коллизии имён результатов.
- Черезстрочное видео, субтитры MKV, нечётное разрешение, обложка вместо видео, дата файла.

[0.9.0]: https://github.com/remrem23/framewring/releases/tag/v0.9.0

---

<a id="русский"></a>
## Русский

Журнал изменений ведётся по формату [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — по [SemVer](https://semver.org/lang/ru/).
Каждая версия описана сначала на английском, затем на русском — см. подраздел **«Русский»** внутри каждой версии выше.
Подробная история разработки — в [DEVLOG.md](DEVLOG.md#русский).
