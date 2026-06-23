# fashion-fabric-bot

MVP-каркас monorepo для Telegram-бота и админки магазина тканей. Проект включает FastAPI backend, PostgreSQL-модели и миграции Alembic, JWT-аутентификацию админки, публичный каталог для Telegram-бота, aiogram 3 scaffold и React + TypeScript + Vite admin frontend.

## Структура проекта

```text
backend/
  app/
    main.py                  # FastAPI app, CORS, routers, /uploads, startup seed
    config.py                # переменные окружения из .env / process env
    database.py              # SQLAlchemy engine/session/Base
    models/                  # Admin, TelegramUser, Fabric, FabricImage, GarmentStyle, Generation
    schemas/                 # Pydantic v2 schemas
    api/routes/              # auth, admin CRUD, public catalog, generations
    services/                # auth, storage, seed, OpenAI/image generation/recommendation
    utils/                   # JWT/password helpers, pagination
  alembic/                   # Alembic env и initial migration
  requirements.txt
  Dockerfile
bot/
  app/                       # aiogram bot scaffold, handlers, API client
  check_token.py             # безопасная проверка TELEGRAM_BOT_TOKEN
  requirements.txt
  Dockerfile
admin-frontend/
  src/                       # React admin app, pages, components, API client
  package.json
  vite.config.ts
  tsconfig.json
  Dockerfile
uploads/
  fabrics/
  garment-styles/
  generations/
  user-photos/
```

## Настройка окружения

Перед запуском создайте локальный файл окружения из примера:

```bash
cp .env.example .env
```

Затем откройте `.env` и замените плейсхолдеры на реальные значения. Не коммитьте `.env`: файл добавлен в `.gitignore`.

Минимально замените:

- `TELEGRAM_BOT_TOKEN=put_token_here` — реальный токен Telegram-бота.
- `OPENAI_API_KEY=put_openai_key_here` — реальный OpenAI API key для GPT-подбора и AI-визуализации.
- `BOT_INTERNAL_TOKEN=change_me_bot_internal_token` — общий внутренний токен backend и bot.
- `JWT_SECRET=replace_with_strong_admin_jwt_secret` — сильный секрет для JWT.
- `INITIAL_ADMIN_PASSWORD=replace_with_strong_admin_password` — безопасный пароль начального администратора.

`APP_ENV=development` подходит для локального запуска. Для `APP_ENV=production`, `prod` или `staging` backend откажется стартовать с пустыми или placeholder-значениями `JWT_SECRET`, `INITIAL_ADMIN_PASSWORD` и `BOT_INTERNAL_TOKEN`.

`MAX_UPLOAD_BYTES` задаёт лимит загрузки в байтах и имеет приоритет над `MAX_UPLOAD_SIZE_MB`, если обе переменные указаны.

### Runtime checklist

Перед запуском Docker/CI/staging проверьте:

- `BOT_INTERNAL_TOKEN` задан одним и тем же значением для backend и bot.
- `JWT_SECRET` и `INITIAL_ADMIN_PASSWORD` заменены на реальные секреты перед production-like запуском.
- `OPENAI_API_KEY`, `OPENAI_MODEL` и `OPENAI_IMAGE_*` заданы для AI-функций, если generation должен работать.
- Frontend получает только `VITE_API_BASE_URL` и `VITE_BACKEND_PUBLIC_URL`; backend secrets не должны попадать в Vite env.
- Backend tests используют отдельную `TEST_DATABASE_URL`; имя тестовой базы должно содержать `test`.

## Required production environment

Для `APP_ENV=production`, `prod` или `staging` сначала подготовьте production/staging `.env` и не используйте demo-плейсхолдеры из `.env.example`.

Обязательные runtime values:

| Переменная | Где используется | Production requirement |
| --- | --- | --- |
| `APP_ENV` | backend | `production`, `prod` или `staging` включает fail-fast проверку unsafe placeholders. |
| `DATABASE_URL` | backend | URL PostgreSQL для runtime базы; не должен указывать на test DB. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Docker Compose Postgres | Замените local defaults перед production-like запуском. |
| `JWT_SECRET` | backend admin auth | Сильный секрет; `change_me` и пустое значение запрещены в production-like режиме. |
| `INITIAL_ADMIN_EMAIL` | backend bootstrap | Email initial admin, создается один раз idempotent bootstrap-логикой. |
| `INITIAL_ADMIN_PASSWORD` | backend bootstrap | Сильный initial password; `admin12345` и пустое значение запрещены в production-like режиме. |
| `BOT_INTERNAL_TOKEN` | backend и bot | Одинаковый strong token в обоих сервисах; placeholder запрещен в production-like backend. |
| `TELEGRAM_BOT_TOKEN` | bot | Реальный token Telegram-бота; placeholder безопасно завершает bot container без запуска polling. |
| `BOT_BACKEND_TIMEOUT_SECONDS`, `BOT_GENERATION_TIMEOUT_SECONDS`, `BOT_USER_PHOTO_TRY_ON_ENABLED` | bot | Обычный backend timeout, увеличенный timeout для user-photo generation upload и отдельный rollout flag для пользовательской фото-примерки. `BOT_USER_PHOTO_TRY_ON_ENABLED=false` по умолчанию скрывает/блокирует user-photo flow в Telegram. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | backend AI/recommendation | Реальный key нужен для GPT-подбора; placeholder оставляет controlled fallback/error. |
| `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_SIZE`, `OPENAI_IMAGE_QUALITY`, `OPENAI_IMAGE_OUTPUT_FORMAT`, `OPENAI_IMAGE_TIMEOUT_SECONDS` | backend image generation | Настройки OpenAI image edit для catalog-style и user-photo try-on; defaults: `gpt-image-1`, `1024x1536`, `medium`, `png`, `120`. |
| `USER_PHOTO_MASK_MODE`, `USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT`, `USER_PHOTO_MASK_MIN_COVERAGE_PERCENT`, `USER_PHOTO_MASK_MAX_COVERAGE_PERCENT`, `USER_PHOTO_MASK_DILATE_PIXELS`, `USER_PHOTO_MASK_DEBUG_SAVE` | backend user-photo try-on | Clothing mask pipeline. Strict clothing-only edits require a valid mask by default. `provided` accepts explicit PNG masks, `mock` is tests/dev only, `provider` is reserved and fails closed until a segmentation provider exists. |
| `USER_PHOTO_PRESERVATION_CHECK_ENABLED`, `USER_PHOTO_PRESERVATION_MAX_MEAN_DELTA`, `USER_PHOTO_PRESERVATION_MAX_CHANGED_PIXEL_PERCENT`, `USER_PHOTO_PRESERVATION_PIXEL_DELTA_THRESHOLD` | backend user-photo try-on | Post-generation preservation guardrail for masked edits. Provider output that changes protected pixels outside the transparent clothing mask fails closed instead of being exposed as a successful result. |
| `UPLOAD_DIR` | backend | Persistent uploads volume/path для fabrics, garment styles, generations, user photos и user-photo masks. |
| `MAX_UPLOAD_BYTES` | backend upload validation | Byte limit, имеет приоритет над `MAX_UPLOAD_SIZE_MB`. |
| `RATE_LIMIT_WINDOW_SECONDS`, `ADMIN_LOGIN_RATE_LIMIT`, `BOT_API_RATE_LIMIT`, `GENERATION_RATE_LIMIT`, `UPLOAD_RATE_LIMIT` | backend abuse guards | Ненулевые scoped limits для admin login, bot API, generation и uploads; `0` используйте только для local debugging. |
| `VITE_API_BASE_URL`, `VITE_BACKEND_PUBLIC_URL` | admin frontend | Единственные frontend env values; не передавайте backend secrets в `VITE_*`. |

## Deployment checklist

Порядок production/staging запуска:

1. Создайте `.env` из `.env.example` и замените все required secrets.
2. Убедитесь, что `APP_ENV` соответствует окружению, а `SEED_DEMO_DATA=false` для production-like режимов.
3. Проверьте, что `BOT_INTERNAL_TOKEN` совпадает в backend и bot.
4. Поднимите PostgreSQL и дождитесь healthcheck `pg_isready`.
5. Примените migrations: Docker backend делает `alembic upgrade head` перед `uvicorn`; при ручном запуске выполните `docker compose --env-file .env run --rm backend alembic upgrade head`.
6. Запустите backend и проверьте `/api/health`; ответ не должен содержать secrets/config values.
7. Запустите admin frontend и убедитесь, что он получает только `VITE_API_BASE_URL` и `VITE_BACKEND_PUBLIC_URL`.
8. Запустите bot только после проверки backend health и совпадения `BOT_INTERNAL_TOKEN`.
9. Перед deploy убедитесь, что GitHub Actions jobs green: `Backend`, `Admin frontend`, `Docker Compose config`, `Whitespace check`, `Bot`.

Runtime diagnostics:

- Backend добавляет `X-Request-ID` в ответы и принимает безопасный входящий `X-Request-ID` для корреляции логов.
- `/api/health` возвращает только `{"status":"ok"}` и не раскрывает secrets.
- Upload limits возвращают controlled `400`/`413`/`415`, rate limits возвращают `429` с `Retry-After`.
- Provider/OpenAI failures не должны попадать наружу как raw traceback.
- User-photo generation может занимать 1–2 минуты; bot использует отдельный `BOT_GENERATION_TIMEOUT_SECONDS` для этого endpoint.

### Fabric image readiness

Для AI-примерки одной записи в таблице `fabric_images` недостаточно: соответствующий файл должен реально существовать в persistent `UPLOAD_DIR`, открываться как изображение и быть достаточно большим для provider input.

Production-like правила:

- Монтируйте persistent storage для backend uploads; на Render staging используйте `UPLOAD_DIR=/var/data/uploads` при подключенном Render Disk.
- Загружайте `main` и `texture` через admin UI/API, а не ручной записью в базу.
- Перед real generation smoke проверьте admin endpoint `GET /api/admin/fabrics/{fabric_id}/image-readiness`.
- `ai_reference_ready=true` означает, что хотя бы `texture` или `main` подходит как reference image; preferred order: `texture`, затем `main` той же ткани.
- Missing/broken/tiny/unsupported images дают controlled validation error; backend не должен подставлять random/default/other fabric.
- Catalog preview image failures должны оставаться non-blocking: бот отправляет текстовую карточку и кнопки, а logs не раскрывают secrets, raw filesystem paths или image bytes/base64.

## Post-merge smoke checks

После merge/deploy выполните короткую проверку:

```bash
docker compose --env-file .env config
docker compose --env-file .env up --build
curl -i http://localhost:8000/api/health
curl -i -H 'X-Request-ID: smoke-test' http://localhost:8000/api/health
```

Затем проверьте вручную:

1. Backend logs не содержат `JWT_SECRET`, `BOT_INTERNAL_TOKEN`, `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, password values, upload bytes/base64.
2. Admin login работает с `INITIAL_ADMIN_EMAIL` и `INITIAL_ADMIN_PASSWORD`.
3. Public catalog route открывается без admin token.
4. Admin frontend не показывает raw backend/provider errors и чистит token на `401`.
5. Bot `/start` отвечает friendly message даже при временно недоступном backend.
6. Generation endpoint с отсутствующим/неверным `X-Bot-Token` возвращает `401`, а частые запросы после лимита получают safe `429`.

Rollback notes:

- Для кода откатитесь к предыдущему green commit/tag и повторите smoke checks.
- Не откатывайте production database вручную без отдельного migration/backup plan.
- Если проблема только в secrets/env, исправьте `.env` и перезапустите сервисы без изменения кода.

## Frontend env для Vite

Admin frontend читает только переменные с префиксом `VITE_`:

- `VITE_API_BASE_URL=http://localhost:8000/api` — базовый URL backend API.
- `VITE_BACKEND_PUBLIC_URL=http://localhost:8000` — публичный URL backend для отображения изображений из `/uploads`.

В Docker Compose эти переменные прокидываются в сервис `admin-frontend`.

## Запуск через Docker Compose

```bash
docker compose --env-file .env up --build
```

Backend Dockerfile запускает `alembic upgrade head` перед стартом `uvicorn`. Если нужно выполнить миграции вручную:

```bash
docker compose --env-file .env run --rm backend alembic upgrade head
```

### Database bootstrap checklist

На первом запуске backend ожидает, что Alembic migrations уже применены. Dockerfile делает это автоматически командой `alembic upgrade head`; при ручном запуске сначала выполните эту команду сами.

Startup bootstrap делает только безопасные idempotent-действия:

- создаёт initial admin, если `INITIAL_ADMIN_EMAIL` ещё отсутствует в таблице `admins`;
- не меняет пароль уже существующего initial admin при повторном старте;
- создаёт demo fabric/style только при `SEED_DEMO_DATA=true`;
- запрещает `SEED_DEMO_DATA=true` для `APP_ENV=production`, `prod` и `staging`;
- логирует bootstrap errors через redaction helper, без DB password/token values.

Для production-like запуска сначала замените `JWT_SECRET`, `INITIAL_ADMIN_PASSWORD` и `BOT_INTERNAL_TOKEN`; backend откажется стартовать с placeholder-значениями до создания admin.

## Swagger и healthcheck

- Swagger UI: http://localhost:8000/docs
- Health endpoint: http://localhost:8000/api/health

Ответ health endpoint:

```json
{"status":"ok"}
```

## Админка

Админка запускается через Vite dev server и доступна по адресу:

- http://localhost:5173

Initial admin создаётся при старте backend, если пользователя ещё нет:

- Email: значение `INITIAL_ADMIN_EMAIL`, по умолчанию `admin@example.com`.
- Password: значение `INITIAL_ADMIN_PASSWORD` из `.env`.

Повторный bootstrap не перезаписывает пароль существующего admin. Чтобы сменить пароль после первого запуска, используйте отдельную admin/service операцию вместо изменения `.env`.

## Как создать ткань

Через админку:

1. Откройте http://localhost:5173.
2. Войдите initial admin-аккаунтом.
3. Перейдите в раздел «Ткани».
4. Нажмите «Добавить ткань».
5. Заполните обязательные поля: `sku`, `name`, `category`, `price_per_meter`, `stock_status`, `description_for_gpt`.

Через API:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin12345"}'

curl -X POST http://localhost:8000/api/admin/fabrics \
  -H 'Authorization: Bearer <TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"sku":"LINEN-001","name":"Лён молочный","category":"лён","price_per_meter":1800,"stock_status":"in_stock","description_for_gpt":"Молочный лён для летних платьев."}'
```

Для публикации ткани нужны `sku`, `name`, `category`, `price_per_meter`, `stock_status`, `description_for_gpt`, а также изображения типов `main` и `texture`.


## Как добавить ткань через админку

1. Откройте http://localhost:5173.
2. Войдите под initial admin (`INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`).
3. Перейдите в раздел «Ткани».
4. Нажмите «Добавить ткань».
5. Заполните обязательные поля карточки ткани.
6. Загрузите главное фото и фото фактуры. На странице создания изображения можно выбрать до сохранения: после сохранения черновика они загрузятся автоматически.
7. Нажмите «Проверить карточку», чтобы увидеть недостающие поля или сообщение «Карточка готова к публикации».
8. При необходимости нажмите «Составить описание карточки». Это помогает подготовить текстовое описание карточки, но не создает ткань, фото или характеристики за администратора.
9. Нажмите «Сохранить черновик» или «Сохранить и опубликовать».
10. Если публикация невозможна, backend вернёт понятную ошибку; после исправления карточки нажмите «Опубликовать».

## Обязательные поля для публикации ткани

- артикул;
- название;
- категория;
- цена за метр;
- наличие;
- главное фото;
- фото фактуры;
- описание для GPT.

## Что уже реализовано

- FastAPI backend с `/api/health`, Swagger, CORS и static serving `/uploads`.
- SQLAlchemy 2.x модели PostgreSQL и initial Alembic migration.
- JWT login `/api/auth/login` и `/api/auth/me`.
- Защищённые `/api/admin/*` endpoints для тканей, фасонов и генераций.
- Public catalog endpoints для опубликованных тканей и фасонов; `/api/catalog/fabrics/recommend` анализирует текстовый запрос, ранжирует только опубликованные ткани из базы и возвращает объяснения подбора.
- Storage service для безопасной загрузки изображений в подпапки `UPLOAD_DIR` и сохранения generated images.
- GPT recommendation fallback и OpenAI image edit integration с controlled failed-state behavior, если AI не настроен.
- Aiogram 3 scaffold бота с командами `/start`, `/catalog`, `/pick`, `/styles`, `/help`.
- React + TypeScript + Vite + Tailwind scaffold админки на русском языке.
- Dockerfile для backend, bot и admin-frontend.

## Продуктовые инварианты каталога

- Ткань — это только запись из базы данных, созданная администратором через web-админку.
- Фото ткани — это только файл, загруженный администратором через upload в админке.
- GPT используется только для анализа пользовательского запроса и подбора подходящих `fabric_id` из опубликованного каталога.
- GPT не создает ткани, не придумывает артикулы, названия, цены, наличие, материалы, фото или карточки тканей.

## Как работает GPT-подбор ткани

- Ткани добавляет только администратор через web-админку: название, артикул, характеристики, цена, наличие, фото ткани, фото фактуры и описание.
- Фото тканей загружаются только через админку; GPT не создает фото, карточки, артикулы, цены или новые материалы.
- Endpoint `POST /api/catalog/fabrics/recommend` принимает текст пользователя, например «Мне нужна ткань для летнего платья на свадьбу, чтобы выглядело дорого, но не ярко».
- Backend извлекает требования (`garment_type`, `occasion`, `desired_style`, `preferred_colors`, `avoid`, `season`, `required_properties`).
- Система ищет только опубликованные ткани из базы (`status="published"`) и отдает приоритет `in_stock`, затем `preorder`; `out_of_stock` не попадает в рекомендации, если есть подходящие доступные варианты.
- При настроенном `OPENAI_API_KEY` GPT анализирует запрос и ранжирует только переданные backend реальные candidate fabrics; backend отбрасывает любые `fabric_id`, которых не было в списке кандидатов. Модель никогда не должна возвращать ткань, которой нет в базе данных.
- Если `OPENAI_API_KEY` пока равен `put_openai_key_here`, используется простой fallback-подбор по ключевым словам и характеристикам; endpoint продолжает возвращать реальные `fabric_id` из каталога.

## Telegram-сценарий выбора ткани

- `/start` регистрирует или обновляет Telegram-пользователя в backend через `POST /api/bot/users/upsert` и показывает меню.
- `/catalog` показывает только опубликованные ткани из public catalog; у каждой карточки есть кнопка «Выбрать эту ткань».
- `/pick` просит описать вещь и случай, вызывает `POST /api/catalog/fabrics/recommend` и показывает 3–5 реальных тканей из опубликованного каталога с причиной подбора и возможным минусом.
- `/styles` показывает опубликованные фасоны из public catalog; у каждого фасона есть кнопка «Выбрать этот фасон».
- `/selected` показывает текущий выбор пользователя: выбранную ткань и выбранный фасон, либо понятные сообщения, если что-то еще не выбрано.
- Выбор ткани сохраняется через `POST /api/bot/users/{telegram_id}/selected-fabric`; выбрать можно только `status=published`.
- Выбор фасона сохраняется через `POST /api/bot/users/{telegram_id}/selected-garment-style`; выбрать можно только опубликованный фасон.
- Фасоны, как и ткани, добавляет только администратор через web-админку; GPT не генерирует фасоны, ткани, карточки или фото.
- GPT только помогает выбрать существующий `fabric_id` из опубликованного каталога тканей.
- Фото тканей и фасонов загружаются только администратором через web-админку; бот использует уже сохраненные URL из backend.


## AI-визуализация ткани на фасоне

- Администратор должен загрузить texture image ткани через карточку ткани в web-админке.
- Администратор должен загрузить base image фасона через карточку фасона; mask image фасона опциональна.
- Пользователь выбирает реальную опубликованную ткань и реальный опубликованный фасон в Telegram.
- Когда ткань и фасон выбраны, бот показывает кнопку «Создать визуализацию».
- Backend вызывает `POST /api/generations/catalog-style`, использует только выбранные `selected_fabric_id` и `selected_garment_style_id`, создает запись `Generation` и сохраняет результат в `/uploads/generations`.
- Backend использует OpenAI image edit с base image фасона, texture image ткани и опциональной mask image.
- Если `OPENAI_API_KEY` не настроен или равен `put_openai_key_here`, генерация не выполняется, запись получает `status=failed`, а приложение и бот не падают.
- AI-визуализация показывает примерный внешний вид ткани на фасоне и может отличаться от реального изделия.

## AI-примерка ткани на пользовательском фото

- Telegram user-facing flow защищен отдельным bot-side rollout flag `BOT_USER_PHOTO_TRY_ON_ENABLED=false` по умолчанию. Пока нет настоящей clothing segmentation или operator/user-provided mask workflow, bot не показывает кнопку примерки на пользовательском фото и не отправляет фото в backend из старых callback/state.
- Пользователь выбирает опубликованную ткань в Telegram и отправляет одно безопасное фото, где видна одежда.
- Backend вызывает `POST /api/generations/user-photo`, сохраняет user photo в `UPLOAD_DIR/user-photos`, применяет texture image выбранной ткани через OpenAI image edit и сохраняет результат в `UPLOAD_DIR/generations`.
- Prompt-only user-photo edit может изменить лицо, руки, фон, предметы и композицию, поэтому он не считается production-quality clothing-only примеркой.
- По умолчанию `USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT=true`: без валидной clothing mask backend возвращает controlled error до OpenAI и не запускает no-mask generation под видом точечной замены ткани.
- `USER_PHOTO_MASK_MODE=off` является legacy/dev режимом. No-mask edit можно разрешить только явным `USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT=false`, понимая, что strict preservation не гарантируется.
- В режиме `USER_PHOTO_MASK_MODE=provided` backend требует явную PNG mask, совпадающую по размерам с user photo; прозрачная область mask считается editable clothing region. Без mask режим fails closed до OpenAI. Валидная mask сохраняется в `UPLOAD_DIR/user-photo-masks` и `Generation.mask_image_url`.
- В режиме `USER_PHOTO_MASK_MODE=mock` backend генерирует простую dev/test mask для проверки pipeline. Не используйте `mock` как production segmentation.
- `USER_PHOTO_MASK_MODE=provider` зарезервирован для будущего segmentation provider и сейчас возвращает controlled error `Clothing mask provider is not configured yet.` No silent fallback to no-mask is allowed.
- Mask validation rejects missing, broken, non-PNG, non-alpha, wrong-size, empty, tiny, full-image and excessive-coverage masks without exposing absolute filesystem paths.
- Для masked user-photo edits backend после ответа provider проверяет protected-region drift вне прозрачной clothing mask. Если output меняет лицо, руки, фон, силуэт или другие protected pixels сильнее порогов `USER_PHOTO_PRESERVATION_*`, generation получает `status="failed"`, а provider output не сохраняется как successful `result_image_url`.
- User-photo generation всегда получает явный `fabric_id` из выбора пользователя и использует только reference image этой ткани: сначала `texture`, затем `main`, иначе controlled error. Случайная или fallback-ткань не подставляется.
- Для staging/production DB-записей с `/uploads/...` недостаточно: соответствующие файлы ткани должны реально существовать в persistent `UPLOAD_DIR`. Если texture-файл выбранной ткани отсутствует, backend пробует `main` этой же ткани; если usable reference image нет, generation fails before OpenAI by design.
- Prompt формулируется как image edit / clothing-only fabric replacement: сохранить лицо, тело, позу, фон, освещение, предметы и композицию, меняя только материал видимой одежды.
- Bot использует отдельный длинный timeout `BOT_GENERATION_TIMEOUT_SECONDS`, потому что real image generation может занимать 1–2 минуты.
- Успешная masked генерация получает `status="completed"` и `result_image_url` только после preservation guardrail pass; bot отправляет generated image пользователю только для completed results.
- Ошибки провайдера, timeout, отсутствующий ключ и validation failures получают controlled messages без raw traceback/provider details, без upload bytes/base64 и без secret values.
- Missing/wrong `X-Bot-Token` отклоняется до создания записи. После успешной bot-auth проверки failed attempts сохраняются в `generations`, чтобы admin мог видеть failures.
- Используйте только synthetic или явно разрешенные тестовые фото для smoke; не отправляйте документы, интимные фото или фото других людей без согласия.

## Что пока является заглушкой

- Полноценная OpenAI-логика описаний и проверки карточки через модель.
- История пользовательских результатов в Telegram-боте.
- Продвинутый роутинг/UX админки и production-сборка frontend.

Расширение OpenAI text workflows и история результатов будут следующими шагами разработки.

## Поведение без OPENAI_API_KEY

Если `OPENAI_API_KEY` пустой или равен `put_openai_key_here`, backend стартует нормально. AI-функции и endpoints возвращают понятную ошибку конфигурации, а generation endpoints создают запись со `status="failed"` и `error_message`, не роняя приложение. Для real image generation также проверьте `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_SIZE`, `OPENAI_IMAGE_QUALITY`, `OPENAI_IMAGE_OUTPUT_FORMAT` и `OPENAI_IMAGE_TIMEOUT_SECONDS`.

## Поведение без TELEGRAM_BOT_TOKEN

Если `TELEGRAM_BOT_TOKEN` пустой или равен `put_token_here`, `bot/check_token.py` печатает понятное сообщение и завершает контейнер с кодом `0`. Остальные сервисы Docker Compose продолжают работать.


## Проверка билда через GitHub Actions

Проект содержит workflow `CI`, который проверяет backend, admin frontend и Docker Compose config прямо в GitHub.

Чтобы запустить проверку вручную:

1. Откройте вкладку **Actions** в репозитории GitHub.
2. В списке workflows выберите **CI**.
3. Нажмите **Run workflow**.
4. Выберите нужную ветку и подтвердите запуск.
5. Дождитесь результата jobs `Backend`, `Admin frontend` и `Docker Compose config`.
6. Если проверка упала, откройте failed job и разверните шаг с ошибкой: там будут логи установки зависимостей, TypeScript build, Alembic migration или Docker Compose validation.

Workflow также запускается автоматически на `pull_request` и на `push` в `main`.

## Автоматические тесты

GitHub Actions в job `Backend` поднимает PostgreSQL service container с базой `fashion_bot_test`, устанавливает зависимости backend, применяет Alembic migrations и запускает backend API tests командой:

```bash
cd backend
pytest -q
```

Тесты проверяют основной сценарий админки тканей: login initial admin, создание ткани, проверку карточки, загрузку `main` и `texture` изображений, публикацию и появление ткани в public catalog.

Для локального запуска нужен доступный PostgreSQL и отдельная тестовая база. Тесты используют `TEST_DATABASE_URL` и откажутся запускаться, если имя базы не содержит `test`.

```bash
cd backend
export TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fashion_bot_test
pytest -q
```

Pytest применяет Alembic migrations к тестовой базе перед запуском и очищает таблицы между тестами.

## Следующие шаги разработки

1. Расширить OpenAI text workflows для описаний и проверки карточек.
2. Улучшить UX замены уже загруженных изображений ткани и фасонов.
3. Добавить историю пользовательских generation results в Telegram.
4. Расширить покрытие API и добавить frontend component tests.
5. Подготовить production frontend build и reverse proxy.
