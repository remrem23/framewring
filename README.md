**English** · [Русский](#русский)

# Framewring — free local video compressor

**Finds videos that waste space on your drives and shrinks them several times over with no visible loss of quality.**
Free, local, no limits: your files never leave your computer.

Framewring is a Windows app built on top of FFmpeg. It finds heavy videos on all your drives,
estimates how much space each one would free, lets you test the result on a short piece, and re-encodes on an
Nvidia GPU (NVENC AV1 / H.265) or on the CPU (x265, SVT-AV1). The interface is in English and Russian
(switch **RU | EN** in the header; the default follows your Windows language).

<!-- TODO: screenshots of the main window, "Find heavy videos" and a test result with VMAF -->

## Download

Get the latest version from [Releases](https://github.com/remrem23/framewring/releases/latest):

- **`Framewring-…-setup.exe`** — installer. Installs for the current user without admin rights
  (into `%LOCALAPPDATA%\Programs\Framewring`), uninstall via *Settings → Apps*.
- **`Framewring-…-portable.zip`** — portable version: unzip anywhere and run `Framewring.exe`.
  Settings and history are kept in the `data` folder next to it.

FFmpeg is included, nothing else to install.

> **"Windows protected your PC".** The app has no paid code-signing certificate yet, so SmartScreen warns on first launch.
> Click *More info* → *Run anyway*. To make sure the file was not tampered with, compare it with `SHA256SUMS.txt`
> from the release (in PowerShell: `Get-FileHash Framewring-…-setup.exe`).

**The only official page of the program is [github.com/remrem23/framewring](https://github.com/remrem23/framewring).**
Copies from other sites may be modified.

## Requirements

- **Windows 10 or 11, 64-bit.**
- **Microsoft Edge WebView2 Runtime** for the app window. Windows 11 already has it, Windows 10 usually does too.
  If it is missing, Framewring opens its interface in your default browser instead and tells you so.
- **GPU modes need an Nvidia card and an up-to-date driver:** *Nvidia GPU · AV1* needs an RTX 40 or 50 series card,
  *Nvidia GPU · H.265* works on most GeForce GTX 10 series and newer. Framewring test-encodes on startup and greys out
  modes your hardware cannot do. Without a suitable Nvidia card the CPU modes (x265, SVT-AV1) are used —
  they work everywhere, just slower. AMD and Intel GPU encoding is not supported yet.

## Features

- **Find heavy videos** on all drives: how much space compressing each file would free, duplicate detection,
  checkboxes to choose what to queue. With the free [Everything](https://www.voidtools.com/) installed the search takes seconds;
  without it a multi-threaded folder scan is used automatically.
- **GPU compression** (Nvidia AV1 / H.265) — 5–7× faster than the CPU — or **CPU compression** (x265, SVT-AV1) when every gigabyte counts.
- **Test on a piece of the video:** predicted final size, time and VMAF quality score before the full run.
- **A queue that survives restarts**, a *↻ Retry* button for failed files, **history** of everything compressed with the total space freed.
- **Drag & drop** files and folders onto the app window to add them.
- **Safe for your files:** originals are never modified or deleted, other files are never overwritten,
  the result is written to a temporary file and appears only when complete. Audio, text subtitles and the file date are kept;
  interlaced video is deinterlaced; variable-frame-rate recordings keep their timing.
- **Reliable:** free-space check, automatic retry on memory errors, works even if an antivirus or a player holds the file.

Example from the author's machine: a 3440×1440 screen recording, **76.6 GB → 7.3 GB (−90%)**; 93 GB freed on the first evening.

## How to use

1. **Find heavy videos** — or **+ Files** / **+ Folder**, or drag files onto the window.
2. **Test (2 min)** — see the predicted size and quality.
3. **Compress all.** Results go to a `compressed` subfolder next to each original (you can change the **Output folder**).

Full guide: [docs/USER-GUIDE.md](docs/USER-GUIDE.md) (also shipped with the app as `README.txt`).

## Where settings and logs are stored

| How you run it | Data folder |
|---|---|
| Installed (setup.exe) | `%APPDATA%\Framewring` |
| Portable (zip) | `data\` next to `Framewring.exe` |
| From source | next to `app.py` |

The folder holds `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (the last three contain paths to your videos —
they never leave your computer) and, for the exe, `framewring.log`. Uninstalling keeps this folder so history is not lost;
delete it by hand if you want a clean slate.

## FAQ

**Windows says "Windows protected your PC".** See *Download* above: *More info* → *Run anyway*, and check the SHA-256 if in doubt.

**Compression fails with "access denied" / "permission denied" in Documents, Videos or Desktop.**
That is probably Windows *Controlled folder access* (ransomware protection). Open *Windows Security → Virus & threat protection →
Ransomware protection → Allow an app through Controlled folder access* and add `Framewring.exe` and `ffmpeg.exe` from the
program's `ffmpeg\bin` folder (installed: `%LOCALAPPDATA%\Programs\Framewring\ffmpeg\bin\ffmpeg.exe`).

**Do I need Everything?** No. It only makes the search faster (seconds instead of minutes). Without it Framewring scans folders itself.
If Everything is installed but not running, Framewring starts it in the tray for the search and closes it afterwards.

**Will it touch my original files?** No. Originals are only read, and a result can never replace an original.
If the output folder is the source folder, the result gets a `_compressed` suffix; in a common output folder you choose,
existing files from elsewhere are never overwritten (a number is added). Deleting originals is up to you, after you check the result.

**What about variable frame rate (phones, OBS, screen recorders)?** Frames are passed through with their original timestamps —
nothing is dropped or duplicated, and the test VMAF compares the right frames.

**Is anything sent to the internet?** No. See *Privacy* below.

**Where do I report a bug?** [Issues](https://github.com/remrem23/framewring/issues) — please attach `framewring.log` from the data folder.

## Running from source

You need Python 3.8+ and FFmpeg with `libx265` / `libsvtav1` / `libvmaf`
(for example the [Gyan](https://www.gyan.dev/ffmpeg/builds/) build) in `PATH` or in an `ffmpeg/` folder next to `app.py`.
The app itself uses only the standard library; [pywebview](https://pywebview.flowrl.com/) is optional —
with it the app opens in its own window, without it in the browser.

- Windows: `START-Windows.bat` (installs Python and FFmpeg via `winget` if missing).
- Mac: `START-Mac.command`, Linux: `./start-linux.sh` — barely tested so far.

Building the exe, installer and portable zip: [packaging/](packaging/) (`build.py`, then `release.py`).

## Privacy

Everything runs on your computer: the interface is a local server on `127.0.0.1`, protected by a random token.
Nothing is sent over the network: no analytics, no telemetry, no background update checks.
The app opens a web page only when you click a link (this repository, the support page, voidtools.com).

## Support the author

Framewring is free. If it saved you disk space and time — see the [support page](DONATE.md).

## Documentation

- [docs/USER-GUIDE.md](docs/USER-GUIDE.md) — user guide.
- [CHANGELOG.md](CHANGELOG.md) — what changed in each version.
- [DEVLOG.md](DEVLOG.md) — development history, measurements and decisions.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the program works, API, data files.
- [ROADMAP.md](ROADMAP.md) — plans and known limitations.
- [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## License

[GNU GPL v3](LICENSE). You may freely use, study and modify the program; modified versions may be distributed
only with source code, under the same license, and with authorship preserved.

The builds include [FFmpeg](https://ffmpeg.org) (Gyan build, GPL v3) and other components listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md); their license texts are shipped in the program's `licenses` and `ffmpeg` folders.
[Everything](https://www.voidtools.com/) is a separate third-party program and is not included.

---

<a id="русский"></a>
## Русский

**Framewring Жмых — локальный компрессор видео.**
**Находит на дисках видео, которые зря занимают место, и ужимает их в разы без видимой потери качества.**
Бесплатно, локально, без лимитов: файлы никуда не отправляются.

Framewring Жмых (английское название — *Framewring*) — программа для Windows, обёртка над FFmpeg. Находит тяжёлые видео
на всех дисках, оценивает, сколько места освободит каждое, позволяет проверить результат на коротком куске и пережимает
на видеокарте Nvidia (NVENC AV1 / H.265) или на процессоре (x265, SVT-AV1). Интерфейс на русском и английском
(переключатель **RU | EN** в шапке; по умолчанию — язык Windows).

### Скачать

Последняя версия — на странице [Releases](https://github.com/remrem23/framewring/releases/latest):

- **`Framewring-…-setup.exe`** — установщик. Ставится для текущего пользователя без прав администратора
  (в `%LOCALAPPDATA%\Programs\Framewring`), удаляется через «Параметры → Приложения».
- **`Framewring-…-portable.zip`** — портабл-версия: распакуй куда угодно и запусти `Framewring.exe`.
  Настройки и история хранятся в папке `data` рядом.

FFmpeg уже внутри, ничего доустанавливать не нужно.

> **«Windows защитила ваш компьютер».** У программы пока нет платной цифровой подписи, поэтому SmartScreen
> предупреждает при первом запуске. Нажми «Подробнее» → «Выполнить в любом случае».
> Проверить, что файл не подменён, можно по контрольным суммам из `SHA256SUMS.txt` в релизе
> (в PowerShell: `Get-FileHash Framewring-…-setup.exe`).

**Официальная страница программы — только [github.com/remrem23/framewring](https://github.com/remrem23/framewring).**
Копии с других сайтов могут быть изменены.

### Требования

- **Windows 10 или 11, 64 бит.**
- **Microsoft Edge WebView2 Runtime** — для окна программы. В Windows 11 он уже есть, в Windows 10 обычно тоже.
  Если его нет, Framewring откроет интерфейс в браузере по умолчанию и скажет об этом.
- **Для режимов на видеокарте нужна карта Nvidia и свежий драйвер:** «Видеокарта Nvidia · AV1» — RTX 40xx/50xx,
  «Видеокарта Nvidia · H.265» — большинство карт начиная с GeForce GTX 10xx. При запуске Framewring делает пробное кодирование
  и делает недоступные режимы серыми. Без подходящей карты Nvidia работают режимы на процессоре (x265, SVT-AV1) —
  везде, просто медленнее. Видеокарты AMD и Intel пока не поддерживаются.

### Что умеет

- **Поиск тяжёлых видео** на всех дисках: сколько места освободит сжатие каждого файла, пометка дублей, выбор галочками.
  Если установлен бесплатный [Everything](https://www.voidtools.com/), поиск занимает секунды; без него автоматически работает многопоточный обход папок.
- **Сжатие на видеокарте** (Nvidia AV1 / H.265) — в 5–7 раз быстрее процессора — или **на процессоре** (x265, SVT-AV1), когда важен каждый гигабайт.
- **Тест на куске видео:** прогноз итогового размера, времени и оценка качества VMAF до полного сжатия.
- **Очередь, которая переживает перезапуск**, кнопка «↻ Повторить» у неудачных файлов, **история** всего сжатого с итогом освобождённого места.
- **Перетаскивание** файлов и папок прямо в окно программы.
- **Бережно к файлам:** оригиналы не изменяются и не удаляются, чужие файлы не перезаписываются,
  результат пишется во временный файл и появляется только целым. Сохраняются звук, текстовые субтитры и дата файла;
  черезстрочное видео деинтерлейсится; у видео с переменной частотой кадров сохраняется исходный тайминг.
- **Надёжность:** проверка свободного места, повтор при сбоях памяти, корректная работа, если файл держит антивирус или плеер.

Пример с машины автора: запись экрана 3440×1440 — **76,6 ГБ → 7,3 ГБ (−90%)**; за первый вечер освобождено 93 ГБ.

### Как пользоваться

1. «Найти тяжёлые видео» — или «+ Файлы» / «+ Папка», или перетащи файлы в окно.
2. «Тест на 2 мин» — посмотреть прогноз размера и качество.
3. «Сжать всё». Результат — в подпапке `compressed` рядом с оригиналом (папку можно поменять в «Куда сохранять»).

Подробная инструкция — [docs/USER-GUIDE.md](docs/USER-GUIDE.md#русский) (в программе — файл `README.txt`).

### Где хранятся настройки и журнал

| Как запущено | Папка данных |
|---|---|
| Установлено (setup.exe) | `%APPDATA%\Framewring` |
| Портабл (zip) | `data\` рядом с `Framewring.exe` |
| Из исходников | рядом с `app.py` |

В папке лежат `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (в трёх последних — пути к твоим видео,
они никуда не отправляются) и у exe-версии — журнал `framewring.log`. При удалении программы папка сохраняется, чтобы
не потерять историю; удали её вручную, если нужно начать с чистого листа.

### Частые вопросы

**«Windows защитила ваш компьютер».** См. «Скачать» выше: «Подробнее» → «Выполнить в любом случае»; при сомнениях сверь SHA-256.

**Сжатие падает с «отказано в доступе» в «Документах», «Видео» или на рабочем столе.**
Скорее всего, это «Контролируемый доступ к папкам» (защита от программ-вымогателей). Открой «Безопасность Windows →
Защита от вирусов и угроз → Защита от программ-шантажистов → Разрешить работу приложения через контролируемый доступ к папкам»
и добавь `Framewring.exe` и `ffmpeg.exe` из папки `ffmpeg\bin` программы
(у установленной: `%LOCALAPPDATA%\Programs\Framewring\ffmpeg\bin\ffmpeg.exe`).

**Обязателен ли Everything?** Нет, он только ускоряет поиск (секунды вместо минут). Без него Framewring обходит папки сам.
Если Everything установлен, но закрыт, Framewring запустит его в трей на время поиска и потом закроет.

**Тронет ли программа оригиналы?** Нет, оригиналы только читаются, и результат никогда не может заменить оригинал.
Если папка вывода совпадает с папкой оригинала, к имени добавляется `_compressed`; в общей папке вывода, которую ты указал,
чужие файлы не перезаписываются (к имени добавляется номер). Удалять оригиналы — тебе, после проверки результата.

**Видео с переменной частотой кадров (телефоны, OBS, запись экрана)?** Кадры передаются с исходными метками времени —
ничего не выбрасывается и не дублируется, а VMAF в тесте сравнивает правильные кадры.

**Отправляется ли что-то в интернет?** Нет, см. «Приватность».

**Куда писать об ошибке?** В [Issues](https://github.com/remrem23/framewring/issues) — приложи `framewring.log` из папки данных.

### Запуск из исходников

Нужны Python 3.8+ и FFmpeg с `libx265` / `libsvtav1` / `libvmaf`
(например, сборка [Gyan](https://www.gyan.dev/ffmpeg/builds/)) в `PATH` или в папке `ffmpeg/` рядом с `app.py`.
Сама программа использует только стандартную библиотеку; [pywebview](https://pywebview.flowrl.com/) — по желанию:
с ним открывается своё окно, без него — браузер.

- Windows: `START-Windows.bat` (поставит Python и FFmpeg через `winget`, если их нет).
- Mac: `START-Mac.command`, Linux: `./start-linux.sh` — пока почти не тестировалось.

Сборка exe, установщика и портабл-архива — в [packaging/](packaging/) (`build.py`, затем `release.py`).

### Приватность

Программа работает только на твоём компьютере: интерфейс — локальный сервер на `127.0.0.1`, защищённый случайным токеном.
Ничего не отправляется в сеть: нет аналитики, телеметрии и проверки обновлений в фоне.
Веб-страницу программа открывает, только когда ты нажимаешь ссылку (этот репозиторий, страница поддержки, voidtools.com).

### Поддержать автора

Framewring бесплатный. Если он сэкономил тебе место и время — [страница поддержки](DONATE.md#русский).

### Документация

- [docs/USER-GUIDE.md](docs/USER-GUIDE.md#русский) — инструкция.
- [CHANGELOG.md](CHANGELOG.md) — что изменилось в версиях.
- [DEVLOG.md](DEVLOG.md#русский) — история разработки, замеры и решения.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#русский) — устройство программы, API, файлы данных.
- [ROADMAP.md](ROADMAP.md#русский) — планы и известные ограничения.
- [CONTRIBUTING.md](CONTRIBUTING.md#русский), [SECURITY.md](SECURITY.md#русский), [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md#русский).

### Лицензия

[GNU GPL v3](LICENSE). Можно свободно пользоваться, изучать и изменять; распространять изменённые версии —
только с открытым исходным кодом, под той же лицензией и с сохранением указания авторства.

В сборки входят [FFmpeg](https://ffmpeg.org) (сборка Gyan, GPL v3) и другие компоненты из
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md#русский); тексты их лицензий лежат в папках `licenses` и `ffmpeg` программы.
[Everything](https://www.voidtools.com/) — сторонняя программа, в состав не входит.
