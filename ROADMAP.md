**English** · [Русский](#русский)

# Roadmap

Ideas and requests are welcome in [Issues](https://github.com/remrem23/framewring/issues).

## Done in 0.9.0

- Windows installer and portable zip with FFmpeg bundled, own app window (WebView2).
- **English interface** (RU | EN switch).
- Everything is optional: without it the multi-threaded folder walk is used automatically.

## Planned

- **AMD (AMF)** and **Intel (QSV)** GPU encoding — owners of those cards can only use the CPU for now.
- **Auto quality:** pick the compression level for a target VMAF (like ab-av1).
- Resume an interrupted file from where it stopped (it currently starts over).
- Explicit HDR support.
- Testing and builds for macOS / Linux.
- Card payments on the support page (Ko-fi).
- Smaller download (a leaner FFmpeg build).

## Known limitations

- Tested mainly on one machine (Windows 11, RTX 5070 Ti). Reports from other hardware are very welcome.
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
- **Английский интерфейс** (переключатель RU | EN).
- Everything необязателен: без него автоматически работает многопоточный обход папок.

### В планах

- Видеокарты **AMD (AMF)** и **Intel (QSV)** — сейчас их владельцам доступен только процессор.
- **Авто-качество:** подбор уровня сжатия под целевой VMAF (как ab-av1).
- Продолжение прерванного файла с места остановки (сейчас — с начала).
- Явная поддержка HDR.
- Тестирование и сборки для macOS / Linux.
- Оплата картой на странице поддержки (Ko-fi).
- Меньший размер загрузки (более компактная сборка FFmpeg).

### Известные ограничения

- Проверено в основном на одной машине (Windows 11, RTX 5070 Ti). Отчёты с другого железа очень помогут.
- Оценка экономии в поиске рассчитана на H.265 «Баланс»; точный прогноз даёт «Тест».
- В поиске пропускаются папки с именем `games` (чтобы не трогать установленные игры) — видео в такой папке не найдутся.
- При выключенном файле подкачки возможны сбои памяти (программа повторяет и предупреждает).
- Субтитры-картинки (PGS) в MP4 не помещаются и отбрасываются с предупреждением.
- У программы пока нет цифровой подписи, поэтому SmartScreen предупреждает при первом запуске.
