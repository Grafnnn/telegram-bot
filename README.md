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
    services/                # auth, storage, seed, OpenAI/image/recommendation stubs
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
- `OPENAI_API_KEY=put_openai_key_here` — реальный OpenAI API key, когда будете подключать AI.
- `BOT_INTERNAL_TOKEN=change_me_bot_internal_token` — общий внутренний токен backend и bot.
- `JWT_SECRET=replace_with_strong_admin_jwt_secret` — сильный секрет для JWT.
- `INITIAL_ADMIN_PASSWORD=replace_with_strong_admin_password` — безопасный пароль начального администратора.

`APP_ENV=development` подходит для локального запуска. Для `APP_ENV=production`, `prod` или `staging` backend откажется стартовать с пустыми или placeholder-значениями `JWT_SECRET`, `INITIAL_ADMIN_PASSWORD` и `BOT_INTERNAL_TOKEN`.

`MAX_UPLOAD_BYTES` задаёт лимит загрузки в байтах и имеет приоритет над `MAX_UPLOAD_SIZE_MB`, если обе переменные указаны.

### Runtime checklist

Перед запуском Docker/CI/staging проверьте:

- `BOT_INTERNAL_TOKEN` задан одним и тем же значением для backend и bot.
- `JWT_SECRET` и `INITIAL_ADMIN_PASSWORD` заменены на реальные секреты перед production-like запуском.
- `OPENAI_API_KEY` и опциональный `OPENAI_MODEL` заданы для AI-функций.
- Frontend получает только `VITE_API_BASE_URL` и `VITE_BACKEND_PUBLIC_URL`; backend secrets не должны попадать в Vite env.
- Backend tests используют отдельную `TEST_DATABASE_URL`; имя тестовой базы должно содержать `test`.

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
- Storage service для безопасной загрузки изображений в подпапки `UPLOAD_DIR`.
- Заглушки AI/recommendation/image generation с правильными интерфейсами.
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
- Фото тканей загружаются только через админку; GPT не создает фото, карточки, цены или новые материалы.
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
- Если `OPENAI_API_KEY` не настроен или равен `put_openai_key_here`, генерация не выполняется, запись получает `status=failed`, а приложение и бот не падают.
- AI-визуализация показывает примерный внешний вид ткани на фасоне и может отличаться от реального изделия.

## Что пока является заглушкой

- Полноценная OpenAI-логика описаний, проверки карточки через модель и image generation.
- История пользовательских результатов в Telegram-боте.
- Продвинутый роутинг/UX админки и production-сборка frontend.

Полноценная OpenAI-логика будет следующим шагом разработки.

## Поведение без OPENAI_API_KEY

Если `OPENAI_API_KEY` пустой или равен `put_openai_key_here`, backend стартует нормально. AI-функции и endpoints возвращают понятную ошибку конфигурации, а generation endpoints создают запись со `status="failed"` и `error_message`, не роняя приложение.

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

1. Подключить реальные OpenAI image/text workflows.
2. Улучшить UX замены уже загруженных изображений ткани и фасонов.
3. Расширить Telegram-сценарии выбора ткани, фасона и пользовательского фото.
4. Расширить покрытие API и добавить frontend component tests.
5. Подготовить production frontend build и reverse proxy.
