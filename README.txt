FRAMEWRING - free local video compressor
========================================
(Русский текст - ниже, после английского.)

Framewring finds heavy videos on your drives and re-encodes them several
times smaller without visible quality loss. It is a front-end for FFmpeg.
Everything runs on your computer; your files never leave it.

Official page (the only one): https://github.com/remrem23/framewring
Full guide:  https://github.com/remrem23/framewring/blob/main/docs/USER-GUIDE.md


START
  Installed version: Start menu -> "Framewring".
  Portable version:  run Framewring.exe; settings and history are kept in
                     the "data" folder next to it.
  If Windows says "Windows protected your PC" (the app is not code-signed
  yet): "More info" -> "Run anyway".
  The app opens in its own window. If the Microsoft Edge WebView2 Runtime is
  missing, it opens in your browser instead - keep the app running while it
  compresses. Interface language: the list in the header (7 languages).

QUICK START
  1. Add videos: "Find heavy videos", "+ Files", "+ Folder", or drag files
     and folders onto the app window.
  2. Pick the mode marked "recommended" and quality "Balanced".
  3. "Test (2 min)": forecast of the final size and time, VMAF quality score.
     To compare by eye, open the files in compressed\_tests full screen.
  4. Happy with it - "Compress all". Results go to the "compressed"
     subfolder next to each original ("Output folder" changes this).
  5. Compression does NOT delete or modify originals. When you have checked
     the result, "Replace originals..." can put the compressed files in
     their place (see below). A short "How it works" hint is shown on
     first run; "Got it" hides it.

REPLACE ORIGINALS
  "Replace original" on a finished file, or "Replace originals..." under
  the list, opens the window "Replace originals with compressed files".
  Nothing is ticked by default - only the files you tick are replaced
  ("Tick those without warnings" ticks the safe ones). For each file:
  - the compressed file is fully checked: its duration and number of
    audio tracks must match the original; the video is decoded completely
    and must reach the original's duration; the audio is decoded too;
  - the original and the compressed file must be unchanged since
    compression (size, date) - checked again right before moving;
  - the compressed file takes the original's place: same folder and name,
    with .mp4 (for video.mkv a video.mp4 appears next to it); nothing is
    ever overwritten, a copy from another drive is compared byte by byte;
  - the ORIGINAL GOES TO THE WINDOWS RECYCLE BIN - you can restore it.
    Framewring then checks that it really is in the Recycle Bin.
  If anything fails before the Recycle Bin step, nothing changes. If the
  program is closed or crashes in the middle, the replacement is rolled
  back (original still in place) or finished (original already in the
  Recycle Bin) on the next start. History import waits until it ends.
  Warnings: quality not checked with "Test", Test VMAF below 93, editing
  source (ProRes etc.), small saving (under 20%), tracks of the original
  missing from the compressed file (extra video, subtitles, data such as
  GoPro telemetry or timecode, attachments).
  Not possible: the compressed file is not smaller; the original or the
  compressed file was changed after compression; entry from an older
  version (compress again with "Retry"); a file is missing; the file is
  queued or being compressed; the name is taken by another file; a
  leftover "name.framewring-new.mp4" from an unfinished replacement;
  network or removable drives (no Recycle Bin there; subst and mapped
  drives are judged by the drive they really point to); Recycle Bin
  turned off for the drive; the original
  is bigger than the free space of the Recycle Bin (Windows would delete
  it permanently - empty the bin or enlarge it); already replaced.
  Replaced files show "The original is replaced (it's in the Recycle
  Bin)"; in History the Original button becomes "original in the Recycle
  Bin". After you empty the Recycle Bin the originals are gone for good.

HISTORY
  "History" shows everything compressed and the space freed. "Export..."
  saves it to Documents\Framewring-history-YYYY-MM-DD.json; "Import..."
  adds entries from such a file, skipping duplicates.

FIND HEAVY VIDEOS
  Tick drives (or type a folder), choose the minimum size, start the search.
  You see big videos and roughly how much space compressing each would free.
  Worthwhile files are ticked automatically (only one of identical copies);
  add them to the queue with one button. "copies: N" = the same file in
  several places: delete the extra copies yourself, that frees more than any
  compression. Skipped: system folders, installed games (any "games" folder),
  folders starting with $ or ., OneDrive online-only files.
  Everything (free, https://www.voidtools.com/) makes the search take
  seconds. It is optional: without it Framewring scans folders itself.

WHICH MODE
  Nvidia GPU · AV1   - RTX 40/50 series. 5-7x faster than the CPU and smaller
                       than H.265. Best for big archives.
  Nvidia GPU · H.265 - plays almost everywhere, incl. older phones and TVs.
  AMD GPU · AV1      - Radeon RX 7000 or newer, and Ryzen 7040/8040-series
                       graphics (Radeon 780M/880M).
  AMD GPU · H.265    - Radeon RX 400 series or newer, including Ryzen
                       integrated graphics.
  Intel GPU · AV1    - Intel Arc or Core Ultra graphics.
  Intel GPU · H.265  - most Intel graphics since about 2016.
  CPU · H.265 / AV1  - files usually 10-20% smaller than on the GPU, but many
                       times slower (hours per hour of 4K video). For PCs
                       without a suitable GPU, or when every GB counts.
  Every mode is test-encoded on startup; only working ones can be picked.
  Greyed-out modes are not supported by your hardware - try updating the
  driver of your GPU (Nvidia, AMD or Intel). Modes for GPU vendors your PC
  does not have are hidden. AMD AV1 and the Intel modes have not been
  tested on real hardware yet - please report how they work for you.
  "Recommended" order: Nvidia AV1 -> Nvidia H.265 -> AMD H.265 ->
  Intel H.265 -> AMD AV1 -> Intel AV1 -> CPU (AMD AV1 and Intel AV1 stay
  below H.265 until they are verified on real hardware).
  VMAF: 95+ practically indistinguishable, 92-95 very good.

DATA AND LOG
  Installed:  %APPDATA%\Framewring
  Portable:   data\ next to Framewring.exe
  settings.json, queue.json, history.json, probe_cache.json and the log
  framewring.log (attach it to bug reports). Uninstalling keeps this folder.
  Settings, history and the queue also have up to 3 backup copies
  (installed: %LOCALAPPDATA%\Framewring\backup; otherwise data\backup);
  a damaged or deleted file is restored from them on the next start.

TROUBLESHOOTING
  "Access denied" in Documents/Videos/Desktop: Windows "Controlled folder
  access". Windows Security -> Virus & threat protection -> Ransomware
  protection -> Allow an app through Controlled folder access -> add
  Framewring.exe and ffmpeg\bin\ffmpeg.exe from the program folder.
  Memory errors: turn the Windows page file back on. If you keep it off on
  purpose, hide the warning with its "x" button (remembered).
  Your own FFmpeg: replace ffmpeg.exe and ffprobe.exe in ffmpeg\bin.
  A file can't be ticked in "Replace originals": the reason is shown under
  its name. Want an original back: restore it from the Recycle Bin.

REPORT A BUG
  "Report a bug" in the header opens a small window:
  "Open the form on GitHub" - the bug-report form with the program version,
  Windows version, graphics cards, FFmpeg version and mode filled in; you see
  everything before sending (a free GitHub account is needed).
  "Show the log" - opens the folder with framewring.log; attach it if you
  can, removing anything you don't want to share (e.g. file paths).

UPDATES
  Once per launch the app asks GitHub for the newest version number
  (setting "Check for updates on startup" turns this off). If there is a
  newer one, a bar offers "Update": the installed version downloads the new
  setup.exe, verifies its SHA-256, installs it and restarts; settings, queue
  and history are kept. The portable version shows "Download" instead.

PRIVACY
  The interface is a local server on 127.0.0.1 protected by a token.
  Your files never leave your computer. The only network request is a check
  for a new version on GitHub once per launch (can be turned off in
  settings); nothing about your files is sent. No analytics, no telemetry.
  Web pages open only when you click a link or button.

LICENSE
  GNU GPL v3 (LICENSE.txt). Third-party components and their licenses:
  THIRD-PARTY-NOTICES.md and the "licenses" and "ffmpeg" folders.
  Bug reports: https://github.com/remrem23/framewring/issues


==========================================================================
FRAMEWRING ЖМЫХ - бесплатный локальный компрессор видео
==========================================================================

Framewring Жмых находит на дисках тяжёлые видео и пережимает их в разы
меньше без видимой потери качества. Это обёртка над FFmpeg. Всё работает
на твоём компьютере, файлы его не покидают.

Официальная страница (единственная): https://github.com/remrem23/framewring
Подробная инструкция:
  https://github.com/remrem23/framewring/blob/main/docs/USER-GUIDE.md#русский


ЗАПУСК
  Установленная версия: «Пуск» -> «Framewring Жмых».
  Портабл-версия: запусти Framewring.exe; настройки и история хранятся
                  в папке data рядом.
  Если Windows пишет «Windows защитила ваш компьютер» (у программы пока нет
  цифровой подписи): «Подробнее» -> «Выполнить в любом случае».
  Программа открывается в своём окне. Если нет Microsoft Edge WebView2
  Runtime, интерфейс откроется в браузере - тогда не закрывай программу,
  пока идёт сжатие. Язык интерфейса: список в шапке (7 языков).

КАК ПОЛЬЗОВАТЬСЯ
  1. Добавь видео: «Найти тяжёлые видео», «+ Файлы», «+ Папка» или
     перетащи файлы и папки в окно программы.
  2. Режим с пометкой «рекомендую», качество «Баланс».
  3. «Тест на 2 мин»: прогноз размера и времени, оценка качества VMAF.
     Сравнить глазами: открой файлы из compressed\_tests на полном экране.
  4. Устраивает - «Сжать всё». Результат в подпапке compressed рядом
     с оригиналом (папку меняет настройка «Куда сохранять»).
  5. Сжатие НЕ удаляет и не изменяет оригиналы. Когда проверишь результат,
     «Заменить оригиналы…» может поставить сжатые файлы на их место
     (см. ниже). При первом запуске показывается короткая подсказка
     «Как это работает»; «Понятно» скрывает её.

ЗАМЕНА ОРИГИНАЛОВ
  «Заменить оригинал» у готового файла или «Заменить оригиналы…» под
  списком открывает окно «Заменить оригиналы сжатыми». По умолчанию ничего
  не отмечено - заменяются только отмеченные тобой файлы («Отметить без
  предупреждений» отмечает безопасные). Для каждого файла:
  - сжатый файл полностью проверяется: длительность и число звуковых
    дорожек должны совпасть с оригиналом; видео декодируется целиком и
    должно дойти до длительности оригинала; звук тоже декодируется;
  - оригинал и сжатый файл не должны меняться после сжатия (размер,
    дата) - это проверяется ещё раз прямо перед переносом;
  - сжатый файл встаёт на место оригинала: та же папка и имя, .mp4
    (для видео.mkv рядом появится видео.mp4); ничего не перезаписывается,
    копия с другого диска сверяется побайтно;
  - ОРИГИНАЛ УХОДИТ В КОРЗИНУ WINDOWS - его можно восстановить.
    Затем Framewring проверяет, что он действительно в корзине.
  Если что-то не вышло до шага с корзиной, ничего не меняется. Если
  программу закрыли или она упала посередине, при следующем запуске
  замена откатывается (оригинал на месте) или доделывается (оригинал уже
  в корзине). Импорт «Истории» ждёт, пока замена не закончится.
  Предупреждения: качество не проверено «Тестом», VMAF теста ниже 93,
  монтажный исходник (ProRes и т.п.), небольшой выигрыш (меньше 20%),
  в сжатом файле нет части дорожек оригинала (доп. видео, субтитры,
  данные вроде телеметрии GoPro или таймкода, вложения).
  Нельзя: сжатый файл не меньше; оригинал или сжатый файл изменили после
  сжатия; запись из старой версии (сожми заново - «Повторить»); файла
  нет; файл в очереди или сжимается; имя занято другим файлом; остался
  «имя.framewring-new.mp4» от незавершённой замены; сетевые и съёмные
  диски (там нет корзины; subst и подключённые диски оцениваются по
  диску, на который они на самом деле указывают); корзина отключена для
  диска; оригинал больше свободного места в корзине
  (Windows удалила бы его насовсем - очисти корзину или увеличь её);
  уже заменён.
  У заменённых файлов написано «Оригинал заменён (он в корзине)», в
  «Истории» вместо кнопки «Оригинал» - «оригинал в корзине». После очистки
  корзины оригиналов больше нет.

ИСТОРИЯ
  «История» - всё сжатое и сколько места освобождено. «Экспорт…» сохраняет
  её в Документы\Framewring-history-ГГГГ-ММ-ДД.json; «Импорт…» добавляет
  записи из такого файла, пропуская дубли.

НАЙТИ ТЯЖЁЛЫЕ ВИДЕО
  Отметь диски (или впиши папку), выбери минимальный размер, нажми «Искать».
  Программа покажет большие видео и примерно сколько места освободит сжатие
  каждого. Выгодные отмечаются сами (из одинаковых копий - только одна),
  «Добавить в очередь» ставит их в список. Метка «копий: N» - одинаковые
  файлы в разных местах: лишние копии удали сам, это освобождает больше
  любого сжатия. Пропускаются системные папки, установленные игры (любая
  папка games), папки на $ и ., файлы OneDrive «только в облаке».
  Everything (бесплатный, https://www.voidtools.com/) сокращает поиск до
  секунд. Он не обязателен: без него программа обходит папки сама.

ЧТО ВЫБРАТЬ
  Видеокарта Nvidia · AV1   - RTX 40xx/50xx. В 5-7 раз быстрее процессора,
                              компактнее H.265. Лучше всего для архивов.
  Видеокарта Nvidia · H.265 - открывается почти везде, в т.ч. на старых
                              телефонах и ТВ.
  Видеокарта AMD · AV1      - Radeon RX 7000 и новее, а также графика Ryzen
                              серий 7040/8040 (Radeon 780M/880M).
  Видеокарта AMD · H.265    - Radeon RX 400 и новее, в т.ч. графика,
                              встроенная в процессоры Ryzen.
  Видеокарта Intel · AV1    - графика Intel Arc или Core Ultra.
  Видеокарта Intel · H.265  - большинство графики Intel примерно с 2016 г.
  Процессор · H.265 / AV1   - файл обычно на 10-20% меньше, чем у видеокарты,
                              но в разы медленнее (часы на час видео в 4K).
                              Если подходящей видеокарты нет или важен
                              каждый гигабайт.
  При запуске каждый режим проверяется пробным кодированием, выбрать можно
  только работающие. Серые режимы не поддерживает твоё железо - попробуй
  обновить драйвер своей видеокарты (Nvidia, AMD или Intel). Режимы
  производителей, чьей видеокарты в компьютере нет, скрыты. AMD AV1 и режимы
  Intel на реальном железе ещё не проверялись - напиши, как они у тебя
  работают. Порядок «рекомендую»: Nvidia AV1 -> Nvidia H.265 -> AMD H.265 ->
  Intel H.265 -> AMD AV1 -> Intel AV1 -> процессор (AMD AV1 и Intel AV1 ниже
  H.265, пока не проверены на реальном железе).
  VMAF: 95+ - разницу практически не отличить, 92-95 - очень хорошо.

ДАННЫЕ И ЖУРНАЛ
  Установленная версия: %APPDATA%\Framewring
  Портабл:              data\ рядом с Framewring.exe
  settings.json, queue.json, history.json, probe_cache.json и журнал
  framewring.log (приложи его к сообщению об ошибке). При удалении
  программы папка сохраняется.
  У настроек, истории и очереди есть до 3 резервных копий (установленная
  версия: %LOCALAPPDATA%\Framewring\backup; иначе data\backup);
  повреждённый или удалённый файл восстанавливается из них при запуске.

ЕСЛИ ЧТО-ТО НЕ ТАК
  «Отказано в доступе» в «Документах»/«Видео»/на рабочем столе: мешает
  «Контролируемый доступ к папкам». Безопасность Windows -> Защита от
  вирусов и угроз -> Защита от программ-шантажистов -> Разрешить работу
  приложения через контролируемый доступ к папкам -> добавь Framewring.exe
  и ffmpeg\bin\ffmpeg.exe из папки программы.
  Сбои памяти: включи файл подкачки Windows. Если он выключен намеренно,
  скрой предупреждение крестиком (программа это запомнит).
  Свой FFmpeg: замени ffmpeg.exe и ffprobe.exe в папке ffmpeg\bin.
  Файл нельзя отметить в «Заменить оригиналы»: причина написана под его
  именем. Нужно вернуть оригинал: восстанови его из корзины.

СООБЩИТЬ ОБ ОШИБКЕ
  Кнопка «Сообщить об ошибке» в шапке открывает небольшое окно:
  «Открыть форму на GitHub» - форма, где уже заполнены версия программы,
  Windows, видеокарты, версия FFmpeg и режим; всё видно до отправки (нужен
  бесплатный аккаунт GitHub).
  «Показать журнал» - открывает папку с framewring.log; приложи его, если
  можешь, убрав то, чем не хочешь делиться (например, пути к файлам).

ОБНОВЛЕНИЯ
  Один раз при запуске программа спрашивает у GitHub номер новейшей версии
  (отключается настройкой «Проверять обновления при запуске»). Если есть
  новая, появляется кнопка «Обновить»: установленная версия скачивает новый
  setup.exe, сверяет его SHA-256, устанавливает и перезапускается;
  настройки, очередь и история сохраняются. У портабл-версии вместо неё -
  «Скачать».

ПРИВАТНОСТЬ
  Интерфейс - локальный сервер на 127.0.0.1, защищённый токеном.
  Твои файлы никуда не уходят с компьютера. Единственный запрос в сеть -
  проверка новой версии на GitHub один раз при запуске (можно отключить
  в настройках); ничего о твоих файлах не передаётся. Аналитики и
  телеметрии нет. Веб-страницы открываются, только когда ты нажимаешь
  ссылку или кнопку.

ЛИЦЕНЗИЯ
  GNU GPL v3 (LICENSE.txt). Сторонние компоненты и их лицензии:
  THIRD-PARTY-NOTICES.md и папки licenses и ffmpeg.
  Сообщить об ошибке: https://github.com/remrem23/framewring/issues
