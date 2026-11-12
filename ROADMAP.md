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

## Road to 1.0

1.0 is about being **reliable on other people's computers** and finishing the main promise — actually freeing the space.
New big features wait until after 1.0.

| Version | What's in it |
|---|---|
| **0.9.2** | “Thorough” speed for *CPU · AV1* uses SVT-AV1 preset 4 ([#1](https://github.com/remrem23/framewring/issues/1)); history and queue are saved with backup copies and restored automatically if a file gets damaged; leftover `.part.mp4` files from a crash are cleaned up; installer and update tests run in Windows Sandbox. |
| **0.9.3** | Each finished file is verified (it opens, duration matches, no broken frames); a **Move originals to Recycle Bin** button for verified files, with a confirmation and the total space it frees (never a permanent delete); a short first-run hint; history export/import; install via `winget`. |
| **1.0.0-rc1** | Release candidate for testers (marked as pre-release, so the built-in updater doesn't offer it to everyone). |
| **1.0.0** | When the criteria below are met. |

**Also before 1.0:** code signing (applying to SignPath Foundation for open-source projects) so SmartScreen stops warning;
every release checked on VirusTotal; builds made by GitHub Actions; card payments on the support page (Ko-fi).

**1.0 is released when:**
- two weeks pass without a critical bug (damaged or lost files, the app won't start);
- it has been tested on at least 5 different setups, including Windows 10, a PC without Everything, AMD Radeon RX 6000/7000 and Intel graphics;
- the built-in update has worked for real users;
- the release is clean on VirusTotal, and signing is done or at least applied for.

**Help wanted:** if you have Windows 10, an AMD Radeon or Intel graphics, run **Test (2 min)** on a couple of videos
and post the result in [Issues](https://github.com/remrem23/framewring/issues) — it helps a lot.

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

### Путь к 1.0

1.0 — это **надёжность на чужих компьютерах** и выполненное до конца главное обещание: реально освобождать место.
Новые большие функции — после 1.0.

| Версия | Что входит |
|---|---|
| **0.9.2** | Скорость «Тщательно» для «Процессор · AV1» — пресет 4 у SVT-AV1 ([#1](https://github.com/remrem23/framewring/issues/1)); история и очередь сохраняются с резервными копиями и сами восстанавливаются при повреждении файла; уборка оставшихся после сбоя `.part.mp4`; проверка установщика и обновлений в «Песочнице Windows». |
| **0.9.3** | Проверка каждого готового файла (открывается, длительность совпадает, нет битых кадров); кнопка **«Удалить оригиналы в корзину»** для проверенных файлов — с подтверждением и итогом, сколько места освободится (никогда не удаляет насовсем); короткая подсказка при первом запуске; экспорт и импорт истории; установка через `winget`. |
| **1.0.0-rc1** | Кандидат в релиз для тестеров (помечен как предварительный, поэтому встроенное обновление не предлагает его всем). |
| **1.0.0** | Когда выполнены условия ниже. |

**Ещё до 1.0:** цифровая подпись (заявка в SignPath Foundation для открытых проектов), чтобы SmartScreen перестал предупреждать;
проверка каждого релиза на VirusTotal; сборка через GitHub Actions; оплата картой на странице поддержки (Ko-fi).

**1.0 выходит, когда:**
- две недели без критических ошибок (порча или потеря файлов, программа не запускается);
- проверено минимум на 5 разных конфигурациях, включая Windows 10, компьютер без Everything, AMD Radeon RX 6000/7000 и графику Intel;
- встроенное обновление сработало у реальных пользователей;
- релиз чистый на VirusTotal, а подпись получена или хотя бы подана заявка.

**Нужна помощь:** если у тебя Windows 10, видеокарта AMD Radeon или графика Intel — запусти **«Тест на 2 мин»** на паре видео
и напиши результат в [Issues](https://github.com/remrem23/framewring/issues). Это очень поможет.

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
