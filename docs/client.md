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

Клиент исполняет только команды, описанные в локальном YAML config-файле.
Серверу отправляются только `name` и `description`; поле `cmd` остаётся только
на клиенте и не управляется сервером.

Пример:

```yaml
server_url: "http://127.0.0.1:5852"
client_id: "linux-client"
client_token: "change-me-client-token"
allowed_commands:
  - name: hostname
    description: "Get the hostname of the client machine"
    cmd: "hostname"
  - name: network_interfaces
    description: "Get network interface information"
    cmd: "ip addr show"
logging_level: "INFO"
```

Файл ищется как `nexus.yml`/`nexus.yaml` в текущей директории, затем в
`$XDG_CONFIG_HOME`, затем в `~/.config`, затем как
`~/.config/nexus/config.yml`/`.yaml`.
