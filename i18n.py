# -*- coding: utf-8 -*-
"""Строки интерфейса Framewring: русский и английский.

Ключи одинаковые в обоих языках. Параметры пишутся как {name}. Бэкенд отдаёт в интерфейс
не готовый текст, а {"k": ключ, "p": {параметры}}; переводит страница (тот же словарь
встраивается в неё как JSON). Python сам переводит только системные окна и консоль.

To add a language: copy the "en" block, translate the values, keep keys and {params} intact,
and add the language code to LANGS (plus a button in the header in app.py).
"""
import os
import re

LANGS = ("ru", "en")
APP_NAMES = {"ru": "Framewring Жмых", "en": "Framewring"}

RU = {
    # ---- шапка, общее
    "app.suffix": " Жмых",
    "app.title": "Framewring Жмых — компрессор видео",
    "app.sub": "Жмёт локально через FFmpeg. Файлы никуда не уходят, лимитов нет.",
    "ver.checking": "проверяю FFmpeg…",
    "ver.found": "FFmpeg найден",
    "ver.missing": "FFmpeg не найден",
    "ver.no_response": "программа не отвечает (закрыта?)",
    "lang.title": "Язык интерфейса",
    "common.collapse": "Свернуть",
    "common.stop": "Стоп",
    "common.close": "Закрыть",
    "err.generic": "Ошибка",
    "err.no_response": "Программа не отвечает",
    "unit.gb": "ГБ",
    "unit.mb": "МБ",
    "unit.mbps": "Мбит/с",
    "unit.k": "к",
    "time.hm": "{h} ч {m} мин",
    "time.ms": "{m} мин {s} с",
    "time.s": "{s} с",
    # ---- поддержка автора
    "donate.btn": "♥ Поддержать автора",
    "donate.btn_title": "Поддержать автора Framewring",
    "donate.title": "Поддержать автора",
    "donate.text": "Framewring бесплатный. Если он сэкономил тебе место и время, можно поддержать автора.",
    "donate.ways": "Способы поддержки (карта, USDT) — на официальной странице программы на GitHub.",
    "donate.open": "♥ Открыть страницу поддержки",
    "donate.official": "Официальная страница:",
    "donate.official2": "Скачивай Framewring только оттуда. Если программа скачана в другом месте и здесь указан "
                        "другой адрес — это изменённая копия.",
    # ---- настройки
    "set.mode": "Режим",
    "set.quality": "Качество",
    "set.speed": "Скорость кодирования",
    "set.speed_hint": "«Тщательно» даёт чуть меньший файл, но занимает в 1,5–2 раза больше времени.",
    "set.audio": "Звук",
    "set.audio_hint": "Копирование звука почти ничего не весит, пережимать нет смысла.",
    "set.outdir": "Куда сохранять",
    "set.outdir_ph": "Пусто = подпапка «compressed» рядом с исходником",
    "set.lowprio": "Низкий приоритет (компом можно пользоваться)",
    "set.nosleep": "Не давать компьютеру уснуть",
    "set.skip": "Пропускать уже сжатые файлы",
    "set.qhint": "{unit} {high} / {balanced} / {compact}. «Баланс» визуально почти неотличим от оригинала. "
                 "Не уверен — сделай тест.",
    "quality.high": "Максимальное",
    "quality.balanced": "Баланс",
    "quality.compact": "Компактное",
    "quality.name.high": "максимальное",
    "quality.name.balanced": "сбалансированное",
    "quality.name.compact": "компактное",
    "speed.slow": "Тщательно",
    "speed.normal": "Обычно",
    "speed.fast": "Быстрее",
    "audio.auto": "Копировать без потерь",
    "audio.aac": "Пережать AAC 192",
    "preset.recommended": " · рекомендую",
    "preset.unavailable": "Недоступно: {why}",
    "preset.nvenc_av1.title": "Видеокарта Nvidia · AV1",
    "preset.nvenc_av1.desc": "RTX 40xx/50xx. В 5–7 раз быстрее процессора и компактнее, чем H.265. "
                             "Лучший выбор для больших архивов. Играется на ПК, новых телефонах и ТВ.",
    "preset.nvenc_hevc.title": "Видеокарта Nvidia · H.265",
    "preset.nvenc_hevc.desc": "Быстро, и открывается почти везде: старые телефоны, ТВ, iPhone. "
                              "Файл немного больше, чем у AV1.",
    "preset.vt_hevc.title": "Видеокарта Mac · H.265",
    "preset.vt_hevc.desc": "Аппаратный энкодер Mac (VideoToolbox). Быстро, файл больше, чем на процессоре.",
    "preset.x265.title": "Процессор · H.265",
    "preset.x265.desc": "Файл обычно на 10–20% меньше, чем у видеокарты, но в разы медленнее. "
                        "Если видеокарты нет или важен каждый гигабайт.",
    "preset.av1.title": "Процессор · AV1",
    "preset.av1.desc": "Самый маленький файл, но самый медленный режим. Открывается не везде.",
    "caps.no_encoder": "нет в твоей сборке FFmpeg",
    "caps.hw_unsupported": "видеокарта или драйвер не поддерживают",
    "caps.check_failed": "проверка не прошла",
    # ---- кнопки списка
    "btn.files": "+ Файлы",
    "btn.folder": "+ Папка",
    "btn.scan": "Найти тяжёлые видео",
    "btn.scan_title": "Найти на дисках большие видео, которые выгодно сжать",
    "btn.hist": "История",
    "btn.hist_title": "Всё, что уже сжато, с кнопками показать файлы",
    "btn.test_min": "Тест на {n} мин",
    "btn.test_sec": "Тест на {n} с",
    "btn.test_title": "Сжимает кусок из середины каждого файла и показывает прогноз размера, времени и качества",
    "btn.go": "Сжать всё",
    "btn.clear": "Убрать готовые из списка",
    "btn.open_out": "📂 Сжатый",
    "btn.open_out_title": "Открыть папку и выделить сжатый файл",
    "btn.open_src": "📂 Оригинал",
    "btn.open_src_title": "Открыть папку и выделить оригинал",
    "manual.ph": "…или вставь путь к файлу или папке и нажми Enter",
    "manual.add": "Добавить",
    "drop.browser": "Перетаскивание работает в окне программы. Здесь — кнопки «+ Файлы» / «+ Папка».",
    "pick.opening": "Открываю окно выбора…",
    "pick.opening_browser": "Открываю окно выбора… (может появиться за браузером)",
    "add.adding": "Добавляю…",
    "start.probing": "Ещё читаю параметры файлов, подожди секунду",
    "start.nothing": "Нечего запускать: добавь файлы (готовые и уже стоящие в очереди не трогаю)",
    "stop.confirm": "Остановить сжатие «{name}»? Сделано {pct}%, файл потом начнётся сначала.",
    # ---- задачи
    "status.probing": "Читаю файл…",
    "status.ready": "Ждёт",
    "status.queued": "В очереди",
    "status.running": "В работе",
    "status.done": "Готово",
    "status.tested": "Тест готов",
    "status.skipped": "Пропущен",
    "status.error": "Ошибка",
    "status.cancelled": "Отменён",
    "jobs.empty1": "Добавь видео кнопками сверху.",
    "jobs.empty2": "Совет: сначала нажми «Тест», посмотри прогноз размера и качество, потом жми «Сжать всё».",
    "job.audio": "звук: {list}",
    "job.no_audio": "нет",
    "job.skipped_prefix": "Уже был сжат: ",
    "job.bigger": "Результат больше оригинала: исходник уже сжат эффективно. Оставь оригинал или выбери «Компактное».",
    "job.retry": "↻ Повторить",
    "job.retry_title": "Поставить этот файл в очередь ещё раз",
    "job.remove_title": "Убрать из списка (файл не удаляется)",
    "test.head": "Тест: {label}",
    "test.clip": "Кусок {a} → {b} ({pct}%).",
    "test.forecast": "Прогноз для всего файла: ≈ {size}",
    "test.time": ", время ≈ {t}.",
    "test.vmaf_scale": "(95+ — разницу практически не отличить, 92–95 — очень хорошо, ниже — уже видно)",
    "test.eyes": "Сравни глазами: открой оба файла из папки _tests на полном экране.",
    "test.not_smaller": "Сжатие не уменьшает этот файл: исходник уже сжат эффективно.",
    "test.open": "Открыть папку теста",
    "progress.finish": "Дописываю файл: переношу индекс в начало, чтобы видео сразу открывалось и перематывалось",
    "progress.left_approx": "осталось ≈ {t}",
    "progress.big_files": "на больших файлах это пара минут",
    "progress.ok": "всё идёт нормально, не закрывай",
    "progress.speed": "скорость {v}",
    "progress.left": "осталось {t}",
    "progress.elapsed": "прошло {t}",
    "progress.so_far": "уже {size}",
    "foot.queue": "В очереди ещё {n} ({d} видео)",
    "foot.disk": "Свободно на диске для результата: {size}",
    "warn.ffmpeg_t": "FFmpeg не найден.",
    "warn.ffmpeg_1": "Установи его и перезапусти программу.",
    "warn.ffmpeg_2": "Или распакуй FFmpeg в папку ffmpeg рядом с программой.",
    "warn.pf_t": "Файл подкачки Windows выключен.",
    "warn.pf_1": "Из-за этого сжатие иногда падает с ошибкой «Cannot allocate memory», даже когда свободной памяти "
                 "полно: программы заранее резервируют память, и запаса не остаётся. Framewring в таком случае сам "
                 "повторит файл, но лучше включить подкачку:",
    "warn.pf_2": "→ «Дополнительно» → Быстродействие «Параметры» → «Дополнительно» → Виртуальная память «Изменить» "
                 "→ галочка «Автоматически выбирать объём файла подкачки» → ОК и перезагрузка.",
    # ---- история
    "hist.title": "История сжатия",
    "hist.sum": "Сжато файлов: {n} · было {before}, стало {after} · освобождено {saved} ({pct}%)",
    "hist.empty": "Пока ничего не сжато. Здесь появятся все готовые файлы, даже если убрать их из списка.",
    "hist.unknown_mode": "режим неизвестен",
    "hist.took": "сжималось {t}",
    # ---- поиск тяжёлых видео
    "scan.title": "Поиск тяжёлых видео",
    "scan.hint": "Ищет большие видео и прикидывает, сколько места освободит сжатие. Системные папки, установленные "
                 "игры и файлы OneDrive «только в облаке» пропускаются. Ничего не удаляет и не меняет.",
    "scan.path_ph": "…или своя папка (например D:\\Videos)",
    "scan.min_label": "Файлы от",
    "scan.min200": "200 МБ",
    "scan.min500": "500 МБ",
    "scan.min1000": "1 ГБ",
    "scan.min3000": "3 ГБ",
    "scan.ev_label": "через Everything",
    "scan.ev_title": "Если установлен Everything (voidtools), ищем по его индексу: доли секунды вместо минут. "
                     "Сними галочку, если Everything индексирует не все диски.",
    "scan.search": "Искать",
    "scan.need_root": "Отметь диск или впиши папку",
    "scan.phase.walk": "Ищу большие видео",
    "scan.phase.ev_open": "Открываю индекс Everything",
    "scan.phase.probe": "Читаю параметры видео",
    "scan.method.everything": "индекс Everything",
    "scan.method.walk": "обход папок",
    "scan.running": "{phase}… Папок просмотрено: {dirs} · больших видео: {cand}",
    "scan.read": "прочитано {n}",
    "scan.error": "Ошибка поиска: {e}",
    "scan.found": "Найдено {n} видео на {size} за {t}{method}. Если сжать все, освободится примерно {save}. "
                  "Оценка грубая, точный прогноз покажет «Тест».",
    "scan.none": "Подходящих видео не нашлось. Попробуй порог поменьше или другой диск.",
    "scan.stopped": "Поиск остановлен.",
    "scan.ev_tip": "Совет: с бесплатной программой {ev} поиск займёт секунды вместо {t} — Framewring сам "
                   "воспользуется её индексом.",
    "scan.ev_hide": "больше не показывать",
    "scan.dups": "Ещё одинаковые копии одних и тех же видео в разных местах занимают {size} (помечены «копий: N»). "
                 "Лишние копии Framewring не удаляет: проверь и удали сам.",
    "scan.cloud": "Пропущено файлов «только в облаке» OneDrive: {n}.",
    "scan.copies": "копий: {n} ({drives})",
    "scan.copies_title": "Тот же файл (имя и размер) лежит в нескольких местах: удалить лишнюю копию выгоднее, "
                         "чем сжимать",
    "scan.edit": "монтажный исходник",
    "scan.edit_title": "Монтажный кодек: обычно это исходник для видеоредактора, сжимать его стоит, только если "
                       "монтаж закончен",
    "scan.in_list": "уже в списке",
    "scan.has_out": "сжатая копия есть",
    "scan.v.g": "много",
    "scan.v.y": "средне",
    "scan.v.m": "мало",
    "scan.selected": "Выбрано {n} на {size} · освободится ≈ {save}",
    "scan.pick_good": "Отметить выгодные",
    "scan.pick_all": "Все",
    "scan.pick_none": "Снять",
    "scan.add": "Добавить в очередь ({n})",
    "scan.adding": "Добавляю файлы: {n}…",
    "scan.added": "Добавлено в очередь: {n}. Можно жать «Тест» или «Сжать всё».",
    "drive.free": "свободно {free} из {total}",
    "drive.net": "сеть",
    "drive.removable": "съёмный",
    "drive.none": "Диски не найдены, укажи папку",
    "drive.home": "Домашняя папка",
    # ---- этапы работы (бэкенд)
    "phase.compress": "Сжимаю",
    "phase.save": "Сохраняю файл",
    "phase.save_wait": "Сохраняю файл: его сейчас держит другая программа (обычно антивирус проверяет свежий файл "
                       "или открыт плеер), жду… {secs} с",
    "phase.finish": "Дописываю файл",
    "phase.test_cut": "Тест: вырезаю кусок",
    "phase.test_enc": "Тест: сжимаю кусок",
    "phase.vmaf": "Считаю VMAF (оценка качества)",
    # ---- заметки к задачам (бэкенд)
    "note.av1_lp_low": "Мало свободной памяти для AV1: параллельность снижена до lp={lp} (чуть медленнее). "
                       "Поможет закрыть лишние программы или увеличить файл подкачки.",
    "note.mem_retry": "Сбой: Windows не выделила память (попытка {n} из 3). Перезапустил сжатие этого файла.",
    "note.mem_retry_cpu": "Сбой: Windows не выделила память (попытка {n} из 3). Перезапустил сжатие этого файла, "
                          "декодирую на процессоре.",
    "note.av1_lp_retry": "Не хватило памяти для AV1: перезапустил с параллельностью lp={lp} (медленнее). "
                         "Поможет закрыть лишние программы или увеличить файл подкачки.",
    "note.saved_as": "«{out}» занят другой программой (открыт в плеере?), сохранил как «{alt}».",
    "note.rename_failed": "Сжатие готово, но файл так и не удалось переименовать (занят другой программой). "
                          "Готовый результат: «{name}» — переименуй его сам, убрав «.part».",
    "note.space_tight": "Места на диске впритык (свободно {free} ГБ): если кончится, сжатие оборвётся.",
    "note.image_subs": "В оригинале есть субтитры-картинки ({codecs}): в MP4 они не переносятся. "
                       "Если нужны, не удаляй оригинал.",
    "note.interrupted": "Прошлый сеанс закрылся во время сжатия этого файла: начнётся заново.",
    # ---- ошибки (бэкенд)
    "err.probe_failed": "ffprobe не смог прочитать файл",
    "err.no_video": "в файле нет видеодорожки",
    "err.not_found_path": "Не найдено: {path}",
    "err.no_ffmpeg": "FFmpeg не найден",
    "err.scan_no_roots": "Выбери хотя бы один диск или существующую папку",
    "err.scan_running": "Поиск уже идёт",
    "err.ffmpeg_code": "ffmpeg завершился с кодом {code}",
    "err.mem3": "Трижды не хватило оперативной памяти. Закрой лишние программы и включи файл подкачки "
                "(см. предупреждение вверху).\n\n{detail}",
    "err.av1_mem": "Не хватает оперативной памяти для AV1 на {res}. Закрой лишние программы, увеличь файл подкачки "
                   "или выбери H.265.\n\n{detail}",
    "err.same_as_src": "Отказ: результат совпал бы с оригиналом. Выбери другую папку.",
    "err.no_space": "Мало места на диске для результата: нужно примерно {need} ГБ, свободно {free} ГБ ({dir}). "
                    "Освободи место или укажи другую папку в «Куда сохранять».",
    "err.file_gone": "Файл не найден (удалён, перемещён или диск отключён).",
    "err.no_result": "задача завершилась без результата",
    "err.pick_failed": "Не удалось открыть окно выбора файлов ({detail}). Вставь путь вручную.",
    "api.checking": "Ещё проверяю возможности FFmpeg и видеокарты, подожди пару секунд",
    "api.mode_unavailable": "Выбранный режим недоступен на этом компьютере",
    "api.cant_retry": "Эту задачу сейчас нельзя повторить",
    "api.unreadable": "Файл не читается: {detail}",
    "api.no_info": "нет параметров видео",
    "api.url_denied": "ссылка не разрешена",
    "api.open_missing": "Файл не найден (удалён или перемещён): {path}",
    # ---- системные окна и консоль (переводит Python)
    "pick.title_files": "Выбери видео",
    "pick.title_folder": "Выбери папку с видео",
    "pick.video": "Видео",
    "pick.all": "Все файлы",
    "native.close_confirm": "Сейчас идёт сжатие. Остановить его и закрыть программу?\n\n"
                            "Список файлов сохранится, текущий файл потом начнётся заново.",
    "con.window_unavail": " Своё окно недоступно ({e}), открываю в браузере.",
    "con.window_failed": " Своё окно не запустилось ({e}), открываю в браузере.",
    "con.dnd_unavail": " drag&drop недоступен: {e}",
    "con.already": "Framewring уже запущен: {url}  (показываю его, второй экземпляр не нужен)",
    "con.no_port": "Не нашёл свободный порт 8765–8799",
    "con.started": " {name} v{ver} запущен: {url}",
    "con.data": " Данные (настройки, очередь, история): {dir}",
    "con.ffmpeg": " FFmpeg: {path}",
    "con.ffmpeg_missing": "НЕ НАЙДЕН",
    "con.restored": " Восстановил список прошлого сеанса, файлов: {n}.",
    "con.keep_open": " Не закрывай это окно, пока идёт сжатие.",
    "con.how_quit": " Чтобы выключить, закрой окно или нажми Ctrl+C.",
}

EN = {
    # ---- header, common
    "app.suffix": "",
    "app.title": "Framewring — video compressor",
    "app.sub": "Compresses videos locally with FFmpeg. Your files never leave your computer. No limits.",
    "ver.checking": "checking FFmpeg…",
    "ver.found": "FFmpeg found",
    "ver.missing": "FFmpeg not found",
    "ver.no_response": "the program isn't responding (closed?)",
    "lang.title": "Interface language",
    "common.collapse": "Hide",
    "common.stop": "Stop",
    "common.close": "Close",
    "err.generic": "Error",
    "err.no_response": "The program isn't responding",
    "unit.gb": "GB",
    "unit.mb": "MB",
    "unit.mbps": "Mbit/s",
    "unit.k": "k",
    "time.hm": "{h} h {m} min",
    "time.ms": "{m} min {s} s",
    "time.s": "{s} s",
    # ---- support
    "donate.btn": "♥ Support the author",
    "donate.btn_title": "Support the author of Framewring",
    "donate.title": "Support the author",
    "donate.text": "Framewring is free. If it saved you space and time, you can support the author.",
    "donate.ways": "Ways to support (card, USDT) are on the program's official GitHub page.",
    "donate.open": "♥ Open the support page",
    "donate.official": "Official page:",
    "donate.official2": "Download Framewring only from there. If you got it somewhere else and a different "
                        "address is shown here, it's a modified copy.",
    # ---- settings
    "set.mode": "Mode",
    "set.quality": "Quality",
    "set.speed": "Encoding speed",
    "set.speed_hint": "“Thorough” makes a slightly smaller file but takes 1.5–2× longer.",
    "set.audio": "Audio",
    "set.audio_hint": "Copied audio takes almost no space, so there's no point re-encoding it.",
    "set.outdir": "Output folder",
    "set.outdir_ph": "Empty = “compressed” subfolder next to the original",
    "set.lowprio": "Low priority (you can keep using your PC)",
    "set.nosleep": "Keep the computer awake",
    "set.skip": "Skip already compressed files",
    "set.qhint": "{unit} {high} / {balanced} / {compact}. “Balanced” looks almost identical to the original. "
                 "Not sure? Run a test.",
    "quality.high": "Maximum",
    "quality.balanced": "Balanced",
    "quality.compact": "Compact",
    "quality.name.high": "maximum",
    "quality.name.balanced": "balanced",
    "quality.name.compact": "compact",
    "speed.slow": "Thorough",
    "speed.normal": "Normal",
    "speed.fast": "Faster",
    "audio.auto": "Copy losslessly",
    "audio.aac": "Re-encode to AAC 192",
    "preset.recommended": " · recommended",
    "preset.unavailable": "Unavailable: {why}",
    "preset.nvenc_av1.title": "Nvidia GPU · AV1",
    "preset.nvenc_av1.desc": "RTX 40xx/50xx. 5–7× faster than the CPU and smaller files than H.265. "
                             "Best for large archives. Plays on PCs, recent phones and TVs.",
    "preset.nvenc_hevc.title": "Nvidia GPU · H.265",
    "preset.nvenc_hevc.desc": "Fast, and plays almost everywhere: older phones, TVs, iPhone. "
                              "Files are a bit bigger than with AV1.",
    "preset.vt_hevc.title": "Mac GPU · H.265",
    "preset.vt_hevc.desc": "Mac hardware encoder (VideoToolbox). Fast, but files are bigger than with the CPU.",
    "preset.x265.title": "CPU · H.265",
    "preset.x265.desc": "Files are usually 10–20% smaller than with a GPU, but encoding is many times slower. "
                        "For when there's no GPU or every gigabyte counts.",
    "preset.av1.title": "CPU · AV1",
    "preset.av1.desc": "The smallest files, but the slowest mode. Doesn't play everywhere.",
    "caps.no_encoder": "not in your FFmpeg build",
    "caps.hw_unsupported": "not supported by your GPU or driver",
    "caps.check_failed": "the check failed",
    # ---- list buttons
    "btn.files": "+ Files",
    "btn.folder": "+ Folder",
    "btn.scan": "Find heavy videos",
    "btn.scan_title": "Find large videos on your drives that are worth compressing",
    "btn.hist": "History",
    "btn.hist_title": "Everything compressed so far, with buttons to show the files",
    "btn.test_min": "Test ({n} min)",
    "btn.test_sec": "Test ({n} s)",
    "btn.test_title": "Compresses a clip from the middle of each file and predicts size, time and quality",
    "btn.go": "Compress all",
    "btn.clear": "Clear finished",
    "btn.open_out": "📂 Compressed",
    "btn.open_out_title": "Open the folder and select the compressed file",
    "btn.open_src": "📂 Original",
    "btn.open_src_title": "Open the folder and select the original",
    "manual.ph": "…or paste a file or folder path and press Enter",
    "manual.add": "Add",
    "drop.browser": "Drag and drop works in the program window. Here, use “+ Files” / “+ Folder”.",
    "pick.opening": "Opening the file picker…",
    "pick.opening_browser": "Opening the file picker… (it may appear behind the browser)",
    "add.adding": "Adding…",
    "start.probing": "Still reading the files, wait a moment",
    "start.nothing": "Nothing to start: add files (finished and already queued files are left alone)",
    "stop.confirm": "Stop compressing “{name}”? {pct}% done. The file will start over next time.",
    # ---- jobs
    "status.probing": "Reading file…",
    "status.ready": "Waiting",
    "status.queued": "Queued",
    "status.running": "Working",
    "status.done": "Done",
    "status.tested": "Test ready",
    "status.skipped": "Skipped",
    "status.error": "Error",
    "status.cancelled": "Cancelled",
    "jobs.empty1": "Add videos with the buttons above.",
    "jobs.empty2": "Tip: press “Test” first to see the predicted size and quality, then press “Compress all”.",
    "job.audio": "audio: {list}",
    "job.no_audio": "none",
    "job.skipped_prefix": "Already compressed: ",
    "job.bigger": "The result is bigger than the original: the source is already compressed efficiently. "
                  "Keep the original or choose “Compact”.",
    "job.retry": "↻ Retry",
    "job.retry_title": "Queue this file again",
    "job.remove_title": "Remove from the list (the file isn't deleted)",
    "test.head": "Test: {label}",
    "test.clip": "Clip {a} → {b} ({pct}%).",
    "test.forecast": "Forecast for the whole file: ≈ {size}",
    "test.time": ", time ≈ {t}.",
    "test.vmaf_scale": "(95+: practically indistinguishable, 92–95: very good, lower: the difference shows)",
    "test.eyes": "Compare by eye: open both files from the _tests folder in full screen.",
    "test.not_smaller": "Compression doesn't make this file smaller: the source is already compressed efficiently.",
    "test.open": "Open test folder",
    "progress.finish": "Finishing the file: moving the index to the start so the video opens and seeks instantly",
    "progress.left_approx": "≈ {t} left",
    "progress.big_files": "takes a couple of minutes on big files",
    "progress.ok": "all good, don't close the program",
    "progress.speed": "speed {v}",
    "progress.left": "{t} left",
    "progress.elapsed": "elapsed {t}",
    "progress.so_far": "{size} so far",
    "foot.queue": "{n} more in the queue ({d} of video)",
    "foot.disk": "Free space for output: {size}",
    "warn.ffmpeg_t": "FFmpeg not found.",
    "warn.ffmpeg_1": "Install it and restart the program.",
    "warn.ffmpeg_2": "Or unpack FFmpeg into an ffmpeg folder next to the program.",
    "warn.pf_t": "The Windows page file is turned off.",
    "warn.pf_1": "Because of this, compression sometimes fails with “Cannot allocate memory” even when there's "
                 "plenty of free RAM: programs reserve memory in advance and nothing is left over. Framewring "
                 "retries the file automatically, but it's better to turn the page file on:",
    "warn.pf_2": "→ “Advanced” → Performance “Settings” → “Advanced” → Virtual memory “Change” → tick "
                 "“Automatically manage paging file size for all drives” → OK, then restart.",
    # ---- history
    "hist.title": "Compression history",
    "hist.sum": "Files compressed: {n} · before {before}, after {after} · freed {saved} ({pct}%)",
    "hist.empty": "Nothing compressed yet. Every finished file will show up here, even after you clear it "
                  "from the list.",
    "hist.unknown_mode": "unknown mode",
    "hist.took": "took {t}",
    # ---- heavy video search
    "scan.title": "Find heavy videos",
    "scan.hint": "Finds large videos and estimates how much space compression would free up. System folders, "
                 "installed games and OneDrive cloud-only files are skipped. Nothing is deleted or changed.",
    "scan.path_ph": "…or a folder of your choice (e.g. D:\\Videos)",
    "scan.min_label": "Files over",
    "scan.min200": "200 MB",
    "scan.min500": "500 MB",
    "scan.min1000": "1 GB",
    "scan.min3000": "3 GB",
    "scan.ev_label": "use Everything",
    "scan.ev_title": "If Everything (voidtools) is installed, search its index: a split second instead of minutes. "
                     "Untick this if Everything doesn't index all your drives.",
    "scan.search": "Search",
    "scan.need_root": "Tick a drive or enter a folder",
    "scan.phase.walk": "Looking for large videos",
    "scan.phase.ev_open": "Opening the Everything index",
    "scan.phase.probe": "Reading video details",
    "scan.method.everything": "Everything index",
    "scan.method.walk": "folder scan",
    "scan.running": "{phase}… Folders scanned: {dirs} · large videos: {cand}",
    "scan.read": "read {n}",
    "scan.error": "Search error: {e}",
    "scan.found": "Videos found: {n}, {size} in total, in {t}{method}. Compressing all of them would free about "
                  "{save}. This is a rough estimate; “Test” gives an exact forecast.",
    "scan.none": "No suitable videos found. Try a lower size threshold or another drive.",
    "scan.stopped": "Search stopped.",
    "scan.ev_tip": "Tip: with the free program {ev}, the search takes seconds instead of {t}. Framewring uses "
                   "its index automatically.",
    "scan.ev_hide": "don't show again",
    "scan.dups": "Also, identical copies of the same videos in different places take up {size} (marked "
                 "“copies: N”). Framewring doesn't delete extra copies: check them and delete them yourself.",
    "scan.cloud": "OneDrive cloud-only files skipped: {n}.",
    "scan.copies": "copies: {n} ({drives})",
    "scan.copies_title": "The same file (name and size) is in several places: deleting the extra copy saves more "
                         "than compressing it",
    "scan.edit": "editing source",
    "scan.edit_title": "Editing codec: usually a source file for a video editor. Compress it only if the editing "
                       "is finished",
    "scan.in_list": "already in list",
    "scan.has_out": "compressed copy exists",
    "scan.v.g": "a lot",
    "scan.v.y": "some",
    "scan.v.m": "little",
    "scan.selected": "Selected: {n}, {size} · frees ≈ {save}",
    "scan.pick_good": "Select worthwhile",
    "scan.pick_all": "All",
    "scan.pick_none": "None",
    "scan.add": "Add to queue ({n})",
    "scan.adding": "Adding files: {n}…",
    "scan.added": "Added to the queue: {n}. Now press “Test” or “Compress all”.",
    "drive.free": "{free} free of {total}",
    "drive.net": "network",
    "drive.removable": "removable",
    "drive.none": "No drives found, enter a folder",
    "drive.home": "Home folder",
    # ---- work phases (backend)
    "phase.compress": "Compressing",
    "phase.save": "Saving the file",
    "phase.save_wait": "Saving the file: another program is holding it (usually an antivirus checking the new "
                       "file, or a player), waiting… {secs} s",
    "phase.finish": "Finishing the file",
    "phase.test_cut": "Test: cutting a clip",
    "phase.test_enc": "Test: compressing the clip",
    "phase.vmaf": "Calculating VMAF (quality score)",
    # ---- job notes (backend)
    "note.av1_lp_low": "Not much free memory for AV1: parallelism lowered to lp={lp} (a bit slower). "
                       "Closing other programs or enlarging the page file helps.",
    "note.mem_retry": "Windows couldn't allocate memory (attempt {n} of 3). Restarted compressing this file.",
    "note.mem_retry_cpu": "Windows couldn't allocate memory (attempt {n} of 3). Restarted compressing this file, "
                          "decoding on the CPU.",
    "note.av1_lp_retry": "Ran out of memory for AV1: restarted with parallelism lp={lp} (slower). "
                         "Closing other programs or enlarging the page file helps.",
    "note.saved_as": "“{out}” is in use by another program (open in a player?), saved as “{alt}”.",
    "note.rename_failed": "Compression finished, but the file couldn't be renamed (another program is using it). "
                          "The result is “{name}”: rename it yourself and remove “.part”.",
    "note.space_tight": "Disk space is tight ({free} GB free): if it runs out, compression will stop.",
    "note.image_subs": "The original has image-based subtitles ({codecs}): MP4 can't carry them. "
                       "If you need them, keep the original.",
    "note.interrupted": "The previous session closed while this file was compressing: it will start over.",
    # ---- errors (backend)
    "err.probe_failed": "ffprobe couldn't read the file",
    "err.no_video": "the file has no video track",
    "err.not_found_path": "Not found: {path}",
    "err.no_ffmpeg": "FFmpeg not found",
    "err.scan_no_roots": "Choose at least one drive or an existing folder",
    "err.scan_running": "A search is already running",
    "err.ffmpeg_code": "ffmpeg exited with code {code}",
    "err.mem3": "Ran out of memory three times. Close other programs and turn on the page file "
                "(see the warning at the top).\n\n{detail}",
    "err.av1_mem": "Not enough memory for AV1 at {res}. Close other programs, enlarge the page file "
                   "or choose H.265.\n\n{detail}",
    "err.same_as_src": "Refused: the output would overwrite the original. Choose another folder.",
    "err.no_space": "Not enough disk space for the output: about {need} GB needed, {free} GB free ({dir}). "
                    "Free up space or choose another “Output folder”.",
    "err.file_gone": "File not found (deleted, moved, or the drive is disconnected).",
    "err.no_result": "the task ended without a result",
    "err.pick_failed": "Couldn't open the file picker ({detail}). Paste the path instead.",
    "api.checking": "Still checking FFmpeg and GPU capabilities, wait a couple of seconds",
    "api.mode_unavailable": "The selected mode isn't available on this computer",
    "api.cant_retry": "This task can't be retried right now",
    "api.unreadable": "Can't read the file: {detail}",
    "api.no_info": "no video details",
    "api.url_denied": "link not allowed",
    "api.open_missing": "File not found (deleted or moved): {path}",
    # ---- native dialogs and console (translated by Python)
    "pick.title_files": "Choose videos",
    "pick.title_folder": "Choose a folder with videos",
    "pick.video": "Videos",
    "pick.all": "All files",
    "native.close_confirm": "Compression is in progress. Stop it and close the program?\n\n"
                            "The file list is saved; the current file will start over next time.",
    "con.window_unavail": " Program window unavailable ({e}), opening in the browser.",
    "con.window_failed": " Program window failed to start ({e}), opening in the browser.",
    "con.dnd_unavail": " drag & drop unavailable: {e}",
    "con.already": "Framewring is already running: {url}  (showing it, a second copy isn't needed)",
    "con.no_port": "No free port in 8765–8799",
    "con.started": " {name} v{ver} running: {url}",
    "con.data": " Data (settings, queue, history): {dir}",
    "con.ffmpeg": " FFmpeg: {path}",
    "con.ffmpeg_missing": "NOT FOUND",
    "con.restored": " Restored the previous session's list, files: {n}.",
    "con.keep_open": " Don't close this window while compression is running.",
    "con.how_quit": " To quit, close the window or press Ctrl+C.",
}

CATALOG = {"ru": RU, "en": EN}

_PARAM = re.compile(r"\{(\w+)\}")


def _fmt_param(lang, v):
    if isinstance(v, dict) and "k" in v:  # вложенное сообщение
        return t(lang, v["k"], **(v.get("p") or {}))
    if isinstance(v, list):
        return " ".join(_fmt_param(lang, x) for x in v)
    if isinstance(v, float):
        return ("%.1f" % v).rstrip("0").rstrip(".")
    return str(v)


def t(lang, key, **p):
    """Перевод ключа. Нет перевода — русский, нет и его — сам ключ."""
    s = CATALOG.get(lang, RU).get(key)
    if s is None:
        s = RU.get(key, key)
    if not p:
        return s
    return _PARAM.sub(lambda m: _fmt_param(lang, p[m.group(1)]) if m.group(1) in p else m.group(0), s)


def text(lang, m):
    """Сообщение из бэкенда ({"k","p"}, список таких или обычная строка) -> текст."""
    if not m:
        return ""
    if isinstance(m, str):
        return m
    if isinstance(m, list):
        return " ".join(x for x in (text(lang, y) for y in m) if x)
    if isinstance(m, dict) and "k" in m:
        return t(lang, m["k"], **(m.get("p") or {}))
    return str(m)


def sys_lang():
    """Язык системы: ru/uk/be/kk -> русский интерфейс, остальное -> английский."""
    try:
        if os.name == "nt":
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return "ru" if lid in (0x19, 0x22, 0x23, 0x3F) else "en"
        import locale
        loc = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG")
               or (locale.getlocale()[0] or ""))
        return "ru" if loc[:2].lower() in ("ru", "uk", "be", "kk") else "en"
    except Exception:
        return "en"
