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

## Planned

- **Auto quality:** pick the compression level for a target VMAF (like ab-av1).
- Resume an interrupted file from where it stopped (it currently starts over).
- Explicit HDR support.
- Testing and builds for macOS / Linux.
- Card payments on the support page (Ko-fi).
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

### В планах

- **Авто-качество:** подбор уровня сжатия под целевой VMAF (как ab-av1).
- Продолжение прерванного файла с места остановки (сейчас — с начала).
- Явная поддержка HDR.
- Тестирование и сборки для macOS / Linux.
- Оплата картой на странице поддержки (Ko-fi).
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
