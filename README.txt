FRAMEWRING - free local video compressor
========================================
(Русский текст - ниже, после английского.)

Framewring finds heavy videos on your drives and re-encodes them several
times smaller without visible quality loss. It is a front-end for FFmpeg.
Everything runs on your computer; nothing is uploaded anywhere.

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
  5. Originals are NOT deleted or modified. Delete them yourself after you
     have checked the result. A result never replaces an original.

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
  CPU · H.265 / AV1  - files usually 10-20% smaller than on the GPU, but many
                       times slower (hours per hour of 4K video). For PCs
                       without a suitable Nvidia card, or when every GB counts.
  Greyed-out modes are not supported by your hardware - try updating the
  Nvidia driver. VMAF: 95+ practically indistinguishable, 92-95 very good.

DATA AND LOG
  Installed:  %APPDATA%\Framewring
  Portable:   data\ next to Framewring.exe
  settings.json, queue.json, history.json, probe_cache.json and the log
  framewring.log (attach it to bug reports). Uninstalling keeps this folder.

TROUBLESHOOTING
  "Access denied" in Documents/Videos/Desktop: Windows "Controlled folder
  access". Windows Security -> Virus & threat protection -> Ransomware
  protection -> Allow an app through Controlled folder access -> add
  Framewring.exe and ffmpeg\bin\ffmpeg.exe from the program folder.
  Memory errors: turn the Windows page file back on.
  Your own FFmpeg: replace ffmpeg.exe and ffprobe.exe in ffmpeg\bin.

PRIVACY
  The interface is a local server on 127.0.0.1 protected by a token.
  No analytics, no telemetry, no update checks. Web pages open only when you
  click a link.

LICENSE
  GNU GPL v3 (LICENSE.txt). Third-party components and their licenses:
  THIRD-PARTY-NOTICES.md and the "licenses" and "ffmpeg" folders.
  Bug reports: https://github.com/remrem23/framewring/issues


==========================================================================
FRAMEWRING ЖМЫХ - бесплатный локальный компрессор видео
==========================================================================

Framewring Жмых находит на дисках тяжёлые видео и пережимает их в разы
меньше без видимой потери качества. Это обёртка над FFmpeg. Всё работает
на твоём компьютере, файлы никуда не отправляются.

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
  5. Оригиналы НЕ удаляются и не изменяются. Удаляй сам, когда проверишь
     результат. Результат никогда не заменяет оригинал.

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
  Процессор · H.265 / AV1   - файл обычно на 10-20% меньше, чем у видеокарты,
                              но в разы медленнее (часы на час видео в 4K).
                              Если подходящей карты Nvidia нет или важен
                              каждый гигабайт.
  Серые режимы не поддерживает твоё железо - попробуй обновить драйвер
  Nvidia. VMAF: 95+ - разницу практически не отличить, 92-95 - очень хорошо.

ДАННЫЕ И ЖУРНАЛ
  Установленная версия: %APPDATA%\Framewring
  Портабл:              data\ рядом с Framewring.exe
  settings.json, queue.json, history.json, probe_cache.json и журнал
  framewring.log (приложи его к сообщению об ошибке). При удалении
  программы папка сохраняется.

ЕСЛИ ЧТО-ТО НЕ ТАК
  «Отказано в доступе» в «Документах»/«Видео»/на рабочем столе: мешает
  «Контролируемый доступ к папкам». Безопасность Windows -> Защита от
  вирусов и угроз -> Защита от программ-шантажистов -> Разрешить работу
  приложения через контролируемый доступ к папкам -> добавь Framewring.exe
  и ffmpeg\bin\ffmpeg.exe из папки программы.
  Сбои памяти: включи файл подкачки Windows.
  Свой FFmpeg: замени ffmpeg.exe и ffprobe.exe в папке ffmpeg\bin.

ПРИВАТНОСТЬ
  Интерфейс - локальный сервер на 127.0.0.1, защищённый токеном. Нет
  аналитики, телеметрии и проверки обновлений. Веб-страницы открываются,
  только когда ты нажимаешь ссылку.

ЛИЦЕНЗИЯ
  GNU GPL v3 (LICENSE.txt). Сторонние компоненты и их лицензии:
  THIRD-PARTY-NOTICES.md и папки licenses и ffmpeg.
  Сообщить об ошибке: https://github.com/remrem23/framewring/issues
