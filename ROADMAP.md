**English** · [Русский](#русский)

# Roadmap

Ideas and requests are welcome in [Issues](https://github.com/remrem23/framewring/issues).

## Done in 0.9.0

- Windows installer and portable zip with FFmpeg bundled, own app window (WebView2).
- **Interface in 7 languages** (English, Russian, German, French, Spanish, Portuguese and Simplified Chinese).
- Everything is optional: without it the multi-threaded folder walk is used automatically.
- **AMD (AMF)** and **Intel (QSV)** GPU encoding, AV1 and H.265, next to Nvidia. Every mode is test-encoded on startup;
  modes for GPU vendors the PC does not have are hidden.
- **Updates:** a check for a new version on GitHub once per launch (can be turned off); the installed version updates in one click.
- **🐞 Report a bug** button: opens the GitHub form with system details pre-filled and shows the log.

## Done in 0.9.1

- No more results bigger than the original: compression stops early when it can't save space, and the video is marked **Kept as is**.

## Done in 0.9.2

- “Thorough” speed for *CPU · AV1* uses SVT-AV1 preset 4 ([#1](https://github.com/remrem23/framewring/issues/1)).
- **Backups of your data:** settings, history and the queue are saved with up to 3 backup copies and restored automatically
  if a file gets damaged or the data folder is deleted (the installed version keeps them in `%LOCALAPPDATA%\Framewring\backup`).
- Leftover `.part.mp4` files are removed on exit in the middle of compression and on the next start after a crash.
- Installer and update tests in Windows Sandbox.

## Done in 0.9.3

- **⇄ Replace originals:** a compressed file takes the original's place (same folder and name, `.mp4`) — only for the files
  you tick yourself. Each one is first fully verified (SHA-256 checksum taken right after compression, decoded from start to
  end, duration, audio tracks and audio length match the original); the original goes to the Windows Recycle Bin. This is
  checked beforehand (Recycle Bin present, turned on, enough free space, path not too long); if Windows would still delete
  permanently it asks first; afterwards Framewring confirms the original is in the Recycle Bin and warns if not. Warnings
  for untested quality, low VMAF, editing sources and small savings; risky cases (changed files, old or imported history
  entries) are blocked.
- Fixed a false **Kept as is** on videos with a complex beginning: the early stop now compares the output with the part of
  the original already read.
- Startup and data robustness: a damaged queue or history entry no longer prevents start; history writes are serialized;
  the single-instance check comes first.
- A short **How it works** hint on first run.
- **History export and import** (export to the real *Documents* folder, timestamped name).

## Done in 0.9.5

- The PyInstaller bootloader is compiled from source in the GitHub Actions build; documentation and screenshots updated.

## Done in 0.9.4

- Modes not yet tested on real hardware are marked **experimental**; a **📤 Share result** button after a Test opens a
  ready-filled GitHub form (no file names or paths).
- Releases are built by GitHub Actions with build provenance; automated tests run on every build.
- Ko-fi in the support window.

## Road to 1.0

1.0 is about being **reliable on other people's computers** and finishing the main promise — actually freeing the space.
New big features wait until after 1.0.

| Version | What's in it |
|---|---|
| **0.9.2** ✓ | Done: SVT-AV1 preset 4 for “Thorough”, data backups, `.part.mp4` cleanup, Windows Sandbox tests. |
| **0.9.3** ✓ | Done: full verification of compressed files and **⇄ Replace originals** (originals go to the Recycle Bin), first-run hint, history export/import. **Still pending:** install via `winget`. |
| **0.9.5** ✓ | Done: bootloader compiled from source, updated docs and screenshots. |
| **0.9.4** ✓ | Done: experimental marks, **📤 Share result**, builds and tests in GitHub Actions. |
| **1.0.0-rc1** | Release candidate for testers (marked as pre-release, so the built-in updater doesn't offer it to everyone). |
| **1.0.0** | When the criteria below are met. |

**Also before 1.0:** every release checked on VirusTotal; experimental marks for untested modes and a **Share test result**
button, so anyone can report how a mode works on their hardware; ~~builds made by GitHub Actions~~ — done; ~~card payments on the support page (Ko-fi)~~ — done.

**1.0 is released when:**
- two weeks pass without a critical bug (damaged or lost files, the app won't start);
- automated tests (safe replacement of originals, history, real compression on the CPU) pass for every build on a clean
  Windows machine in GitHub Actions — without a GPU and without Everything;
- modes not yet confirmed on real hardware (*AMD GPU · AV1*, the Intel modes) are marked **experimental** in the app;
  the mark is removed as soon as someone reports a result;
- the built-in update has worked;
- the release is clean on VirusTotal.

Code signing (SignPath Foundation) is a goal, not a condition for 1.0: it needs some project history first.

**Help wanted:** if you have an AMD Radeon RX 7000, Intel graphics or Windows 10, run **Test (2 min)** on a couple of
videos and send the result to [Issues](https://github.com/remrem23/framewring/issues) — it helps a lot.

## After 1.0

- **Auto quality:** pick the compression level for a target VMAF (like ab-av1).
- Resume an interrupted file from where it stopped (it currently starts over).
- Explicit HDR support.
- Testing and builds for macOS / Linux.
- Smaller download (a leaner FFmpeg build).

## Known limitations

- Tested mainly on one machine (Windows 11, RTX 5070 Ti). Reports from other hardware are very welcome.
- *AMD GPU · H.265* has been checked on real hardware (graphics built into a Ryzen 7 9700X), but *AMD GPU · AV1*
  (Radeon RX 7000, Radeon 780M/880M) and the Intel modes (Quick Sync) have not been tested on real hardware yet — only the startup
  test-encode guards them, and AMD AV1 / Intel AV1 are recommended only after the H.265 modes. If you have such a card,
  please report in Issues.
- On AMD and Intel modes the video is decoded on the CPU (Nvidia modes decode on the GPU), so they load the CPU more.
- The savings estimate in the search assumes H.265 *Balanced*; the **Test** gives the exact forecast.
- The search skips folders named `games` (so as not to touch installed games) — videos inside such folders are not found.
- With the Windows page file disabled, memory errors are possible (the app retries and warns).
- Picture subtitles (PGS) cannot be stored in MP4 and are dropped with a warning.
- The app is not code-signed yet, so SmartScreen warns on first launch.

---

<a id="русский"></a>
## Русский

Идеи и пожелания — в [Issues](https://github.com/remrem23/framewring/issues).

### Сделано в 0.9.0

- Установщик и портабл-архив для Windows с FFmpeg внутри, своё окно программы (WebView2).
- **Интерфейс на 7 языках** (русский, английский, немецкий, французский, испанский, португальский и китайский (упрощённый)).
- Everything необязателен: без него автоматически работает многопоточный обход папок.
- Сжатие на видеокартах **AMD (AMF)** и **Intel (QSV)**, AV1 и H.265, наряду с Nvidia. При запуске каждый режим
  проверяется пробным кодированием; режимы производителей, чьей видеокарты в компьютере нет, скрыты.
- **Обновления:** проверка новой версии на GitHub один раз при запуске (можно отключить); установленная версия обновляется в один клик.
- Кнопка **«🐞 Сообщить об ошибке»:** открывает форму на GitHub с заполненными данными о системе и показывает журнал.

### Сделано в 0.9.1

- Больше никаких результатов крупнее оригинала: если сжатие не экономит место, оно останавливается сразу, а видео помечается **«Оставлен как есть»**.

### Сделано в 0.9.2

- Скорость «Тщательно» для «Процессор · AV1» — пресет 4 у SVT-AV1 ([#1](https://github.com/remrem23/framewring/issues/1)).
- **Резервные копии данных:** настройки, история и очередь сохраняются с резервными копиями (до 3 штук) и сами восстанавливаются,
  если файл повреждён или папку данных удалили (установленная версия хранит их в `%LOCALAPPDATA%\Framewring\backup`).
- Недоделанный `.part.mp4` удаляется при выходе посреди сжатия и при следующем запуске после сбоя.
- Проверка установщика и обновлений в «Песочнице Windows».

### Сделано в 0.9.3

- **«⇄ Заменить оригиналы»:** сжатый файл встаёт на место оригинала (та же папка и имя, `.mp4`) — только для файлов,
  которые ты отметил сам. Каждый сначала полностью проверяется (контрольная сумма SHA-256, посчитанная сразу после сжатия,
  декодирование от начала до конца, длительность, звуковые дорожки и длина звука совпадают с оригиналом); оригинал уходит
  в корзину Windows. Это проверяется заранее (корзина есть, включена, в ней хватает места, путь не слишком длинный); если
  Windows всё же собралась бы удалить насовсем, она сначала спросит; после замены Жмых проверяет, что оригинал в корзине,
  и предупреждает, если нет. Предупреждения о непроверенном качестве, низком VMAF, монтажных исходниках и небольшом
  выигрыше; рискованные случаи (изменённые файлы, старые или импортированные записи истории) заблокированы.
- Исправлено ложное **«Оставлен как есть»** у видео со сложным началом: ранняя остановка теперь сравнивает результат
  с уже прочитанной частью оригинала.
- Надёжность запуска и данных: испорченная запись очереди или истории больше не мешает запуску; записи истории идут
  по одной; проверка единственного экземпляра выполняется первой.
- Короткая подсказка **«Как это работает»** при первом запуске.
- **Экспорт и импорт истории** (экспорт — в настоящую папку «Документы», имя с датой и временем).

### Сделано в 0.9.5

- Загрузчик PyInstaller собирается из исходников в сборке GitHub Actions; обновлены документация и скриншоты.

### Сделано в 0.9.4

- Режимы, ещё не проверенные на реальном железе, помечены как **«экспериментальные»**; кнопка **«📤 Поделиться
  результатом»** после «Теста» открывает заполненную форму на GitHub (без имён файлов и путей).
- Релизы собирает GitHub Actions с подтверждением происхождения; при каждой сборке проходят автотесты.
- Ko-fi в окне поддержки.

### Путь к 1.0

1.0 — это **надёжность на чужих компьютерах** и выполненное до конца главное обещание: реально освобождать место.
Новые большие функции — после 1.0.

| Версия | Что входит |
|---|---|
| **0.9.2** ✓ | Сделано: пресет 4 у SVT-AV1 для «Тщательно», резервные копии данных, уборка `.part.mp4`, проверки в «Песочнице Windows». |
| **0.9.3** ✓ | Сделано: полная проверка сжатых файлов и **«⇄ Заменить оригиналы»** (оригиналы уходят в корзину), подсказка при первом запуске, экспорт и импорт истории. **Ещё не сделано:** установка через `winget`. |
| **0.9.5** ✓ | Сделано: загрузчик из исходников, обновлённые документы и скриншоты. |
| **0.9.4** ✓ | Сделано: пометка «экспериментальный», **«📤 Поделиться результатом»**, сборка и тесты в GitHub Actions. |
| **1.0.0-rc1** | Кандидат в релиз для тестеров (помечен как предварительный, поэтому встроенное обновление не предлагает его всем). |
| **1.0.0** | Когда выполнены условия ниже. |

**Ещё до 1.0:** проверка каждого релиза на VirusTotal; пометка «экспериментальный» у непроверенных режимов и кнопка
**«Поделиться результатом теста»**, чтобы любой мог сообщить, как режим работает на его железе; ~~сборка через GitHub Actions~~ — сделано; ~~оплата картой на странице поддержки (Ko-fi)~~ — сделано.

**1.0 выходит, когда:**
- две недели без критических ошибок (порча или потеря файлов, программа не запускается);
- автоматические тесты (безопасная замена оригиналов, история, настоящее сжатие на процессоре) проходят при каждой сборке
  на чистой Windows в GitHub Actions — без видеокарты и без Everything;
- режимы, ещё не подтверждённые на реальном железе (*AMD GPU · AV1*, режимы Intel), помечены в программе как
  **экспериментальные**; пометка снимается, как только кто-то пришлёт результат;
- встроенное обновление сработало;
- релиз чистый на VirusTotal.

Цифровая подпись (SignPath Foundation) — цель, но не условие 1.0: для неё сначала нужна история проекта.

**Нужна помощь:** если у тебя AMD Radeon RX 7000, графика Intel или Windows 10 — запусти **«Тест на 2 мин»** на паре
видео и пришли результат в [Issues](https://github.com/remrem23/framewring/issues). Это очень поможет.

### После 1.0

- **Авто-качество:** подбор уровня сжатия под целевой VMAF (как ab-av1).
- Продолжение прерванного файла с места остановки (сейчас — с начала).
- Явная поддержка HDR.
- Тестирование и сборки для macOS / Linux.
- Меньший размер загрузки (более компактная сборка FFmpeg).

### Известные ограничения

- Проверено в основном на одной машине (Windows 11, RTX 5070 Ti). Отчёты с другого железа очень помогут.
- «Видеокарта AMD · H.265» проверена на реальном железе (графика, встроенная в Ryzen 7 9700X), а «Видеокарта AMD · AV1»
  (Radeon RX 7000, Radeon 780M/880M) и режимы Intel (Quick Sync) на реальном железе ещё не проверялись — их страхует только пробное
  кодирование при запуске, а AMD AV1 / Intel AV1 рекомендуются только после режимов H.265. Если у тебя такая карта,
  напиши в Issues.
- В режимах AMD и Intel видео декодируется на процессоре (в режимах Nvidia — на видеокарте), поэтому процессор нагружен сильнее.
- Оценка экономии в поиске рассчитана на H.265 «Баланс»; точный прогноз даёт «Тест».
- В поиске пропускаются папки с именем `games` (чтобы не трогать установленные игры) — видео в такой папке не найдутся.
- При выключенном файле подкачки возможны сбои памяти (программа повторяет и предупреждает).
- Субтитры-картинки (PGS) в MP4 не помещаются и отбрасываются с предупреждением.
- У программы пока нет цифровой подписи, поэтому SmartScreen предупреждает при первом запуске.
