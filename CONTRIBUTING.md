**English** · [Русский](#русский)

# Contributing

Thanks for your interest in Framewring! Issues and pull requests are welcome in **English or Russian**.

## Bug reports

The easiest way: click **🐞 Report a bug** in the app header — it opens the **Bug report** form with the version, install type,
Windows version, graphics cards, FFmpeg version and mode already filled in, and **📂 Show the log** opens the folder with the log.
Or use the form in [Issues](https://github.com/remrem23/framewring/issues/new/choose) directly. The most useful things to include:
- Framewring version (in the window title / header) and how you run it (installer, portable, source);
- Windows version, GPU model and driver version, the mode and quality you used;
- FFmpeg version (shown in the app header; for the exe also in `ffmpeg\README.txt` in the program folder);
- `framewring.log` from the data folder: `%APPDATA%\Framewring` (installed) or `data\` next to `Framewring.exe` (portable).
  When running from source, copy the console output instead.
  The log contains paths to your videos — remove anything you don't want to share.

## Feature requests

Use the **Feature request** form. Check [ROADMAP.md](ROADMAP.md) first — the idea may already be planned.

## Code

- The app is `app.py` (~2,900 lines) plus the interface strings in `i18n.py` and `locales/`, using only the Python standard
  library (pywebview is optional). Please keep it that way: no new required dependencies. Source mode supports Python 3.8+.
- Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first.
- English and Russian strings live in `i18n.py`, other languages in `locales/<code>.py`. Add new strings to `i18n.py` in English and Russian; missing translations fall back to English. Translation fixes and new languages are very welcome.
- Never risk user files: originals are read-only; outputs must not overwrite originals or unrelated files.
- Test on real videos, including odd ones (VFR phone recordings, interlaced `.mts`, MKV with subtitles), and on a GPU and a CPU mode if you can.
- Building the exe and installer: [packaging/](packaging/) (`build.py`, then `release.py`).
- Contributions are accepted under the project license, [GNU GPL v3](LICENSE).

Security issues: see [SECURITY.md](SECURITY.md) — please do not report them publicly.

---

<a id="русский"></a>
## Русский

**Как помочь проекту**

Спасибо за интерес к Framewring! Issues и pull request'ы принимаются **на русском или английском**.

### Сообщения об ошибках

Проще всего — кнопка **«🐞 Сообщить об ошибке»** в шапке программы: она открывает форму **Bug report**, где уже заполнены версия,
способ установки, версия Windows, видеокарты, версия FFmpeg и режим, а **«📂 Показать журнал»** открывает папку с журналом.
Или открой форму в [Issues](https://github.com/remrem23/framewring/issues/new/choose) сам. Самое полезное:
- версия Framewring (в заголовке окна / шапке) и способ запуска (установщик, портабл, исходники);
- версия Windows, модель видеокарты и версия драйвера, выбранные режим и качество;
- версия FFmpeg (видна в шапке программы; у exe-версии — ещё и в `ffmpeg\README.txt` в папке программы);
- `framewring.log` из папки данных: `%APPDATA%\Framewring` (установленная) или `data\` рядом с `Framewring.exe` (портабл).
  При запуске из исходников вместо журнала скопируй вывод консоли.
  В журнале есть пути к твоим видео — убери то, чем не хочешь делиться.

### Пожелания

Используй форму **Feature request**. Сначала загляни в [ROADMAP.md](ROADMAP.md#русский) — возможно, это уже в планах.

### Код

- Программа — это `app.py` (~2900 строк) плюс строки интерфейса в `i18n.py` и `locales/`; только стандартная библиотека
  Python (pywebview — по желанию). Пожалуйста, без новых обязательных зависимостей. Запуск из исходников поддерживает Python 3.8+.
- Сначала прочитай [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#русский).
- Английские и русские строки — в `i18n.py`, остальные языки — в `locales/<код>.py`. Новые строки добавляй в `i18n.py` на английском и русском; без перевода показывается английский. Исправления переводов и новые языки очень приветствуются.
- Никакого риска для файлов пользователя: оригиналы только читаются; результат не должен затирать оригиналы или чужие файлы.
- Проверяй на настоящих видео, в том числе странных (VFR с телефона, черезстрочные `.mts`, MKV с субтитрами), и, если можешь, на видеокарте и процессоре.
- Сборка exe и установщика: [packaging/](packaging/) (`build.py`, затем `release.py`).
- Вклад принимается под лицензией проекта, [GNU GPL v3](LICENSE).

Уязвимости: см. [SECURITY.md](SECURITY.md#русский) — пожалуйста, не публикуй их открыто.
