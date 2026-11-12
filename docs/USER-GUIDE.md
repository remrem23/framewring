**English** · [Русский](#русский)

# Framewring — user guide

Framewring is a free local video compressor (an FFmpeg front-end). It finds heavy videos on your drives and
re-encodes them several times smaller without visible quality loss. Your files never leave your computer.

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
5. Originals are **not** touched by compression. Once you have checked the result, you can put the compressed files
   in their place with **⇄ Replace originals…** — the originals go to the Windows Recycle Bin (see section 7).

On first run a short **How it works** hint with these steps is shown above the list; **Got it** hides it for good.

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
| **AMD GPU · AV1** | Radeon RX 7000 or newer, and Ryzen 7040/8040-series graphics (Radeon 780M/880M). Same idea as Nvidia AV1. Not yet tested on real hardware — please report how it works. |
| **AMD GPU · H.265** | Radeon RX 400 series or newer, including Ryzen integrated graphics. Plays almost everywhere. Tested on real hardware (Ryzen 7 9700X graphics). |
| **Intel GPU · AV1** | Intel Arc or Core Ultra graphics. Not yet tested on real hardware — please report how it works. |
| **Intel GPU · H.265** | Most Intel graphics since about 2016. Plays almost everywhere. Not yet tested on real hardware — please report how it works. |
| **CPU · H.265** | Files are usually 10–20% smaller than on the GPU, but many times slower (hours per hour of 4K). If you have no suitable GPU or every gigabyte counts. |
| **CPU · AV1** | The smallest files, the slowest mode. Does not play everywhere. |
| **Mac GPU · H.265** | Only on macOS, when run from source. |

On startup every mode is test-encoded; only the working ones can be picked. Modes your hardware or FFmpeg cannot do
are greyed out with the reason; GPU modes for a vendor whose card your PC does not have (for example AMD modes on a PC
with only an Nvidia card) are hidden. The best available one is marked **recommended** and chosen by default
(your own choice is remembered). Order of preference: Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 → AMD AV1 →
Intel AV1 → CPU. AMD AV1 and Intel AV1 stay below H.265 until they are verified on real hardware.

**Quality** — **Maximum / Balanced / Compact**. *Balanced* is the right choice for almost everything.
VMAF in the test: 95+ — practically indistinguishable, 92–95 — very good, lower — the difference becomes visible.

**Encoding speed** — **Thorough** gives a slightly smaller file but takes 1.5–2× longer.
For **CPU · AV1** it uses SVT-AV1 preset 4: on a 1080p test the file was ~16% smaller than with **Normal** at ~1.7× the time.

**Audio** — copied losslessly by default (it weighs almost nothing). If the audio format does not fit into MP4, it is re-encoded to AAC 192 kbps;
you can also force AAC.

**Output folder** — empty means a `compressed` subfolder next to each original. You can set one common folder instead.

Other options: low priority (you can keep using the computer), keep the computer awake while compressing,
**Skip already compressed files** (if the result already exists), **Check for updates on startup** (see below).

**Updates.** Once per launch Framewring asks GitHub (`api.github.com`) for the number of the newest version — that is the
only network request it makes, and nothing about your files is sent. Turn it off with **Check for updates on startup**.
If a newer version exists, a bar appears: *"Framewring X is available."* with **Update**, **What's new** and **Later**.
In the installed version **Update** downloads the new installer from the GitHub release, verifies its SHA-256 against
`SHA256SUMS.txt` of the same release, installs it over the old one and restarts the app; settings, the queue and history
are kept (if compression is running, it asks first). The portable version and the source version show **Download**
instead, which opens the release page.

## 5. Compressing

- **Compress all** queues every file that is not done yet. Files can be added while compression is running.
- **Stop** stops the current file and clears the queue (asks for confirmation if a file is already partly compressed). A stopped file starts from the beginning next time.
- **↻ Retry** next to failed or cancelled files puts that file back into the queue.
- **📂 Compressed** / **📂 Original** show the file in Explorer. **Clear finished** removes completed items from the list.
- The list survives restarts: close the app and everything is still there next time.
- If compression can't make a file smaller, the video is marked **Kept as is** — no result bigger than the original is
  ever left behind. While compressing, Framewring compares the output size with the bytes of the original that FFmpeg has
  already read (the same part of the video), so a video with a complex beginning and a static rest isn't stopped by mistake.
  It stops early when the output is at least 110% of what was read after at least 10% of the file is read, or at least 102%
  after at least 30%; where these read counters aren't available (outside Windows), it stops only when the output already
  reaches 97% of the original. A finished result that is not at least 3% smaller is deleted. The original is untouched;
  **↻ Retry** (e.g. with **Compact**) stays available.
- **⇄ Replace original** on a finished file and **⇄ Replace originals…** under the list — see section 7.
- **History** shows everything ever compressed and the total space freed. **Export…** saves it to
  `Documents\Framewring-history-YYYY-MM-DD_HH-MM-SS.json` (the real *Documents* folder, also when it is moved to OneDrive;
  earlier exports are never overwritten) and shows the file in Explorer; **Import…** adds entries from such a file
  (for example from another PC or after a reinstall), skipping the ones already there. Imported entries can't be used to replace originals (section 7) — compress the file again to replace it.
- After 100% the app shows a short "finishing the file" stage: FFmpeg rewrites the file so it starts playing instantly.
  On an HDD this takes from seconds to a minute.

## 6. What happens to your files

- Supported input: `.mp4 .mkv .mov .avi .webm .flv .ts .m2ts .m4v .wmv .mts`. Output: `.mp4` (H.265 or AV1, 10-bit).
- Compression only reads originals, it never modifies or deletes them. An original leaves its place only when you choose
  **⇄ Replace originals…**, which sends it to the Windows Recycle Bin (section 7).
- A result is never written over an original. In the default `compressed` folder the result keeps the original name;
  if the output folder is the source folder, the result gets a `_compressed` suffix; in a common output folder you choose,
  files from elsewhere are never overwritten — a number is added instead.
- A file with the result's name in `compressed` (or with the `_compressed` suffix) is treated as an earlier result of the same video:
  with **Skip already compressed files** on (the default) it is skipped, with the option off it is compressed again and replaced.
- The result is written to `name.part.mp4` and renamed only when complete. If an antivirus or a player holds the file,
  Framewring waits and, if needed, saves under another name — finished work is never lost.
- Kept: audio tracks, text subtitles (picture subtitles such as PGS cannot go into MP4 — you get a warning), the file's modification date.
  Interlaced video is deinterlaced. Variable-frame-rate recordings (phones, OBS) keep their original timing.
- Free space is checked before starting.

## 7. Replacing originals

Compressing alone frees no space — the original is still there. When you are happy with the result, **Replace originals**
puts the compressed file in the original's place and moves the original to the Windows Recycle Bin.

**How to start.** **⇄ Replace originals…** under the list opens the window with nothing ticked. **⇄ Replace original** on a
finished file opens the same window with that file highlighted; it is ticked only if it has no warnings (and can be
replaced). The window, *Replace originals with compressed files*, lists everything from **History** (so it works after
**Clear finished** and after a restart), one line per original, with the compressed file's path, sizes before → after and
the saving.

**Only what you tick.** Nothing is ticked by default. **Tick those without warnings** ticks only the files that have no
warnings and no blocks; **Untick all** clears the selection. The bottom line shows how many files are selected and how much
space they free; the button says **Replace (N)**. If any ticked file has warnings, Framewring lists those files and asks
for confirmation before starting.

**Checksum.** Right after compression Framewring computes a SHA-256 checksum of the compressed file (the stage is shown as
*Computing the checksum*) and records it in History. It is used to make sure the file you replace with is byte for byte the
file that was compressed.

**What happens to each ticked file**, one after another:

1. **The checksum is checked again:** if even one byte of the compressed file has changed since compression, the file is
   not replaced.
2. **Full check of the compressed file:** its duration must match the original's (tolerance: 0.1% of the length, at least
   1 s and at most 3 s) and so must the number of audio tracks; the video track is decoded completely, without a single
   error, and must reach the original's duration (so a video cut short is caught even if the audio is full length); the
   audio is decoded separately, also without errors, and must be as long as the original's audio. Progress is shown as
   *checking the compressed file… N%*.
3. **Everything is checked again right before moving** (the check may take a while): the original's and the compressed file's
   size and date must be the same as recorded at compression, and none of the blocks below may have appeared.
4. Framewring writes into History what it is about to do — so an interrupted replacement can be sorted out later.
5. The compressed file is moved next to the original under a temporary name (`name.framewring-new.mp4`); a move never
   overwrites anything. From another drive it is copied and the copy is compared with the compressed file byte by byte.
6. **The original goes to the Windows Recycle Bin** — you can restore it from there. This is checked beforehand (Recycle Bin
   present, turned on, enough free space, path not too long), and once more right before this step; if Windows would still
   delete the file permanently, it asks first.
7. Framewring confirms that the original is really in the Recycle Bin (it reads the bin's own records) and warns you if it
   isn't.
8. The new file takes the original's name with `.mp4`: `video.mp4` stays `video.mp4`; for `video.mkv` a `video.mp4` appears
   in the same folder (this rename too never overwrites an existing file). If the compressed file was in a folder named
   `compressed` and that folder is now empty, it is removed; an output folder you chose yourself is never removed.

**Result of each file** (shown in its row):

- *✓ replaced, the original is in the Recycle Bin* — done;
- *⚠ …* — the original is in the Recycle Bin, but something after that needs your attention: it was not found in the
  Recycle Bin, or the new file kept its temporary name (the message says where it is);
- *not replaced: …* — an error; the original was not replaced.

If anything fails before the Recycle Bin step, **nothing changes**: the original stays, and the compressed file goes back where
it was. A problem with one file does not stop the others. While it runs, don't move or open these files; importing History
is not possible until it finishes.

**If Framewring is closed or crashes in the middle**, the replacement is sorted out on the next start: if the original is still
in place, everything is rolled back; if the original is already in the Recycle Bin, the replacement is finished.

**Warnings** (you can still replace, but think twice):

- *quality not checked with “Test”* — there was no **Test (2 min)** for this video, or the Test was made with a different
  mode or quality than the compression (its VMAF doesn't describe this file);
- *Test VMAF below 93* — the quality loss may be visible;
- *editing source* (ProRes, DNxHD, …) — such files are usually worth keeping as they are;
- *small saving* — the compressed file is less than 20% smaller;
- *tracks of the original missing from the compressed file* — extra video tracks, subtitles, data tracks (e.g. GoPro
  telemetry, timecode) or attachments (e.g. fonts, covers) that the compressed file doesn't have.

**Blocked** (the file can't be ticked):

- the compressed file is not smaller than the original;
- the original was changed after compression;
- the compressed file was changed or swapped after compression (its size, date and checksum are recorded in History);
- the entry is from an older version of Framewring, without these records (no checksum) — compress the file again
  (**↻ Retry**) to be able to replace it;
- the entry was imported from another history file (**Import…**), so it can't be verified — compress the file again to be
  able to replace it;
- the original or the compressed file is not found;
- the file is queued or being compressed right now;
- a different file with the target name (`name.mp4`) already exists in the original's folder;
- a temporary file `name.framewring-new.mp4` from an unfinished replacement is next to the original — check that file first;
- the drive has no Recycle Bin (network and removable drives — Windows would delete the original permanently there);
  Framewring checks the drive a path really points to, so `subst` drives and mapped network drives are judged correctly;
- the Recycle Bin is turned off for this drive (*Don't move files to the Recycle Bin*);
- the original is bigger than the free space of this drive's Recycle Bin — Windows would delete it permanently. Empty the
  Recycle Bin or increase its size in its properties;
- the path is too long (more than ~250 characters, counting the temporary and the final name) — Windows would delete the
  original permanently instead of moving it to the Recycle Bin (verified). Move or rename the folder to shorten the path;
- the original has already been replaced.

**After replacing**, the file in the list shows *“✓ The original is replaced (it's in the Recycle Bin)”*, and in **History**
the **Original** button becomes *original in the Recycle Bin*. To undo, restore the original from the Recycle Bin
(and delete or rename the new `.mp4` if it took the same name). Once you empty the Recycle Bin, the originals are gone for good.

## 8. Data and logs

| How you run it | Data folder |
|---|---|
| Installed | `%APPDATA%\Framewring` |
| Portable | `data\` next to `Framewring.exe` |
| From source | next to `app.py` |

Files: `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (the last three contain paths to your videos)
and `framewring.log` (the exe's log — attach it to bug reports, removing paths you don't want to share).
Uninstalling keeps this folder; delete it by hand if you want.

**Backups.** Settings, history and the queue are also saved as up to 3 backup copies (the queue at most once every 5 minutes):
in a `backup` subfolder of the data folder, or — for the installed version — separately in `%LOCALAPPDATA%\Framewring\backup`.
If a file is damaged or the whole data folder is deleted, Framewring restores it from the newest good copy on the next start.
An unfinished `name.part.mp4` is removed when you quit in the middle of compression, or on the next start after a crash.

## 9. Troubleshooting

- **A GPU mode is greyed out.** Update the driver for your GPU vendor: Nvidia, AMD (AMD Software / Adrenalin)
  or Intel. AV1 on the GPU needs an Nvidia RTX 40 or 50 series card, an AMD Radeon RX 7000 series card or newer
  (or Ryzen 7040/8040-series graphics, Radeon 780M/880M), or Intel Arc / Core Ultra graphics. The reason is shown next to the greyed-out mode.
- **"Access denied" when writing to Documents / Videos / Desktop.** Windows *Controlled folder access* is blocking it:
  *Windows Security → Virus & threat protection → Ransomware protection → Allow an app through Controlled folder access*, add
  `Framewring.exe` and `ffmpeg.exe` from the program's `ffmpeg\bin` folder.
- **Memory errors / "page file is off" warning.** With the Windows page file disabled the encoder can run out of memory.
  Framewring retries automatically, but turning the page file back on is the real fix. If you keep the page file off
  on purpose, hide the warning with its **✕** — it stays hidden.
- **"Not enough free space".** Free some space on the output drive or choose another output folder.
- **The window does not open.** Install the [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
  or use the browser that opens instead.
- **Use your own FFmpeg.** Replace `ffmpeg.exe` and `ffprobe.exe` in the program's `ffmpeg\bin` folder.
- **A file can't be ticked in *Replace originals*.** The reason is shown under its name (see section 7). On a network or
  removable drive copy the original to a local drive first, or delete it yourself after checking the result.
- **"Not replaced: errors while decoding the compressed file".** The compressed file is damaged — nothing was changed.
  Compress the video again (**↻ Retry**) and replace it then.
- **"Not replaced: the compressed file has changed since compression (checksum differs)".** Something modified the
  compressed file after it was made (an editor, a tag tool, a copy that went wrong) — nothing was changed. Compress again.
- **"The new file is in place, but the original was NOT found in the Recycle Bin".** Windows reported success, but the bin
  has no record of the original. Look for it in the Recycle Bin by name; if it isn't there, it can't be restored from the bin.
- **I want an original back.** Restore it from the Windows Recycle Bin (it is there until you empty the bin).
- **History after reinstalling or on another PC.** Use **Export…** in History on the old setup and **Import…** on the new one.
  Each export gets its own timestamped name in your *Documents* folder (also when it is moved to OneDrive), so earlier exports
  are kept. Imported entries appear in History, but they can't be used to replace originals: an
  entry from another history file can't be verified (the import drops its checksum and file records). Compress the file
  again (**↻ Retry**) to replace it.

## 10. Reporting a problem

Click **🐞 Report a bug** in the header. A small window opens:

- **Open the form on GitHub** opens the bug-report form of this repository with the program version and install type,
  Windows version, graphics card names, FFmpeg version and mode already filled in. You see everything before sending;
  a free GitHub account is needed.
- **📂 Show the log** opens the folder with `framewring.log`. Attach it to the report if you can, removing anything you
  don't want to share, such as file paths. The log exists only in the installed and portable versions.

Questions and bug reports: [github.com/remrem23/framewring/issues](https://github.com/remrem23/framewring/issues).
The only official page of the program is [github.com/remrem23/framewring](https://github.com/remrem23/framewring).

---

<a id="русский"></a>
## Русский

**Framewring Жмых — инструкция.**
Framewring Жмых — бесплатный локальный компрессор видео (обёртка над FFmpeg). Находит на дисках тяжёлые видео и пережимает
их в разы меньше без видимой потери качества. Твои файлы никуда не уходят с компьютера.

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
5. Сжатие оригиналы **не** трогает. Когда проверишь результат, можно поставить сжатые файлы на их место кнопкой
   **«⇄ Заменить оригиналы…»** — оригиналы уйдут в корзину Windows (см. раздел 7).

При первом запуске над списком показывается короткая подсказка «Как это работает» с этими шагами; «Понятно» скрывает её насовсем.

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
| **Видеокарта AMD · AV1** | Radeon RX 7000 и новее, а также графика Ryzen серий 7040/8040 (Radeon 780M/880M). То же, что AV1 на Nvidia. На реальном железе ещё не проверялся — напиши, как работает. |
| **Видеокарта AMD · H.265** | Radeon RX 400 и новее, в том числе графика, встроенная в процессоры Ryzen. Открывается почти везде. Проверен на реальном железе (графика Ryzen 7 9700X). |
| **Видеокарта Intel · AV1** | Графика Intel Arc или Core Ultra. На реальном железе ещё не проверялся — напиши, как работает. |
| **Видеокарта Intel · H.265** | Большинство графики Intel примерно с 2016 года. Открывается почти везде. На реальном железе ещё не проверялся — напиши, как работает. |
| **Процессор · H.265** | Файл обычно на 10–20% меньше, чем у видеокарты, но в разы медленнее (часы на час видео в 4K). Если подходящей видеокарты нет или важен каждый гигабайт. |
| **Процессор · AV1** | Самый маленький файл, самый медленный режим. Открывается не везде. |
| **Видеокарта Mac · H.265** | Только на macOS при запуске из исходников. |

При запуске каждый режим проверяется пробным кодированием; выбрать можно только работающие. Режимы, которые не умеет
твоё железо или FFmpeg, серые, с причиной; режимы видеокарт производителя, которого в компьютере нет (например, режимы
AMD на компьютере только с Nvidia), скрыты. Лучший доступный помечен **«рекомендую»** и выбран по умолчанию
(твой собственный выбор запоминается). Порядок предпочтения: Nvidia AV1 → Nvidia H.265 → AMD H.265 → Intel H.265 →
AMD AV1 → Intel AV1 → процессор. AMD AV1 и Intel AV1 стоят ниже H.265, пока не проверены на реальном железе.

**Качество** — **Максимальное / Баланс / Компактное**. «Баланс» подходит почти всегда.
VMAF в тесте: 95+ — разницу практически не отличить, 92–95 — очень хорошо, ниже — уже видно.

**Скорость кодирования** — «Тщательно» даёт чуть меньший файл, но занимает в 1,5–2 раза больше времени.
Для «Процессор · AV1» это пресет 4 у SVT-AV1: на тесте 1080p файл вышел примерно на 16% меньше, чем с «Обычно», а времени ушло примерно в 1,7 раза больше.

**Звук** — по умолчанию копируется без потерь (почти ничего не весит). Если формат звука не помещается в MP4, он пережимается
в AAC 192 кбит/с; можно и принудительно выбрать AAC.

**Куда сохранять** — пусто = подпапка `compressed` рядом с каждым оригиналом. Можно указать одну общую папку.

Прочее: низкий приоритет (компьютером можно пользоваться), не давать компьютеру уснуть,
**«Пропускать уже сжатые файлы»** (если результат уже есть), **«Проверять обновления при запуске»** (см. ниже).

**Обновления.** Один раз при запуске Framewring спрашивает у GitHub (`api.github.com`) номер новейшей версии — это
единственный запрос в сеть, ничего о твоих файлах не передаётся. Отключается настройкой **«Проверять обновления при запуске»**.
Если есть новая версия, появляется полоса «Доступна версия Framewring X.» с кнопками **«Обновить»**, **«Что нового»** и **«Позже»**.
В установленной версии «Обновить» скачивает новый установщик из релиза на GitHub, сверяет его SHA-256 с `SHA256SUMS.txt`
того же релиза, ставит поверх старой версии и перезапускает программу; настройки, очередь и история сохраняются (если идёт
сжатие, программа сначала спросит). У портабл-версии и при запуске из исходников вместо неё кнопка **«Скачать»** — она
открывает страницу релиза.

### 5. Сжатие

- **«Сжать всё»** ставит в очередь все ещё не сжатые файлы. Добавлять файлы можно и во время сжатия.
- **«Стоп»** останавливает текущий файл и очищает очередь (спрашивает подтверждение, если файл уже частично сжат). Остановленный файл в следующий раз начнётся с начала.
- **«↻ Повторить»** у неудачных и отменённых файлов ставит файл в очередь заново.
- **«📂 Сжатый»** / **«📂 Оригинал»** показывают файл в проводнике. «Убрать готовые из списка» убирает завершённые.
- Список переживает перезапуск: закрыл программу — в следующий раз всё на месте.
- Если сжатие не может сделать файл меньше, видео помечается **«Оставлен как есть»** — результат крупнее оригинала никогда
  не остаётся. Во время сжатия Framewring сравнивает размер результата с объёмом оригинала, который FFmpeg уже прочитал
  (тот же участок видео), поэтому видео со сложным началом и статичным продолжением не останавливается по ошибке.
  Сжатие останавливается раньше, если результат не меньше 110% прочитанного, когда прочитано не меньше 10% файла, или не
  меньше 102%, когда прочитано не меньше 30%; если счётчиков чтения нет (не в Windows), — только когда результат уже достиг
  97% оригинала. Готовый результат, который меньше оригинала не хотя бы на 3%, удаляется. Оригинал не тронут;
  **«↻ Повторить»** (например, с **«Компактным»**) остаётся доступной.
- **«⇄ Заменить оригинал»** у готового файла и **«⇄ Заменить оригиналы…»** под списком — см. раздел 7.
- **«История»** — всё, что когда-либо сжато, и сколько места освобождено. **«Экспорт…»** сохраняет её в
  `Документы\Framewring-history-ГГГГ-ММ-ДД_ЧЧ-ММ-СС.json` (настоящая папка «Документы», в том числе перенесённая в OneDrive;
  прежние экспорты никогда не перезаписываются) и показывает файл в проводнике; **«Импорт…»** добавляет записи из такого файла
  (например, с другого компьютера или после переустановки), пропуская те, что уже есть. Импортированными записями нельзя
  заменить оригиналы (раздел 7) — чтобы заменить, сожми файл заново.
- После 100% идёт короткий этап «Дописываю файл»: FFmpeg переписывает файл, чтобы он сразу начинал играть.
  На HDD это от секунд до минуты.

### 6. Что происходит с файлами

- Поддерживаются: `.mp4 .mkv .mov .avi .webm .flv .ts .m2ts .m4v .wmv .mts`. Результат: `.mp4` (H.265 или AV1, 10 бит).
- При сжатии оригиналы только читаются: не изменяются и не удаляются. Оригинал покидает своё место, только если ты выбрал
  **«⇄ Заменить оригиналы…»**, которая отправляет его в корзину Windows (раздел 7).
- Результат никогда не пишется поверх оригинала. В папке `compressed` результат получает имя оригинала;
  если папка вывода — это папка оригинала, к имени добавляется `_compressed`; в общей папке вывода, которую ты указал,
  чужие файлы не перезаписываются — к имени добавляется номер.
- Файл с именем результата в `compressed` (или с суффиксом `_compressed`) считается прошлым результатом того же видео:
  при включённом «Пропускать уже сжатые файлы» (по умолчанию) он пропускается, при выключенном — сжимается заново и заменяется.
- Результат пишется в `имя.part.mp4` и переименовывается только целым. Если файл держит антивирус или плеер,
  Framewring ждёт и при необходимости сохраняет под другим именем — готовая работа не теряется.
- Сохраняются: звуковые дорожки, текстовые субтитры (субтитры-картинки, например PGS, в MP4 не помещаются — будет предупреждение),
  дата изменения файла. Черезстрочное видео деинтерлейсится. Видео с переменной частотой кадров (телефоны, OBS) сохраняет исходный тайминг.
- Перед стартом проверяется свободное место.

### 7. Замена оригиналов

Само сжатие места не освобождает — оригинал никуда не делся. Когда результат устраивает, **«Заменить оригиналы»** ставит
сжатый файл на место оригинала, а оригинал отправляет в корзину Windows.

**Как открыть.** «⇄ Заменить оригиналы…» под списком открывает окно без отметок. «⇄ Заменить оригинал» у готового файла
открывает то же окно с подсвеченным файлом; он отмечен, только если у него нет предупреждений (и его можно заменить).
В окне «Заменить оригиналы сжатыми» — всё из **«Истории»** (поэтому оно работает и после «Убрать готовые из списка», и после
перезапуска), по одной строке на оригинал, с путём к сжатому файлу, размером до → после и выигрышем.

**Только то, что ты отметил.** По умолчанию ничего не отмечено. «Отметить без предупреждений» отмечает только файлы без
предупреждений и без запретов; «Снять все» снимает отметки. Внизу видно, сколько файлов выбрано и сколько места освободится;
на кнопке — «Заменить (N)». Если у отмеченных файлов есть предупреждения, Framewring перечислит эти файлы и переспросит
перед началом.

**Контрольная сумма.** Сразу после сжатия Framewring считает контрольную сумму SHA-256 сжатого файла (этап «Считаю
контрольную сумму») и записывает её в «Историю». По ней видно, что на место оригинала встаёт байт в байт тот самый файл,
который получился при сжатии.

**Что происходит с каждым отмеченным файлом**, по очереди:

1. **Контрольная сумма сверяется ещё раз:** если после сжатия в сжатом файле изменился хотя бы один байт, файл не заменяется.
2. **Полная проверка сжатого файла:** длительность должна совпасть с оригиналом (допуск — 0,1% длины, не меньше 1 с и не
   больше 3 с), число звуковых дорожек тоже; видеодорожка декодируется целиком, без единой ошибки, и должна дойти до
   длительности оригинала (так ловится обрезанное видео, даже если звук полной длины); звук декодируется отдельно, тоже без
   ошибок, и должен быть не короче звука оригинала. Ход видно как «проверяю сжатый файл… N%».
3. **Прямо перед переносом всё проверяется ещё раз** (проверка могла идти долго): размер и дата оригинала и сжатого файла
   должны быть такими же, как записано при сжатии, и не должен появиться ни один из запретов ниже.
4. Framewring записывает в «Историю», что собирается сделать, — чтобы прерванную замену можно было потом разобрать.
5. Сжатый файл переносится к оригиналу под временным именем (`имя.framewring-new.mp4`); перенос никогда ничего
   не перезаписывает. С другого диска файл копируется, и копия сверяется со сжатым файлом побайтно.
6. **Оригинал уходит в корзину Windows** — оттуда его можно восстановить. Это проверяется заранее (корзина есть, включена,
   в ней хватает места, путь не слишком длинный) и ещё раз прямо перед этим шагом; если Windows всё же собралась бы удалить
   файл насовсем, она сначала спросит.
7. Framewring проверяет, что оригинал действительно в корзине (читает собственные записи корзины), и предупреждает, если его
   там нет.
8. Новый файл получает имя оригинала с `.mp4`: `видео.mp4` остаётся `видео.mp4`; для `видео.mkv` рядом появляется `видео.mp4`
   (и это переименование никогда не перезаписывает существующий файл). Если сжатый файл лежал в папке `compressed` и она
   опустела, она убирается; папка вывода, которую ты выбрал сам, не удаляется никогда.

**Итог по каждому файлу** (виден в его строке):

- «✓ заменён, оригинал в корзине» — готово;
- «⚠ …» — оригинал в корзине, но что-то после этого требует внимания: его не нашли в корзине или новый файл остался
  с временным именем (в сообщении написано, где он);
- «не заменён: …» — ошибка; оригинал не заменён.

Если что-то не получилось до шага с корзиной, **ничего не меняется**: оригинал остаётся на месте, сжатый файл возвращается туда,
где был. Ошибка с одним файлом не мешает остальным. Пока идёт замена, не перемещай и не открывай эти файлы; импорт «Истории»
недоступен, пока она не закончится.

**Если Framewring закрыли или он упал посередине**, замена разбирается при следующем запуске: если оригинал ещё на месте,
всё откатывается; если оригинал уже в корзине, замена доделывается.

**Предупреждения** (заменить можно, но стоит подумать):

- «качество не проверено „Тестом“» — для этого видео не было «Теста на 2 мин» или тест сделан с другими режимом или
  качеством, чем сжатие (его VMAF ничего не говорит об этом файле);
- «VMAF теста» ниже 93 — потеря качества может быть заметна;
- «монтажный исходник» (ProRes, DNxHD, …) — такие файлы обычно стоит оставить;
- «выигрыш небольшой» — сжатый файл меньше оригинала менее чем на 20%;
- «дорожек оригинала нет в сжатом файле» — дополнительных видеодорожек, субтитров, дорожек данных (например, телеметрия
  GoPro, таймкод) или вложений (например, шрифты, обложки), которых в сжатом файле нет.

**Запреты** (файл нельзя отметить):

- сжатый файл не меньше оригинала;
- оригинал изменили после сжатия;
- сжатый файл изменили или подменили после сжатия (его размер, дата и контрольная сумма записаны в «Истории»);
- запись из старой версии Framewring, без этих данных (без контрольной суммы), — сожми файл заново («↻ Повторить»), чтобы
  его можно было заменить;
- запись импортирована из другого файла истории («Импорт…»), её подлинность не подтвердить — сожми файл заново, чтобы его
  можно было заменить;
- оригинал или сжатый файл не найден;
- файл сейчас в очереди или сжимается;
- в папке оригинала уже есть другой файл с нужным именем (`имя.mp4`);
- рядом с оригиналом лежит временный `имя.framewring-new.mp4` от незавершённой замены — сначала проверь этот файл;
- на диске нет корзины (сетевые и съёмные диски — там Windows удалила бы оригинал насовсем); Framewring смотрит на диск,
  на который путь указывает на самом деле, поэтому диски `subst` и подключённые сетевые диски оцениваются правильно;
- для этого диска корзина отключена («Уничтожать файлы сразу после удаления»);
- оригинал больше свободного места в корзине этого диска — Windows удалила бы его насовсем. Очисти корзину или увеличь
  её размер в её свойствах;
- путь слишком длинный (больше ~250 символов, с учётом временного и итогового имени) — Windows удалила бы оригинал
  насовсем, мимо корзины (проверено). Перемести или переименуй папку, чтобы путь стал короче;
- оригинал уже заменён.

**После замены** у файла в списке написано «✓ Оригинал заменён (он в корзине).», а в **«Истории»** вместо кнопки
«Оригинал» — «оригинал в корзине». Чтобы отменить, восстанови оригинал из корзины (и удали или переименуй новый `.mp4`,
если он занял то же имя). После очистки корзины оригиналов больше нет.

### 8. Данные и журнал

| Как запущено | Папка данных |
|---|---|
| Установлено | `%APPDATA%\Framewring` |
| Портабл | `data\` рядом с `Framewring.exe` |
| Из исходников | рядом с `app.py` |

Файлы: `settings.json`, `queue.json`, `history.json`, `probe_cache.json` (в трёх последних — пути к твоим видео)
и `framewring.log` (журнал exe-версии — приложи его к сообщению об ошибке, убрав пути, которыми не хочешь делиться).
При удалении программы папка сохраняется; удали её вручную, если нужно.

**Резервные копии.** Настройки, история и очередь дополнительно сохраняются в резервные копии (до 3 штук; очередь — не чаще
раза в 5 минут): в подпапке `backup` папки данных, а у установленной версии — отдельно, в `%LOCALAPPDATA%\Framewring\backup`.
Если файл повреждён или папку данных удалили целиком, при следующем запуске Framewring восстановит всё из последней целой копии.
Недоделанный `имя.part.mp4` удаляется, если выйти посреди сжатия, или при следующем запуске после сбоя.

### 9. Если что-то не так

- **Режим видеокарты серый.** Обнови драйвер своей видеокарты: Nvidia, AMD (AMD Software / Adrenalin) или Intel.
  AV1 на видеокарте требует Nvidia RTX 40xx/50xx, AMD Radeon RX 7000 и новее (или графику Ryzen серий 7040/8040,
  Radeon 780M/880M) или графику Intel Arc / Core Ultra.
  Причина показана рядом с серым режимом.
- **«Отказано в доступе» при записи в «Документы» / «Видео» / на рабочий стол.** Мешает «Контролируемый доступ к папкам»:
  «Безопасность Windows → Защита от вирусов и угроз → Защита от программ-шантажистов → Разрешить работу приложения через
  контролируемый доступ к папкам», добавь `Framewring.exe` и `ffmpeg.exe` из папки `ffmpeg\bin` программы.
- **Сбои памяти / предупреждение «файл подкачки выключен».** Без файла подкачки кодеру может не хватить памяти.
  Framewring повторяет сам, но надёжнее включить файл подкачки. Если файл подкачки выключен намеренно, скрой
  предупреждение крестиком **✕** — программа это запомнит.
- **«Мало свободного места».** Освободи место на диске вывода или выбери другую папку.
- **Окно не открывается.** Установи [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
  или пользуйся браузером, который откроется вместо окна.
- **Свой FFmpeg.** Замени `ffmpeg.exe` и `ffprobe.exe` в папке `ffmpeg\bin` программы.
- **Файл нельзя отметить в «Заменить оригиналы».** Причина написана под его именем (см. раздел 7). На сетевом или съёмном
  диске сначала скопируй оригинал на локальный диск — или удали его сам, когда проверишь результат.
- **«Не заменён: ошибки при декодировании сжатого файла».** Сжатый файл повреждён — ничего не изменено.
  Сожми видео заново («↻ Повторить») и замени после этого.
- **«Не заменён: сжатый файл изменился после сжатия (контрольная сумма не совпадает)».** Что-то изменило сжатый файл после
  сжатия (редактор, программа для тегов, неудачное копирование) — ничего не изменено. Сожми заново.
- **«Новый файл на месте, но оригинал НЕ найден в корзине».** Windows сообщила об успехе, но в корзине нет записи
  об оригинале. Поищи его в корзине по имени; если его там нет, из корзины его не восстановить.
- **Нужно вернуть оригинал.** Восстанови его из корзины Windows (он там, пока корзину не очистили).
- **История после переустановки или на другом компьютере.** «Экспорт…» в «Истории» на старом месте и «Импорт…» на новом.
  Каждый экспорт получает своё имя с датой и временем в папке «Документы» (в том числе перенесённой в OneDrive), так что
  прежние экспорты сохраняются. Импортированные записи видны в «Истории», но заменить по ним оригиналы нельзя: запись из
  другого файла истории не подтвердить (при импорте её контрольная сумма и данные о файлах отбрасываются). Сожми файл
  заново («↻ Повторить»), чтобы его заменить.

### 10. Как сообщить о проблеме

Нажми **«🐞 Сообщить об ошибке»** в шапке. Откроется небольшое окно:

- **«Открыть форму на GitHub»** открывает форму сообщения об ошибке в этом репозитории, где уже заполнены версия программы
  и тип установки, версия Windows, названия видеокарт, версия FFmpeg и режим. Всё видно до отправки; нужен бесплатный
  аккаунт GitHub.
- **«📂 Показать журнал»** открывает папку с `framewring.log`. Если можешь, приложи его, убрав то, чем не хочешь делиться,
  например пути к файлам. Журнал есть только у установленной и портабл-версии.

Вопросы и ошибки: [github.com/remrem23/framewring/issues](https://github.com/remrem23/framewring/issues).
Официальная страница программы — только [github.com/remrem23/framewring](https://github.com/remrem23/framewring).
