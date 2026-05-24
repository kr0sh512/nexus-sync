# Client

Основная суть - кидает на известный по ip/домену сервак свой ключ и базовую информацию о себе: hostname, местное время (что-то ещё?)

В ответ может получить как простое "ок", так и команду для выполнения

Запросы на сервер будет кидать с некоторой частотой, постепенно возрастающей, но резко снижающейся при получении команды в ответе (вдруг надо ещё что-то выполнить)

Есть установление нижнего предела на частоту (условная 1/минута)

Пример работы

```
...
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, 200
*waits 45s*
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, 200
*waits 46s*
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, execute "ip a", 200
client: *execute*
client -> server: hello!, i'm $(hostname), uuid= , ts=, stdout= , stderr= , ...
*waits 23s*
```

Возможно нужна доп инфа о работе команды (код ошибки как минимум)

+ возможно на клиенте стоит ограничить набор допустимых команд
+ стоит явно задуматься о шифровании/идентификации сервера

## Разрешённые команды

Клиент исполняет только локально разрешённые command presets. Базовая
настройка задаётся переменной окружения `NEXUS_SYNC_ALLOWED_COMMANDS`.

Примеры:

```bash
NEXUS_SYNC_ALLOWED_COMMANDS=hostname,network_interfaces
NEXUS_SYNC_ALLOWED_COMMANDS=full_access
```

`full_access` означает доступ ко всем локально зарегистрированным presets. Это
не разрешает выполнение произвольных shell-строк от сервера.
