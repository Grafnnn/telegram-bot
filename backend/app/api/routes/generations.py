"""Generation routes."""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.rate_limit import rate_limit_catalog_style_generation, rate_limit_user_photo_generation
from app.api.deps import verify_bot_internal_token
from app.config import MissingOpenAIKeyError, get_settings
from app.database import get_db
from app.models import Fabric, GarmentStyle, Generation, TelegramUser
from app.schemas.generation import (
    GENERATION_STATUS_COMPLETED,
    GENERATION_STATUS_FAILED,
    GENERATION_STATUS_PENDING,
    GENERATION_STATUS_PROCESSING,
    CatalogStyleGenerationRequest,
    GenerationRead,
)
from app.services import image_generation_service
from app.services.image_generation_service import IMAGE_ERROR, IMAGE_EDIT_PROMPT, USER_PHOTO_EDIT_PROMPT
from app.services.image_readiness_service import select_ready_fabric_reference_path
from app.services.mask_service import prepare_user_photo_mask, prepare_user_photo_preset_mask
from app.services.preservation_service import (
    PreservationThresholds,
    UserPhotoPreservationError,
    evaluate_generated_image_preservation,
)
from app.services.storage_service import resolve_upload_path, save_generated_image, save_upload
from app.utils.redaction import safe_exception_summary, sanitize_log_message

router = APIRouter(prefix="/generations", tags=["generations"])
logger = logging.getLogger(__name__)
ACTIVE_GENERATION_STATUSES = (GENERATION_STATUS_PENDING, GENERATION_STATUS_PROCESSING)
USER_PHOTO_INPUT_MODE_FULL_PHOTO = "full_photo"
USER_PHOTO_INPUT_MODE_GARMENT_CROP = "garment_crop"
USER_PHOTO_INPUT_MODES = {USER_PHOTO_INPUT_MODE_FULL_PHOTO, USER_PHOTO_INPUT_MODE_GARMENT_CROP}
TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT = "chatgpt_like_masked_edit"


def _generation_or_404(db: Session, generation_id: UUID) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Генерация не найдена")
    return generation


def _telegram_user_or_404(db: Session, telegram_id: int) -> TelegramUser:
    user = db.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь Telegram не найден")
    return user


def _selected_published_fabric(db: Session, user: TelegramUser) -> Fabric:
    if user.selected_fabric_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала выберите ткань.")
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == user.selected_fabric_id))
    if fabric is None or fabric.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранная ткань не найдена или больше не опубликована.")
    return fabric


def _published_fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    if fabric.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранная ткань не найдена или больше не опубликована.")
    return fabric


def _fabric_or_404(db: Session, fabric_id: UUID) -> Fabric:
    fabric = db.scalar(select(Fabric).options(selectinload(Fabric.images)).where(Fabric.id == fabric_id))
    if fabric is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ткань не найдена")
    return fabric


def _require_published_fabric(fabric: Fabric) -> None:
    if fabric.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранная ткань не найдена или больше не опубликована.")


def _selected_published_style(db: Session, user: TelegramUser) -> GarmentStyle:
    if user.selected_garment_style_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала выберите фасон.")
    style = db.get(GarmentStyle, user.selected_garment_style_id)
    if style is None or style.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выбранный фасон не найден или больше не опубликован.")
    return style


def _texture_image_url(fabric: Fabric) -> str:
    texture = next((image for image in fabric.images if image.image_type == "texture"), None)
    if texture is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранной ткани нет texture image.")
    return texture.image_url


def select_fabric_reference_image(fabric: Fabric) -> str:
    """Return the selected fabric reference image for user-photo try-on."""

    texture = next((image for image in fabric.images if image.image_type == "texture"), None)
    main = next((image for image in fabric.images if image.image_type == "main"), None)
    reference = texture or main
    if reference is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранной ткани нет изображения для примерки.")
    return reference.image_url


def select_fabric_reference_image_path(fabric: Fabric) -> tuple[Path, str]:
    """Return a usable selected-fabric reference image path and image type."""

    try:
        return select_ready_fabric_reference_path(fabric)
    except HTTPException as exc:
        logger.warning(
            "Selected fabric has no AI-ready reference image fabric_id=%s error=%s",
            fabric.id,
            safe_exception_summary(exc),
        )
        raise


def resolve_user_photo_upload_path(photo_url: str) -> Path:
    try:
        return resolve_upload_path(photo_url)
    except HTTPException as exc:
        logger.warning(
            "User photo upload path resolution failed reason=%s error=%s",
            getattr(exc, "reason", "unknown"),
            safe_exception_summary(exc),
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo upload file is missing after save.") from exc


def prepare_user_photo_edit_inputs(photo_url: str, fabric: Fabric) -> tuple[Path, Path, str]:
    """Resolve the user photo and selected catalog fabric reference paths."""

    photo_path = resolve_user_photo_upload_path(photo_url)
    reference_path, reference_type = select_fabric_reference_image_path(fabric)
    return photo_path, reference_path, reference_type


def _base_image_url(style: GarmentStyle) -> str:
    if not style.base_image_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "У выбранного фасона нет base image.")
    return style.base_image_url


def _build_catalog_style_prompt(fabric: Fabric, style: GarmentStyle) -> str:
    details = [IMAGE_EDIT_PROMPT, f"Selected fabric id: {fabric.id}.", f"Selected garment style id: {style.id}."]
    if fabric.description_for_gpt:
        details.append(f"Fabric description: {fabric.description_for_gpt}")
    if style.description:
        details.append(f"Garment style description: {style.description}")
    return "\n".join(details)


def _catalog_style_mask_for_provider(mask_path: Path, tmp_dir: Path) -> Path:
    """Return a provider-ready RGBA PNG mask for catalog-style edits."""

    try:
        with Image.open(mask_path) as image:
            mask_image = image.convert("RGBA")
            alpha = mask_image.getchannel("A")
            if alpha.getextrema()[0] < 255:
                return mask_path

            luminance = image.convert("L")
            derived_alpha = luminance.point(lambda value: 0 if value > 8 else 255, mode="L")
            mask_image.putalpha(derived_alpha)
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Garment style mask image is not readable.") from exc

    provider_mask_path = tmp_dir / "catalog_style_mask.png"
    mask_image.save(provider_mask_path, format="PNG")
    return provider_mask_path


def build_user_photo_fabric_replacement_prompt(
    fabric: Fabric,
    garment_style: GarmentStyle | None = None,
    *,
    mask_used: bool = False,
    attempt_index: int = 1,
) -> str:
    details = [
        USER_PHOTO_EDIT_PROMPT,
        "This is an image editing task, not a new image generation task.",
        "Use the user's uploaded photo as the base image.",
        "Use the selected catalog fabric reference image as the only fabric source.",
        "Replace only the visible fabric/material of the clothing item worn by the person.",
        (
            "Preserve the exact same person, face, hair, body, hands, skin, pose, camera angle, "
            "background, lighting, shadows, objects, room, furniture, accessories and image composition."
        ),
        "Do not change identity. Do not beautify the person. Do not change body shape.",
        "Do not add or remove objects. Do not change the scene. Do not invent another fabric.",
        (
            "If the original photo has multiple garments, edit only the main visible garment unless "
            "the user context explicitly identifies another garment."
        ),
        "Keep all unedited regions pixel-level similar to the original photo.",
        "Selected catalog fabric:",
        f"Fabric id: {fabric.id}",
        f"SKU: {fabric.sku}",
        f"Name: {fabric.name}",
    ]
    if fabric.description_for_gpt:
        details.append(f"Description: {fabric.description_for_gpt}")
    if fabric.category:
        details.append(f"Category: {fabric.category}")
    if fabric.color:
        details.append(f"Color: {fabric.color}")
    if garment_style and garment_style.description:
        details.append(f"Garment style context: {garment_style.description}")
    if mask_used:
        details.append(
            "A clothing edit mask is provided. This is a strict inpainting/editing task. "
            "Edit only the transparent/editable clothing region defined by the mask. "
            "Return the full-frame edited original photo, not a crop or standalone garment. "
            "Preserve the original image pixel structure outside the editable clothing mask. "
            "Do not change face, eyes, glasses, hair, skin, hands, fingers, body shape, pose, "
            "background, furniture, objects, lighting, camera angle or composition. "
            "Preserve all non-editable regions exactly. "
            "Do not insert a new person, product mockup, rectangular patch, sticker, collage, "
            "separate generated crop, or pasted shirt photo."
        )
        if attempt_index > 1:
            details.append(
                "Retry correction: the previous attempt was rejected because it changed protected regions or looked "
                "like a pasted patch. Be more conservative. Keep the original person and scene unchanged, blend only "
                "the clothing fabric inside the editable mask, preserve folds and shadows, and avoid rectangular "
                "overlay edges."
            )
    details.append(
        "The final clothing fabric must match the selected catalog fabric reference: "
        "color, pattern, weave, texture, scale and visual style."
    )
    return "\n".join(details)


def _build_user_photo_prompt(fabric: Fabric, *, mask_used: bool = False, attempt_index: int = 1) -> str:
    return build_user_photo_fabric_replacement_prompt(
        fabric,
        mask_used=mask_used,
        attempt_index=attempt_index,
    )


def _build_garment_crop_prompt(fabric: Fabric) -> str:
    details = [
        "Edit only this cropped garment image.",
        "The input image is a close crop of clothing fabric, not a full person photo.",
        "Use the selected catalog fabric reference image as the only fabric source.",
        "Replace the crop's visible clothing material with the selected catalog fabric.",
        "Preserve the crop framing, folds, seams, shadows, garment construction and silhouette.",
        "Do not create a person, face, body, background, room or full-scene composition.",
        "Do not add text, logos, watermarks, extra objects or extra people.",
        "Selected catalog fabric:",
        f"Fabric id: {fabric.id}",
        f"SKU: {fabric.sku}",
        f"Name: {fabric.name}",
    ]
    if fabric.description_for_gpt:
        details.append(f"Description: {fabric.description_for_gpt}")
    if fabric.category:
        details.append(f"Category: {fabric.category}")
    if fabric.color:
        details.append(f"Color: {fabric.color}")
    details.append(
        "The final garment crop must match the selected catalog fabric reference: "
        "color, pattern, weave, texture, scale and visual style."
    )
    return "\n".join(details)


def _safe_generation_error(exc: Exception) -> str:
    if isinstance(exc, MissingOpenAIKeyError):
        return str(exc)
    if isinstance(exc, UserPhotoPreservationError):
        return str(exc)
    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Ошибка генерации скрыта из интерфейса."
        return sanitize_log_message(detail)
    return IMAGE_ERROR


def _active_catalog_style_generation(
    db: Session,
    user: TelegramUser,
    fabric: Fabric,
    style: GarmentStyle,
) -> Generation | None:
    return db.scalar(
        select(Generation)
        .where(
            Generation.telegram_user_id == user.id,
            Generation.fabric_id == fabric.id,
            Generation.garment_style_id == style.id,
            Generation.mode == "catalog_style",
            Generation.status.in_(ACTIVE_GENERATION_STATUSES),
        )
        .order_by(Generation.created_at.desc())
    )


def _mark_generation_completed(generation: Generation, image_bytes: bytes) -> None:
    extension = get_settings().openai_image_output_format.strip().lower()
    generation.result_image_url = save_generated_image(image_bytes, extension)
    generation.status = GENERATION_STATUS_COMPLETED
    generation.error_message = None


def _mark_generation_failed(generation: Generation, exc: Exception) -> None:
    generation.status = GENERATION_STATUS_FAILED
    generation.error_message = _safe_generation_error(exc)


def _preservation_thresholds_from_settings() -> PreservationThresholds:
    settings = get_settings()
    return PreservationThresholds(
        max_mean_delta=settings.user_photo_preservation_max_mean_delta,
        max_changed_pixel_percent=settings.user_photo_preservation_max_changed_pixel_percent,
        pixel_delta_threshold=settings.user_photo_preservation_pixel_delta_threshold,
    )


def _tryon_max_provider_attempts() -> int:
    """Return a conservative bounded provider attempt count."""

    attempts = get_settings().tryon_max_provider_attempts
    return max(1, min(attempts, 3))


def _normalized_fabric_reference_for_provider(reference_path: Path, tmp_dir: Path) -> Path:
    """Return a square provider-ready fabric reference without mutating catalog uploads."""

    try:
        with Image.open(reference_path) as image:
            fabric = image.convert("RGB")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fabric reference image is not readable.") from exc

    target_size = 1024
    if fabric.width <= 0 or fabric.height <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fabric reference image is not readable.")

    if fabric.width < target_size or fabric.height < target_size:
        tile = Image.new("RGB", (target_size, target_size))
        # Keep texture scale legible but avoid sending a tiny thumbnail as the whole reference.
        scale = max(1.0, min(target_size / max(1, fabric.width), target_size / max(1, fabric.height)))
        scaled = fabric.resize(
            (max(1, int(fabric.width * scale)), max(1, int(fabric.height * scale))),
            Image.Resampling.LANCZOS,
        )
        for y in range(0, target_size, scaled.height):
            for x in range(0, target_size, scaled.width):
                tile.paste(scaled, (x, y))
        normalized = tile
    else:
        side = min(fabric.width, fabric.height)
        left = (fabric.width - side) // 2
        top = (fabric.height - side) // 2
        normalized = fabric.crop((left, top, left + side, top + side)).resize(
            (target_size, target_size),
            Image.Resampling.LANCZOS,
        )

    normalized_path = tmp_dir / "fabric_reference_normalized.png"
    normalized.save(normalized_path, format="PNG")
    return normalized_path


def _write_tryon_debug_report(
    generation: Generation,
    *,
    strategy: str,
    attempts: list[dict[str, object]],
) -> None:
    """Persist a sanitized local debug report when explicitly enabled."""

    if not get_settings().tryon_debug_bundle_enabled:
        return
    debug_dir = get_settings().upload_dir / "tryon-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    report_path = debug_dir / f"{generation.id}.json"
    report = {
        "generation_id": str(generation.id),
        "strategy": strategy,
        "attempts": attempts,
    }
    try:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("User photo try-on debug report write failed error=%s", safe_exception_summary(exc))


def _ensure_user_photo_preservation_safe(
    *,
    source_image_path: Path,
    candidate_image_bytes: bytes,
    mask_image_path: Path,
) -> None:
    """Fail closed when a masked provider output changes protected regions."""

    settings = get_settings()
    if not settings.user_photo_preservation_check_enabled:
        return

    result = evaluate_generated_image_preservation(
        source_image_path=source_image_path,
        candidate_image_bytes=candidate_image_bytes,
        mask_image_path=mask_image_path,
        thresholds=_preservation_thresholds_from_settings(),
    )
    if result.passes:
        return

    drift = result.drift
    logger.warning(
        "User photo preservation guardrail failed reason=%s mean_delta=%s changed_pixel_percent=%s max_delta=%s",
        result.reason,
        f"{drift.mean_delta:.4f}" if drift else "n/a",
        f"{drift.changed_pixel_percent:.4f}" if drift else "n/a",
        drift.max_delta if drift else "n/a",
    )
    raise UserPhotoPreservationError(result)


def _generate_masked_user_photo_with_attempts(
    *,
    generation: Generation,
    photo_path: Path,
    reference_path: Path,
    fabric: Fabric,
    mask_path: Path,
) -> bytes:
    """Run bounded full-photo masked edit attempts and fail closed on preservation drift."""

    strategy = get_settings().tryon_provider_strategy.strip().lower()
    if strategy != TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT:
        logger.info(
            "User photo try-on strategy=%s is treated as chatgpt-like masked edit for safety",
            sanitize_log_message(strategy),
        )
    max_attempts = _tryon_max_provider_attempts()
    attempt_reports: list[dict[str, object]] = []
    last_error: Exception | None = None

    with TemporaryDirectory(prefix="tryon-reference-") as tmp_dir:
        normalized_reference_path = _normalized_fabric_reference_for_provider(reference_path, Path(tmp_dir))
        for attempt in range(1, max_attempts + 1):
            prompt = _build_user_photo_prompt(fabric, mask_used=True, attempt_index=attempt)
            generation.prompt = prompt
            report: dict[str, object] = {
                "attempt": attempt,
                "strategy": TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT,
                "fabric_reference_normalized": True,
                "provider_called": False,
                "preservation_checked": False,
                "status": "started",
            }
            try:
                image_bytes = image_generation_service.generate_fabric_on_user_photo(
                    str(photo_path),
                    str(normalized_reference_path),
                    prompt,
                    mask_image_path=str(mask_path),
                )
                report["provider_called"] = True
                _ensure_user_photo_preservation_safe(
                    source_image_path=photo_path,
                    candidate_image_bytes=image_bytes,
                    mask_image_path=mask_path,
                )
                report["preservation_checked"] = True
                report["status"] = "passed"
                attempt_reports.append(report)
                _write_tryon_debug_report(generation, strategy=strategy, attempts=attempt_reports)
                return image_bytes
            except Exception as exc:
                report["status"] = "failed"
                report["error"] = safe_exception_summary(exc)
                attempt_reports.append(report)
                last_error = exc
                logger.warning(
                    "User photo try-on attempt failed generation_id=%s attempt=%s max_attempts=%s error=%s",
                    generation.id,
                    attempt,
                    max_attempts,
                    safe_exception_summary(exc),
                )
                if attempt >= max_attempts:
                    break

    _write_tryon_debug_report(generation, strategy=strategy, attempts=attempt_reports)
    if last_error is not None:
        raise last_error
    raise RuntimeError("User photo try-on failed before provider attempt.")


@router.post(
    "/catalog-style",
    response_model=GenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_catalog_style_generation)],
)
def create_catalog_style_generation(
    payload: CatalogStyleGenerationRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Generation:
    user = _telegram_user_or_404(db, payload.telegram_id)
    fabric = _selected_published_fabric(db, user)
    style = _selected_published_style(db, user)
    active_generation = _active_catalog_style_generation(db, user, fabric, style)
    if active_generation is not None:
        response.status_code = status.HTTP_200_OK
        return active_generation
    texture_url = _texture_image_url(fabric)
    base_url = _base_image_url(style)
    texture_path = resolve_upload_path(texture_url)
    base_path = resolve_upload_path(base_url)
    mask_path = resolve_upload_path(style.mask_image_url) if style.mask_image_url else None
    prompt = _build_catalog_style_prompt(fabric, style)
    generation = Generation(
        telegram_user_id=user.id,
        fabric_id=fabric.id,
        garment_style_id=style.id,
        mode="catalog_style",
        prompt=prompt,
        status=GENERATION_STATUS_PROCESSING,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    try:
        with TemporaryDirectory(prefix="catalog-style-mask-") as tmp_dir:
            provider_mask_path = _catalog_style_mask_for_provider(mask_path, Path(tmp_dir)) if mask_path else None
            image_bytes = image_generation_service.generate_fabric_on_catalog_style(
                str(base_path),
                str(texture_path),
                str(provider_mask_path) if provider_mask_path else None,
                prompt,
            )
        _mark_generation_completed(generation, image_bytes)
    except Exception as exc:
        _mark_generation_failed(generation, exc)
        logger.warning(
            "Catalog style generation failed generation_id=%s error=%s",
            generation.id,
            safe_exception_summary(exc),
        )
    db.commit()
    db.refresh(generation)
    return generation


@router.post(
    "/user-photo",
    response_model=GenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bot_internal_token), Depends(rate_limit_user_photo_generation)],
)
async def create_user_photo_generation(
    telegram_id: int | None = Form(None),
    telegram_user_id: UUID | None = Form(None),
    fabric_id: UUID = Form(...),
    photo: UploadFile = File(...),
    mask: UploadFile | None = File(None),
    mask_preset: str | None = Form(None),
    input_mode: str = Form(USER_PHOTO_INPUT_MODE_FULL_PHOTO),
    db: Session = Depends(get_db),
) -> Generation:
    return await _create_user_photo_generation(
        telegram_id,
        telegram_user_id,
        fabric_id,
        photo,
        mask,
        mask_preset,
        input_mode,
        db,
    )


async def _create_user_photo_generation(
    telegram_id: int | None,
    telegram_user_id: UUID | None,
    fabric_id: UUID,
    photo: UploadFile,
    mask: UploadFile | None,
    mask_preset: str | None,
    input_mode: str,
    db: Session,
) -> Generation:
    normalized_input_mode = input_mode.strip().lower()
    if normalized_input_mode not in USER_PHOTO_INPUT_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported user photo input mode.")
    linked_user_id = telegram_user_id
    if telegram_id is not None:
        linked_user_id = _telegram_user_or_404(db, telegram_id).id
    fabric = _fabric_or_404(db, fabric_id)
    prompt = (
        _build_garment_crop_prompt(fabric)
        if normalized_input_mode == USER_PHOTO_INPUT_MODE_GARMENT_CROP
        else _build_user_photo_prompt(fabric)
    )
    generation = Generation(
        telegram_user_id=linked_user_id,
        fabric_id=fabric_id,
        mode="user_photo_garment_crop" if normalized_input_mode == USER_PHOTO_INPUT_MODE_GARMENT_CROP else "user_photo",
        prompt=prompt,
        status=GENERATION_STATUS_PROCESSING,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    try:
        _require_published_fabric(fabric)
        upload_folder = "user-garment-crops" if normalized_input_mode == USER_PHOTO_INPUT_MODE_GARMENT_CROP else "user-photos"
        photo_url = await save_upload(photo, upload_folder)
        generation.user_photo_url = photo_url
        photo_path, reference_path, reference_type = prepare_user_photo_edit_inputs(photo_url, fabric)
        mask_result = None
        if normalized_input_mode == USER_PHOTO_INPUT_MODE_GARMENT_CROP:
            if mask is not None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Garment crop mode does not accept a full-photo mask.")
            if mask_preset:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Garment crop mode does not accept a full-photo mask preset.")
        else:
            if mask is not None:
                mask_result = await prepare_user_photo_mask(photo_path, mask)
            elif mask_preset:
                mask_result = prepare_user_photo_preset_mask(photo_path, mask_preset)
            else:
                mask_result = await prepare_user_photo_mask(photo_path, None)
            if mask_result is not None:
                generation.mask_image_url = mask_result.mask_image_url
                prompt = _build_user_photo_prompt(fabric, mask_used=True)
                generation.prompt = prompt
        logger.info(
            "User photo generation reference selected generation_id=%s fabric_id=%s image_type=%s input_mode=%s mask_mode=%s",
            generation.id,
            fabric.id,
            reference_type,
            normalized_input_mode,
            mask_result.mode if mask_result else "none",
        )
        if normalized_input_mode == USER_PHOTO_INPUT_MODE_GARMENT_CROP:
            image_bytes = image_generation_service.generate_fabric_on_user_photo(
                str(photo_path),
                str(reference_path),
                prompt,
                mask_image_path=None,
            )
        elif mask_result is not None:
            image_bytes = _generate_masked_user_photo_with_attempts(
                generation=generation,
                photo_path=photo_path,
                reference_path=reference_path,
                fabric=fabric,
                mask_path=mask_result.mask_path,
            )
        else:
            image_bytes = image_generation_service.generate_fabric_on_user_photo(
                str(photo_path),
                str(reference_path),
                prompt,
                mask_image_path=str(mask_result.mask_path) if mask_result else None,
            )
        _mark_generation_completed(generation, image_bytes)
    except HTTPException as exc:
        _mark_generation_failed(generation, exc)
        logger.warning(
            "User photo generation validation failed generation_id=%s error=%s",
            generation.id,
            safe_exception_summary(exc),
        )
        db.commit()
        db.refresh(generation)
        raise
    except Exception as exc:
        _mark_generation_failed(generation, exc)
        logger.warning(
            "User photo generation failed generation_id=%s error=%s",
            generation.id,
            safe_exception_summary(exc),
        )
    db.commit()
    db.refresh(generation)
    return generation


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation(generation_id: UUID, db: Session = Depends(get_db)) -> Generation:
    return _generation_or_404(db, generation_id)
