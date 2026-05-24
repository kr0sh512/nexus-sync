# API contract

## Transport

- Протокол: HTTPS.
- Формат тела запроса и ответа: JSON.
- Префикс API: `/api/v1`.
- Формат времени: RFC 3339 / ISO 8601, например `2026-05-24T13:20:30Z`.
- Авторизация клиента: bearer token в заголовке `Authorization`.

Пример заголовков:

```http
Content-Type: application/json
Authorization: Bearer <client-token>
```

## Client heartbeat

### `POST /api/v1/client/heartbeat`

Клиент вызывает эту ручку на каждом polling tick. Одна и та же ручка
используется для трёх сценариев:

- сообщение "я жив";
- регулярное обновление состояния;
- отправка результата последней завершённой команды.

### Request

```json
{
  "client_id": "macbook-pro-01",
  "observed_at": "2026-05-24T13:20:30Z",
  "client": {
    "hostname": "macbook-pro.local",
    "platform": "darwin",
    "version": "0.1.0"
  },
  "state": {
    "local_time": "2026-05-24T16:20:30+03:00",
    "uptime_seconds": 1200
  },
  "last_command_result": null
}
```

Поля:

- `client_id` - стабильный идентификатор, заданный при настройке клиента. Он не
  должен меняться при каждом рестарте.
- `observed_at` - момент, когда клиент подготовил payload.
- `client.hostname` - текущий hostname машины.
- `client.platform` - платформа клиента. Желательно использовать названия,
  близкие к Python/platform: `linux`, `darwin`, `windows`.
- `client.version` - версия nexus-sync client.
- `state` - намеренно маленький объект. Может быть сюда позже можно добавить IP,
  disk usage, memory, battery status и другие метрики.
- `last_command_result` - `null`, если клиенту нечего нового сообщать о
  выполнении команды.

### Request with command result

```json
{
  "client_id": "macbook-pro-01",
  "observed_at": "2026-05-24T13:21:05Z",
  "client": {
    "hostname": "macbook-pro.local",
    "platform": "darwin",
    "version": "0.1.0"
  },
  "state": {
    "local_time": "2026-05-24T16:21:05+03:00",
    "uptime_seconds": 1235
  },
  "last_command_result": {
    "command_id": "cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
    "status": "succeeded",
    "started_at": "2026-05-24T13:20:35Z",
    "finished_at": "2026-05-24T13:20:36Z",
    "return_code": 0,
    "stdout": "lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384\n",
    "stderr": ""
  }
}
```

Поля результата:

- `command_id` должен совпадать с id команды, которую сервер ранее вернул
  клиенту.
- `status` принимает одно из значений: `succeeded`, `failed`, `timed_out`,
  `rejected`.
- `return_code` - exit code процесса, если процесс был запущен. Для
  `timed_out` или `rejected` поле может быть `null`, если финального exit code
  нет.
- `stdout` и `stderr` клиент должен ограничивать по размеру перед отправкой.
  Конкретный лимит байт в этом контракте пока не фиксируется.

### Response without command

```json
{
  "status": "ok",
  "server_time": "2026-05-24T13:20:30Z",
  "next_poll_after_seconds": 60,
  "command": null
}
```

### Response with command

```json
{
  "status": "ok",
  "server_time": "2026-05-24T13:20:30Z",
  "next_poll_after_seconds": 10,
  "command": {
    "id": "cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
    "kind": "exec",
    "name": "network_interfaces",
    "args": {},
    "timeout_seconds": 30
  }
}
```

Поля команды:

- `id` генерируется сервером и должен быть уникальным.
- `kind` описывает тип executor. Пока определён только `exec`.
- `name` - имя command preset.
- `args` содержит аргументы, специфичные для конкретного preset.
- `timeout_seconds` - максимальное время выполнения, которое сервер допускает
  для этой команды.

Клиент обязан выполнять только те команды, которые он знает и локально
разрешает. Неизвестные или запрещённые команды нужно возвращать как `rejected`.

## Command lifecycle

Жизненный цикл команды:

1. `pending`: команда создана на сервере и ещё не доставлена клиенту.
2. `delivered`: команда была возвращена клиенту в heartbeat response.
3. `succeeded`: клиент сообщил об успешном выполнении.
4. `failed`: клиент сообщил об ошибке выполнения.
5. `timed_out`: клиент сообщил о timeout.
6. `rejected`: клиент отказался выполнять команду.

Терминальные статусы: `succeeded`, `failed`, `timed_out`, `rejected`.

## HTTP statuses

Heartbeat endpoint должен использовать такие HTTP-статусы:

- `200 OK`: heartbeat принят; тело ответа соответствует контракту выше.
- `400 Bad Request`: некорректный JSON или невалидные значения полей.
- `401 Unauthorized`: bearer token отсутствует или невалиден.
- `403 Forbidden`: token валиден, но не имеет права действовать как этот
  `client_id`.
- `409 Conflict`: результат ссылается на неизвестную, уже терминальную или
  несовместимую команду.
- `429 Too Many Requests`: клиент опрашивает сервер слишком часто.
- `500 Internal Server Error`: неожиданная ошибка сервера.

Состояние выполнения команды выражается полями в JSON, а не HTTP-ошибками.
Например, команда с exit code `1` всё равно отправляется через успешный
heartbeat request.

## Polling rules

Ответ сервера содержит `next_poll_after_seconds`.

Поведение:

- обычный polling interval без команды: 60 секунд;
- polling interval после получения команды: 10 секунд;
- клиентский минимальный interval: 5 секунд;
- клиентский максимальный interval: 300 секунд.

Клиент должен воспринимать значение сервера как рекомендацию и зажимать его в
локальные min/max границы.

## Security constraints

Необходимо соблюдать эти ограничения:

- не выполнять произвольные shell-строки, полученные от сервера;
- выполнять только локально известные command presets;
- требовать bearer token для клиентских endpoint'ов;
- включать `command_id` в каждый результат, чтобы не было неоднозначного
  сопоставления;
- хранить command output как логи, а не как доверенные управляющие данные;
- ограничивать размер command output перед отправкой на сервер;
- выполнять каждую команду с timeout.

Эти ограничения намеренно являются частью контракта, потому что проект
занимается удалённым управлением машинами. Дешевле строить первую реализацию
вокруг них, чем добавлять их задним числом.
