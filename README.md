# Fabric Telegram Bot

FastAPI backend and aiogram bot for selecting existing published fabrics from a catalog.

## Run locally

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

For the Telegram bot:

```bash
export TELEGRAM_BOT_TOKEN=...
export BACKEND_URL=http://localhost:8000
export BACKEND_PUBLIC_URL=http://localhost:8000
python -m bot.app.main
```

`BACKEND_PUBLIC_URL` is used for public links to uploaded images. If an image path starts with `/uploads`, the bot builds the full image URL from `BACKEND_PUBLIC_URL`.

## Telegram-сценарий выбора ткани

1. `/start` создает или обновляет Telegram-пользователя в backend через `POST /api/bot/users/upsert` и показывает меню:
   - «Выбрать ткань из каталога»;
   - «Подобрать ткань по описанию»;
   - «Моя выбранная ткань»;
   - «Помощь».
2. `/catalog` вызывает `GET /api/catalog/fabrics` и показывает опубликованные ткани по карточкам. В карточке есть фото при наличии main image, название, категория, цвет, цена, наличие, краткое описание и кнопка «Выбрать эту ткань».
3. `/pick` спрашивает текстовое описание задачи, затем вызывает `POST /api/catalog/fabrics/recommend` и показывает 3–5 рекомендаций из реального опубликованного каталога. У каждой рекомендации есть кнопка «Выбрать эту ткань».
4. `/selected` вызывает `GET /api/bot/users/{telegram_id}/selected-fabric` и показывает выбранную ткань. Если пользователь еще ничего не выбрал, бот отвечает: «Вы пока не выбрали ткань.»
5. Выбор ткани из каталога или рекомендаций сохраняется через `POST /api/bot/users/{telegram_id}/selected-fabric` в `telegram_users.selected_fabric_id`.
6. Backend разрешает выбирать только ткани со статусом `published`. Ткани в статусах `draft`, `hidden` или `archived` выбрать нельзя.
7. GPT/AI-подбор не генерирует ткани, не создает новые записи и не загружает фото. Он только помогает выбрать подходящие варианты среди уже опубликованных тканей из базы.

## API for Telegram bot

Public bot endpoints do not require JWT at this stage. They are isolated under `/api/bot` so a future `BOT_INTERNAL_TOKEN` check can be added at router level.

- `POST /api/bot/users/upsert` — create or update Telegram user.
- `POST /api/bot/users/{telegram_id}/selected-fabric` — save a published fabric as selected.
- `GET /api/bot/users/{telegram_id}/selected-fabric` — return selected fabric with images or a clear empty state.

## Tests

```bash
pytest -q
```
