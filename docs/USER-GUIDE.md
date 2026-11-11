**English** · [Русский](#русский)

# Framewring — user guide

Framewring is a free local video compressor (an FFmpeg front-end). It finds heavy videos on your drives and
re-encodes them several times smaller without visible quality loss. Nothing is uploaded anywhere.

## 1. Install and start

- **Installer** (`Framewring-…-setup.exe`): installs for the current user without admin rights, adds a Start menu shortcut
  (and a desktop one if you tick it). Uninstall via *Settings → Apps*.
- **Portable** (`Framewring-…-portable.zip`): unzip anywhere and run `Framewring.exe`. All data stays in the `data` folder next to it.

On first launch SmartScreen may say *"Windows protected your PC"* (the app is not code-signed yet): click *More info* → *Run anyway*.

The app opens in its own window. If the Microsoft Edge WebView2 Runtime is missing, it opens in your browser instead;
in that case keep the browser tab open while it compresses. Starting the app a second time just brings up the window that is already open.

The interface language follows Windows; change it in the language list in the header (English, Russian, German, French, Spanish, Portuguese and Simplified Chinese).

## 2. Quick start

1. Add videos: **Find heavy videos**, **+ Files**, **+ Folder**, paste a path into the field under the buttons, or drag files and folders onto the app window (drag & drop does not work in the browser fallback).
2. Pick the mode marked **recommended** (your GPU if it is suitable) and quality **Balanced**.
3. Press **Test (2 min)**: you get a forecast of the final size and time and a VMAF quality score.
   To compare with your own eyes, open the original piece and the test result from `compressed\_tests` in full screen.
4. Happy with it — press **Compress all**. Results appear in the `compressed` subfolder next to each original.
5. Originals are **not** deleted. Delete them yourself once you have checked the result.

## 3. Find heavy videos

**Find heavy videos** opens the search panel: tick drives (or type your own folder), choose the minimum file size
(200 MB / 500 MB / 1 GB / 3 GB) and start the search.

- Framewring lists big videos and roughly how much space compressing each one would free. The estimate assumes H.265 *Balanced*;
  the **Test** gives an exact forecast.
- Worthwhile files are ticked automatically (of identical copies — only one). The add-to-queue button puts the ticked files into the list.
- **"copies: N"** means identical files (same name and size) in different places. Delete the extra copies yourself —
  that frees more than any compression.
- Skipped: system folders, installed games (any folder named `games`, Steam/Epic/GOG/… libraries), folders starting with `$` or `.`,
  OneDrive "online-only" files (reading them would download them), and the program's own `compressed` / `_tests` folders.
- Editing codecs (ProRes, DNxHD…) are found but not ticked automatically.
- **Everything** (free, [voidtools.com](https://www.voidtools.com/)) makes the search take seconds. It is optional:
  without it Framewring walks the folders itself (multi-threaded). If Everything is installed but closed, Framewring starts it in the tray
  for the search and closes it afterwards. Network, removable and non-NTFS drives are always scanned by walking folders.
  Untick the Everything option if your Everything does not index all drives.
  After a long search without Everything the app suggests installing it — you can hide that hint.

The search never deletes or changes anything.

## 4. Settings

**Mode** — what encodes the video:

| Mode | When to choose |
|---|---|
| **Nvidia GPU · AV1** | RTX 40/50 series. 5–7× faster than the CPU and smaller than H.265. Best for big archives. Plays on PCs, recent phones and TVs. |
| **Nvidia GPU · H.265** | Fast and plays almost everywhere: older phones and TVs, iPhone. Files are slightly bigger than AV1. |
| **AMD GPU · AV1** | Radeon RX 7000 series or newer. Same idea as Nvidia AV1. Not yet tested on real hardware — please report how it works. |
| **AMD GPU · H.265** | Radeon cards, including the graphics built into Ryzen processors. Plays almost everywhere. |
| **Intel GPU · AV1** | Intel Arc or Core Ultra graphics. Not yet tested on real hardware — please report how it works. |
| **Intel GPU · H.265** | Most Intel graphics since about 2016. Plays almost everywhere. Not yet tested on real hardware — please report how it works. |
| **CPU · H.265** | Files are usually 10–20% smaller than on the GPU, but many times slower (hours per hour of 4K). If you have no suitable GPU or every gigabyte counts. |
| **CPU · AV1** | The smallest files, the slowest mode. Does not play everywhere. |
| **Mac GPU · H.265** | Only on macOS, when run from source. |

On startup every mode is test-encoded; only the working ones can be picked. Modes your hardware or FFmpeg cannot do
are greyed out with the reason; GPU modes for a vendor whose card your PC does not have (for example AMD modes on a PC
with only an Nvidia card) are hidden. The best available one is marked **recommended** and chosen by default
(your own choice is remembered). Order of preference: Nvidia AV1 → AMD AV1 → Intel AV1 → Nvidia H.265 → AMD H.265 →
Intel H.265 → CPU.

**Quality** — **Maximum / Balanced / Compact**. *Balanced* is the right choice for almost everything.
VMAF in the test: 95+ — practically indistinguishable, 92–95 — very good, lower — the difference becomes visible.

**Encoding speed** — the slowest setting gives a slightly smaller file but takes 1.5–2× longer.

**Audio** — copied losslessly by default (it weighs almost nothing). If the audio format does not fit into MP4, it is re-encoded to AAC 192 kbps;
you can also force AAC.

**Output folder** — empty means a `compressed` subfolder next to each original. You can set one common folder instead.

Other options: low priority (you can keep using the computer), keep the computer awake while compressing,
**Skip already compressed files** (if the result already exists).

## 5. Compressing

- **Compress all** queues every file that is not done yet. Files can be added while compression is running.
- **Stop** stops the current file and clears the queue (asks for confirmation if a file is already partly compressed). A stopped file starts from the beginning next time.
- **↻ Retry** next to failed or cancelled files puts that file back into the queue.
- **📂 Compressed** / **📂 Original** show the file in Explorer. **Clear finished** removes completed items from the list.
- The list survives restarts: close the app and everything is still there next time.
- **History** shows everything ever compressed and the total space freed.
- After 100% the app shows a short "finishing the file" stage: FFmpeg rewrites the file so it starts playing instantly.
  On an HDD this takes from seconds to a minute.

## 6. What happens to your files

- Supported input: `.mp4 .mkv .mov .avi .webm .flv .ts .m2ts .m4v .wmv .mts`. Output: `.mp4` (H.265 or AV1, 10-bit).
- Originals are only read, never modified or deleted.
- A result can never replace an original. In the default `compressed` folder the result keeps the original name;
  if the output folder is the source folder, the result gets a `_compressed` suffix; in a common output folder you choose,
  files from elsewhere are never overwritten — a number is added instead.
- A file with the result's name in `compressed` (or with the `_compressed` suffix) is treated as an earlier result of the same video:
  with **Skip already compressed files** on (the default) it is skipped, with the option off it is compressed again and replaced.
- The result is written to `name.part.mp4` and renamed only when complete. If an antivirus or a player holds the file,
  Framewring waits and, if needed, saves under another name — finished work is never lost.
- Kept: audio tracks, text subtitles (picture subtitles such as PGS cannot go into MP4 — you get a warning), the file's modification date.
  Interlaced video is deinterlaced. Variable-frame-rate recordings (phones, OBS) keep their original timing.
- Free space is checked before starting.

## 7. Data and logs

| How you run it | Data folder |
|---|---|
| Installed | `%APPDATA%\Framewring` |
| Portable | `data\` next to `Framewring.exe` |
| From source | next to `app.py` |

Files: `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (the last three contain paths to your videos)
and `framewring.log` (the exe's log — attach it to bug reports, removing paths you don't want to share).
Uninstalling keeps this folder; delete it by hand if you want.

## 8. Troubleshooting

- **A GPU mode is greyed out.** Update the driver for your GPU vendor: Nvidia, AMD (AMD Software / Adrenalin)
  or Intel. AV1 on the GPU needs an Nvidia RTX 40 or 50 series card, an AMD Radeon RX 7000 series card or newer,
  or Intel Arc / Core Ultra graphics. The reason is shown next to the greyed-out mode.
- **"Access denied" when writing to Documents / Videos / Desktop.** Windows *Controlled folder access* is blocking it:
  *Windows Security → Virus & threat protection → Ransomware protection → Allow an app through Controlled folder access*, add
  `Framewring.exe` and `ffmpeg.exe` from the program's `ffmpeg\bin` folder.
- **Memory errors / "page file is off" warning.** With the Windows page file disabled the encoder can run out of memory.
  Framewring retries automatically, but turning the page file back on is the real fix.
- **"Not enough free space".** Free some space on the output drive or choose another output folder.
- **The window does not open.** Install the [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
  or use the browser that opens instead.
- **Use your own FFmpeg.** Replace `ffmpeg.exe` and `ffprobe.exe` in the program's `ffmpeg\bin` folder.

Questions and bug reports: [github.com/remrem23/framewring/issues](https://github.com/remrem23/framewring/issues).
The only official page of the program is [github.com/remrem23/framewring](https://github.com/remrem23/framewring).

---

<a id="русский"></a>
## Русский

**Framewring Жмых — инструкция.**
Framewring Жмых — бесплатный локальный компрессор видео (обёртка над FFmpeg). Находит на дисках тяжёлые видео и пережимает
их в разы меньше без видимой потери качества. Ничего никуда не отправляется.

### 1. Установка и запуск

- **Установщик** (`Framewring-…-setup.exe`): ставится для текущего пользователя без прав администратора, добавляет ярлык в «Пуск»
  (и на рабочий стол, если отметить). Удаление — «Параметры → Приложения».
- **Портабл** (`Framewring-…-portable.zip`): распакуй куда угодно и запусти `Framewring.exe`. Все данные — в папке `data` рядом.

При первом запуске SmartScreen может написать «Windows защитила ваш компьютер» (у программы пока нет цифровой подписи):
«Подробнее» → «Выполнить в любом случае».

Программа открывается в своём окне. Если нет Microsoft Edge WebView2 Runtime, интерфейс откроется в браузере;
тогда не закрывай вкладку, пока идёт сжатие. Повторный запуск просто показывает уже открытое окно.

Язык интерфейса — как в Windows; поменять можно в списке языков в шапке (русский, английский, немецкий, французский, испанский, португальский и китайский (упрощённый)).

### 2. Быстрый старт

1. Добавь видео: «Найти тяжёлые видео», «+ Файлы», «+ Папка», вставь путь в поле под кнопками или перетащи файлы и папки в окно программы (в режиме браузера перетаскивание не работает).
2. Выбери режим с пометкой **«рекомендую»** (видеокарта, если подходит) и качество **«Баланс»**.
3. Нажми **«Тест на 2 мин»**: увидишь прогноз итогового размера и времени и оценку качества VMAF.
   Чтобы сравнить глазами, открой кусок оригинала и результат теста из папки `compressed\_tests` на полном экране.
4. Устраивает — **«Сжать всё»**. Результат — в подпапке `compressed` рядом с каждым оригиналом.
5. Оригиналы **не** удаляются. Удаляй сам, когда проверишь результат.

### 3. Найти тяжёлые видео

Кнопка «Найти тяжёлые видео» открывает панель поиска: отметь диски (или впиши свою папку), выбери минимальный размер
(200 МБ / 500 МБ / 1 ГБ / 3 ГБ) и нажми «Искать».

- Framewring покажет большие видео и примерно сколько места освободит сжатие каждого. Оценка рассчитана на H.265 «Баланс»;
  точный прогноз даёт «Тест».
- Выгодные файлы отмечаются сами (из одинаковых копий — только одна). «Добавить в очередь» ставит отмеченные в список.
- Метка **«копий: N»** — одинаковые файлы (то же имя и размер) в разных местах. Лишние копии удали сам —
  это освобождает больше любого сжатия.
- Пропускаются: системные папки, установленные игры (любая папка `games`, библиотеки Steam/Epic/GOG/…), папки на `$` и `.`,
  файлы OneDrive «только в облаке» (чтение скачало бы их) и собственные папки `compressed` / `_tests`.
- Монтажные кодеки (ProRes, DNxHD…) находятся, но не отмечаются автоматически.
- **Everything** (бесплатный, [voidtools.com](https://www.voidtools.com/)) сокращает поиск до секунд. Он не обязателен:
  без него Framewring сам обходит папки в несколько потоков. Если Everything установлен, но закрыт, Framewring запустит его в трей
  на время поиска и потом закроет. Сетевые, съёмные и не-NTFS диски всегда обходятся по папкам.
  Сними галочку «через Everything», если твой Everything индексирует не все диски.
  После долгого поиска без Everything программа подскажет его установить — подсказку можно скрыть.

Поиск ничего не удаляет и не меняет.

### 4. Настройки

**Режим** — чем кодировать видео:

| Режим | Когда выбирать |
|---|---|
| **Видеокарта Nvidia · AV1** | RTX 40xx/50xx. В 5–7 раз быстрее процессора и компактнее H.265. Лучший выбор для больших архивов. Играется на ПК, новых телефонах и ТВ. |
| **Видеокарта Nvidia · H.265** | Быстро и открывается почти везде: старые телефоны и ТВ, iPhone. Файл немного больше, чем у AV1. |
| **Видеокарта AMD · AV1** | Radeon RX 7000 и новее. То же, что AV1 на Nvidia. На реальном железе ещё не проверялся — напиши, как работает. |
| **Видеокарта AMD · H.265** | Карты Radeon, в том числе графика, встроенная в процессоры Ryzen. Открывается почти везде. |
| **Видеокарта Intel · AV1** | Графика Intel Arc или Core Ultra. На реальном железе ещё не проверялся — напиши, как работает. |
| **Видеокарта Intel · H.265** | Большинство графики Intel примерно с 2016 года. Открывается почти везде. На реальном железе ещё не проверялся — напиши, как работает. |
| **Процессор · H.265** | Файл обычно на 10–20% меньше, чем у видеокарты, но в разы медленнее (часы на час видео в 4K). Если подходящей видеокарты нет или важен каждый гигабайт. |
| **Процессор · AV1** | Самый маленький файл, самый медленный режим. Открывается не везде. |
| **Видеокарта Mac · H.265** | Только на macOS при запуске из исходников. |

При запуске каждый режим проверяется пробным кодированием; выбрать можно только работающие. Режимы, которые не умеет
твоё железо или FFmpeg, серые, с причиной; режимы видеокарт производителя, которого в компьютере нет (например, режимы
AMD на компьютере только с Nvidia), скрыты. Лучший доступный помечен **«рекомендую»** и выбран по умолчанию
(твой собственный выбор запоминается). Порядок предпочтения: Nvidia AV1 → AMD AV1 → Intel AV1 → Nvidia H.265 →
AMD H.265 → Intel H.265 → процессор.

**Качество** — **Максимальное / Баланс / Компактное**. «Баланс» подходит почти всегда.
VMAF в тесте: 95+ — разницу практически не отличить, 92–95 — очень хорошо, ниже — уже видно.

**Скорость кодирования** — «Тщательно» даёт чуть меньший файл, но занимает в 1,5–2 раза больше времени.

**Звук** — по умолчанию копируется без потерь (почти ничего не весит). Если формат звука не помещается в MP4, он пережимается
в AAC 192 кбит/с; можно и принудительно выбрать AAC.

**Куда сохранять** — пусто = подпапка `compressed` рядом с каждым оригиналом. Можно указать одну общую папку.

Прочее: низкий приоритет (компьютером можно пользоваться), не давать компьютеру уснуть,
**«Пропускать уже сжатые файлы»** (если результат уже есть).

### 5. Сжатие

- **«Сжать всё»** ставит в очередь все ещё не сжатые файлы. Добавлять файлы можно и во время сжатия.
- **«Стоп»** останавливает текущий файл и очищает очередь (спрашивает подтверждение, если файл уже частично сжат). Остановленный файл в следующий раз начнётся с начала.
- **«↻ Повторить»** у неудачных и отменённых файлов ставит файл в очередь заново.
- **«📂 Сжатый»** / **«📂 Оригинал»** показывают файл в проводнике. «Убрать готовые из списка» убирает завершённые.
- Список переживает перезапуск: закрыл программу — в следующий раз всё на месте.
- **«История»** — всё, что когда-либо сжато, и сколько места освобождено.
- После 100% идёт короткий этап «Дописываю файл»: FFmpeg переписывает файл, чтобы он сразу начинал играть.
  На HDD это от секунд до минуты.

### 6. Что происходит с файлами

- Поддерживаются: `.mp4 .mkv .mov .avi .webm .flv .ts .m2ts .m4v .wmv .mts`. Результат: `.mp4` (H.265 или AV1, 10 бит).
- Оригиналы только читаются: не изменяются и не удаляются.
- Результат никогда не может заменить оригинал. В папке `compressed` результат получает имя оригинала;
  если папка вывода — это папка оригинала, к имени добавляется `_compressed`; в общей папке вывода, которую ты указал,
  чужие файлы не перезаписываются — к имени добавляется номер.
- Файл с именем результата в `compressed` (или с суффиксом `_compressed`) считается прошлым результатом того же видео:
  при включённом «Пропускать уже сжатые файлы» (по умолчанию) он пропускается, при выключенном — сжимается заново и заменяется.
- Результат пишется в `имя.part.mp4` и переименовывается только целым. Если файл держит антивирус или плеер,
  Framewring ждёт и при необходимости сохраняет под другим именем — готовая работа не теряется.
- Сохраняются: звуковые дорожки, текстовые субтитры (субтитры-картинки, например PGS, в MP4 не помещаются — будет предупреждение),
  дата изменения файла. Черезстрочное видео деинтерлейсится. Видео с переменной частотой кадров (телефоны, OBS) сохраняет исходный тайминг.
- Перед стартом проверяется свободное место.

### 7. Данные и журнал

| Как запущено | Папка данных |
|---|---|
| Установлено | `%APPDATA%\Framewring` |
| Портабл | `data\` рядом с `Framewring.exe` |
| Из исходников | рядом с `app.py` |

Файлы: `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (в трёх последних — пути к твоим видео)
и `framewring.log` (журнал exe-версии — приложи его к сообщению об ошибке, убрав пути, которыми не хочешь делиться).
При удалении программы папка сохраняется; удали её вручную, если нужно.

### 8. Если что-то не так

- **Режим видеокарты серый.** Обнови драйвер своей видеокарты: Nvidia, AMD (AMD Software / Adrenalin) или Intel.
  AV1 на видеокарте требует Nvidia RTX 40xx/50xx, AMD Radeon RX 7000 и новее или графику Intel Arc / Core Ultra.
  Причина показана рядом с серым режимом.
- **«Отказано в доступе» при записи в «Документы» / «Видео» / на рабочий стол.** Мешает «Контролируемый доступ к папкам»:
  «Безопасность Windows → Защита от вирусов и угроз → Защита от программ-шантажистов → Разрешить работу приложения через
  контролируемый доступ к папкам», добавь `Framewring.exe` и `ffmpeg.exe` из папки `ffmpeg\bin` программы.
- **Сбои памяти / предупреждение «файл подкачки выключен».** Без файла подкачки кодеру может не хватить памяти.
  Framewring повторяет сам, но надёжнее включить файл подкачки.
- **«Мало свободного места».** Освободи место на диске вывода или выбери другую папку.
- **Окно не открывается.** Установи [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
  или пользуйся браузером, который откроется вместо окна.
- **Свой FFmpeg.** Замени `ffmpeg.exe` и `ffprobe.exe` в папке `ffmpeg\bin` программы.

Вопросы и ошибки: [github.com/remrem23/framewring/issues](https://github.com/remrem23/framewring/issues).
Официальная страница программы — только [github.com/remrem23/framewring](https://github.com/remrem23/framewring).
