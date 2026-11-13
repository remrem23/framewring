**English** · [Русский](#русский)

# Security policy

## Supported versions

Only the [latest release](https://github.com/remrem23/framewring/releases/latest) receives fixes.

## Reporting a vulnerability

Please **do not** describe vulnerabilities in public issues.
Use GitHub's private reporting: the **Security** tab of this repository → **Report a vulnerability**.
If that is not available, open an issue saying only that you have a security report, and a private channel will be arranged.

Reports in English or Russian are welcome. You can expect a first answer within a week.

Relevant areas include:
- the local HTTP server (`127.0.0.1`, token, Host check) — for example, another program or a web page controlling Framewring;
- anything that could overwrite or delete a user's files;
- the build and release process (installer, portable zip, bundled FFmpeg);
- the update check and one-click update (download from the GitHub release, SHA-256 verification against `SHA256SUMS.txt`).

## Fake copies and payment details

The only official page of the program is **[github.com/remrem23/framewring](https://github.com/remrem23/framewring)**.
Official payment details exist only on [DONATE.md](DONATE.md) in this repository — the program itself contains no wallet addresses.
If you find a copy of Framewring distributed elsewhere, especially one showing other payment details, please report it.

Verify downloads with `SHA256SUMS.txt` from the release (`Get-FileHash <file>` in PowerShell).

Releases after 0.9.3 are built by GitHub Actions from the public source code. You can check that a file was built there
from this repository: `gh attestation verify <file> -R remrem23/framewring` (needs the GitHub CLI).

---

<a id="русский"></a>
## Русский

**Политика безопасности**

### Поддерживаемые версии

Исправления выходят только для [последней версии](https://github.com/remrem23/framewring/releases/latest).

### Как сообщить об уязвимости

Пожалуйста, **не** описывай уязвимости в открытых Issues.
Используй закрытый канал GitHub: вкладка **Security** этого репозитория → **Report a vulnerability**.
Если он недоступен, создай Issue только с фразой, что у тебя есть сообщение о безопасности, — договоримся о закрытом канале.

Можно писать на русском или английском. Первый ответ — в течение недели.

Важные области:
- локальный HTTP-сервер (`127.0.0.1`, токен, проверка Host) — например, если другая программа или веб-страница может управлять Framewring;
- всё, что может перезаписать или удалить файлы пользователя;
- сборка и выпуск (установщик, портабл-архив, FFmpeg в комплекте);
- проверка и установка обновлений (скачивание из релиза на GitHub, сверка SHA-256 с `SHA256SUMS.txt`).

### Поддельные копии и реквизиты

Официальная страница программы — только **[github.com/remrem23/framewring](https://github.com/remrem23/framewring)**.
Официальные реквизиты есть только в [DONATE.md](DONATE.md#русский) этого репозитория — в самой программе адресов кошельков нет.
Если встретишь копию Framewring в другом месте, особенно с другими реквизитами, — сообщи, пожалуйста.

Проверяй загрузки по `SHA256SUMS.txt` из релиза (`Get-FileHash <файл>` в PowerShell).

Релизы после 0.9.3 собирает GitHub Actions из открытого кода. Проверить, что файл собран там и из этого репозитория:
`gh attestation verify <файл> -R remrem23/framewring` (нужен GitHub CLI).
