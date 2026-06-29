"""Generation routes."""

import json
import logging
import inspect
from dataclasses import dataclass
from io import BytesIO
from math import gcd
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
    PRESERVATION_FAILURE_MESSAGE,
    PreservationCheckResult,
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
TRYON_PROVIDER_STRATEGY_VISION_GUIDED_EDIT = "vision_guided_edit"
TRYON_PROVIDER_STRATEGIES = {
    TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT,
    TRYON_PROVIDER_STRATEGY_VISION_GUIDED_EDIT,
}
VISION_GUIDED_PROMPT_VERSION = "vision_guided_edit_v3_canvas_adapter"
VISION_GUIDED_LEGACY_PROVIDER_SIZES = {
    "1:1": "1024x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
}
VISION_GUIDED_GPT_IMAGE_2_MIN_PIXELS = 655_360
VISION_GUIDED_GPT_IMAGE_2_MAX_PIXELS = 8_294_400
VISION_GUIDED_GPT_IMAGE_2_MAX_EDGE = 3_840
VISION_GUIDED_GPT_IMAGE_2_MAX_EDGE_RATIO = 3.0


@dataclass(frozen=True)
class VisionGuidedProviderSize:
    original_size: tuple[int, int]
    original_aspect: float
    requested_size: str
    requested_aspect: str
    exact_aspect_supported: bool
    canvas_adapted: bool = False
    provider_canvas_size: tuple[int, int] | None = None
    source_box: tuple[int, int, int, int] | None = None


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
            "Treat every opaque/protected mask pixel as locked source photography. "
            "Keep protected pixels visually identical to the first input image except for unavoidable compression. "
            "Return the full-frame edited original photo, not a crop or standalone garment. "
            "Preserve the original image pixel structure outside the editable clothing mask. "
            "Do not change face, eyes, glasses, hair, skin, hands, fingers, body shape, pose, "
            "background, furniture, objects, lighting, camera angle or composition. "
            "Preserve all non-editable regions exactly. "
            "Do not repaint, relight, smooth, beautify, sharpen, denoise, recolor, or reinterpret protected regions. "
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


def _aspect_ratio(size: tuple[int, int] | None) -> float | None:
    if size is None:
        return None
    width, height = size
    if width <= 0 or height <= 0:
        return None
    return round(width / height, 6)


def _aspect_label(width: int, height: int) -> str:
    divisor = gcd(width, height)
    if divisor <= 0:
        return "unknown"
    return f"{width // divisor}:{height // divisor}"


def _image_orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    if width > height:
        return "landscape"
    return "portrait"


def _parse_size(size: str) -> tuple[int, int] | None:
    try:
        width_text, height_text = size.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (ValueError, AttributeError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _gpt_image_2_supports_exact_size(width: int, height: int) -> bool:
    total_pixels = width * height
    short_edge = min(width, height)
    long_edge = max(width, height)
    return (
        width % 16 == 0
        and height % 16 == 0
        and long_edge <= VISION_GUIDED_GPT_IMAGE_2_MAX_EDGE
        and total_pixels >= VISION_GUIDED_GPT_IMAGE_2_MIN_PIXELS
        and total_pixels <= VISION_GUIDED_GPT_IMAGE_2_MAX_PIXELS
        and long_edge / short_edge <= VISION_GUIDED_GPT_IMAGE_2_MAX_EDGE_RATIO
    )


def _select_vision_guided_provider_size(photo_path: Path) -> VisionGuidedProviderSize:
    """Choose the safest provider size override for full-frame vision-guided edits."""

    try:
        with Image.open(photo_path) as image:
            width, height = image.size
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo is not readable.") from exc

    if width <= 0 or height <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo is not readable.")

    aspect = _aspect_ratio((width, height)) or 0.0
    aspect_label = _aspect_label(width, height)
    model = get_settings().openai_image_model.strip().lower()

    if model.startswith("gpt-image-2") and _gpt_image_2_supports_exact_size(width, height):
        return VisionGuidedProviderSize(
            original_size=(width, height),
            original_aspect=aspect,
            requested_size=f"{width}x{height}",
            requested_aspect=aspect_label,
            exact_aspect_supported=True,
        )

    legacy_size = VISION_GUIDED_LEGACY_PROVIDER_SIZES.get(aspect_label)
    if legacy_size is not None:
        return VisionGuidedProviderSize(
            original_size=(width, height),
            original_aspect=aspect,
            requested_size=legacy_size,
            requested_aspect=aspect_label,
            exact_aspect_supported=True,
        )

    fallback_size = "1024x1536" if height >= width else "1536x1024"
    provider_canvas_size = _parse_size(fallback_size)
    if provider_canvas_size is None:
        raise RuntimeError("Invalid vision-guided fallback provider size.")
    canvas_width, canvas_height = provider_canvas_size
    scale = min(1.0, canvas_width / width, canvas_height / height)
    adapted_width = max(1, int(round(width * scale)))
    adapted_height = max(1, int(round(height * scale)))
    left = (canvas_width - adapted_width) // 2
    top = (canvas_height - adapted_height) // 2

    return VisionGuidedProviderSize(
        original_size=(width, height),
        original_aspect=aspect,
        requested_size=fallback_size,
        requested_aspect=_aspect_label(canvas_width, canvas_height),
        exact_aspect_supported=False,
        canvas_adapted=True,
        provider_canvas_size=provider_canvas_size,
        source_box=(left, top, left + adapted_width, top + adapted_height),
    )


def _prepare_vision_guided_provider_photo(
    photo_path: Path,
    provider_size: VisionGuidedProviderSize,
    tmp_dir: Path,
) -> Path:
    """Return the image path sent to provider for a vision-guided edit."""

    if not provider_size.canvas_adapted:
        return photo_path
    if provider_size.provider_canvas_size is None or provider_size.source_box is None:
        raise RuntimeError("Vision-guided canvas adapter metadata is incomplete.")

    try:
        with Image.open(photo_path) as image:
            source = image.convert("RGB")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User photo is not readable.") from exc

    canvas_width, canvas_height = provider_size.provider_canvas_size
    left, top, right, bottom = provider_size.source_box
    adapted_width = right - left
    adapted_height = bottom - top
    canvas = Image.new("RGB", (canvas_width, canvas_height), color=(245, 245, 245))
    adapted_source = source.resize((adapted_width, adapted_height), Image.Resampling.LANCZOS)
    canvas.paste(adapted_source, (left, top))

    provider_photo_path = tmp_dir / "vision_guided_provider_canvas.png"
    canvas.save(provider_photo_path, format="PNG")
    return provider_photo_path


def _prepare_provider_mask_canvas(
    mask_path: Path,
    provider_size: VisionGuidedProviderSize,
    tmp_dir: Path,
) -> Path:
    """Return a mask aligned with the provider canvas adapter.

    OpenAI edit masks use transparent pixels as editable and opaque pixels as
    protected. Padding around the original source box must therefore be opaque.
    """

    if not provider_size.canvas_adapted:
        return mask_path
    if provider_size.provider_canvas_size is None or provider_size.source_box is None:
        raise RuntimeError("Provider canvas adapter metadata is incomplete.")

    try:
        with Image.open(mask_path) as image:
            source_mask = image.convert("RGBA")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mask image is not readable.") from exc

    canvas_width, canvas_height = provider_size.provider_canvas_size
    left, top, right, bottom = provider_size.source_box
    adapted_width = right - left
    adapted_height = bottom - top
    canvas = Image.new("RGBA", (canvas_width, canvas_height), color=(0, 0, 0, 255))
    adapted_mask = source_mask.resize((adapted_width, adapted_height), Image.Resampling.NEAREST)
    canvas.paste(adapted_mask, (left, top))

    provider_mask_path = tmp_dir / "masked_edit_provider_canvas_mask.png"
    canvas.save(provider_mask_path, format="PNG")
    return provider_mask_path


def _generate_fabric_on_user_photo(
    user_photo_path: str,
    fabric_reference_path: str,
    prompt: str,
    *,
    mask_image_path: str | None,
    image_size: str | None = None,
    input_fidelity: str | None = None,
) -> bytes:
    """Call the provider while staying compatible with narrow test doubles."""

    generate = image_generation_service.generate_fabric_on_user_photo
    kwargs = {"mask_image_path": mask_image_path}
    try:
        signature = inspect.signature(generate)
    except (TypeError, ValueError):
        supported_kwargs = {"image_size", "input_fidelity"}
        supports_var_kwargs = True
    else:
        supports_var_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        supported_kwargs = set(signature.parameters)
    if image_size is not None and ("image_size" in supported_kwargs or supports_var_kwargs):
        kwargs["image_size"] = image_size
    if input_fidelity is not None and ("input_fidelity" in supported_kwargs or supports_var_kwargs):
        kwargs["input_fidelity"] = input_fidelity
    return generate(user_photo_path, fabric_reference_path, prompt, **kwargs)


def _image_edit_fidelity_metadata(model: str, requested: str | None) -> dict[str, object]:
    decision = image_generation_service.resolve_image_edit_input_fidelity(
        model=model,
        requested=requested,
    )
    return {
        "provider_model": model,
        "endpoint_method": "images.edit",
        "input_image_count": 2,
        "first_input_role": "original_user_photo",
        "second_input_role": "fabric_reference",
        "mask_applied_to_first_input": True,
        "input_fidelity_requested": decision.requested,
        "input_fidelity_applied": decision.applied,
        "input_fidelity_supported": decision.supported,
        "input_fidelity_reason": decision.reason,
    }


def _extract_vision_guided_original_frame(
    image_bytes: bytes,
    provider_size: VisionGuidedProviderSize,
) -> bytes:
    """Reverse the provider canvas adapter before running source-size guardrails."""

    if not provider_size.canvas_adapted:
        return image_bytes
    if provider_size.provider_canvas_size is None or provider_size.source_box is None:
        raise RuntimeError("Vision-guided canvas adapter metadata is incomplete.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            candidate = image.convert("RGB")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise UserPhotoPreservationError(
            PreservationCheckResult(
                passes=False,
                reason="invalid_preservation_inputs",
                message=PRESERVATION_FAILURE_MESSAGE,
                thresholds=_preservation_thresholds_from_settings(),
                drift=None,
            )
        ) from exc

    canvas_width, canvas_height = provider_size.provider_canvas_size
    if candidate.size != (canvas_width, canvas_height):
        return image_bytes

    frame = candidate.crop(provider_size.source_box)
    if frame.size != provider_size.original_size:
        frame = frame.resize(provider_size.original_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    frame.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_vision_guided_user_photo_prompt(
    fabric: Fabric,
    *,
    mask_mode: str | None = None,
    attempt_index: int = 1,
    provider_size: VisionGuidedProviderSize | None = None,
) -> str:
    """Build a natural-language model-led edit prompt for full-frame try-on."""

    canvas_instruction = (
        "Return the full original photo with a realistic fabric change."
    )
    if provider_size is not None:
        width, height = provider_size.original_size
        orientation = _image_orientation(width, height)
        if provider_size.canvas_adapted and provider_size.provider_canvas_size is not None:
            canvas_width, canvas_height = provider_size.provider_canvas_size
            canvas_instruction = (
                f"Canvas/framing requirement: the original {orientation} {width}x{height} photo is centered inside "
                f"a neutral {canvas_width}x{canvas_height} provider canvas because this provider only supports fixed "
                "image sizes. Keep the centered photo region in the same location and proportions. Do not move, crop, "
                "zoom, stretch, replace, or reframe the person/photo region. Do not turn the padded canvas into a new "
                "scene. Return the same full provider canvas with only the visible target clothing fabric changed."
            )
        else:
            canvas_instruction = (
                f"Canvas/framing requirement: return the image in the same {orientation} "
                f"{provider_size.requested_aspect} aspect ratio and same full-frame composition as the original "
                f"{width}x{height} input photo. Do not change canvas size, do not change aspect ratio, do not crop, "
                "do not add padding, do not extend background, do not zoom in, and do not zoom out."
            )

    details = [
        (
            "Using the second image only as the fabric/material reference, edit the first image so that only "
            "the visible target clothing fabric is changed to that fabric."
        ),
        (
            "Keep the same person, face, hands, phone, pose, body shape, outer clothing, background, lighting, "
            "camera angle, photo framing, garment folds, shadows and perspective unchanged."
        ),
        "Do not create a new person. Do not create a new shirt. Do not paste a rectangle.",
        "Do not make a collage, sticker, mockup, product photo, crop, or standalone garment.",
        canvas_instruction,
        "Use the selected catalog fabric reference only as a textile/material guide, not as an object to place.",
        "Retexture/change fabric on the existing visible clothing while preserving garment structure.",
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
    if mask_mode and "visible_inner_tshirt" in mask_mode:
        details.append(
            "The target clothing is the visible inner T-shirt under the open overshirt/jacket. "
            "The outer overshirt/jacket must remain unchanged. Hands and phone are occluders and must remain "
            "unchanged. Apply the fabric only where the inner T-shirt is visible."
        )
    if provider_size is not None and provider_size.canvas_adapted:
        details.append(
            "The neutral padding around the centered photo is only a compatibility canvas. Preserve the centered "
            "photo frame exactly; the final safety check will ignore the padding and evaluate only that original "
            "photo region."
        )
    elif provider_size is not None and not provider_size.exact_aspect_supported:
        details.append(
            "Provider size is requested as auto because the original aspect ratio is not one of the fixed "
            "legacy image sizes. Preserve the original input aspect ratio and full-frame canvas instead of "
            "defaulting to a square or 2:3 portrait canvas."
        )
    if attempt_index > 1:
        details.append(
            "Retry correction: the previous output was rejected by safety checks. Be more conservative: "
            "material transfer only, no patch, no rectangle, no new garment, no identity or background changes."
        )
    return "\n".join(details)


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


def _tryon_provider_strategy() -> str:
    """Return the selected provider strategy, falling back to the safer masked edit path."""

    strategy = get_settings().tryon_provider_strategy.strip().lower()
    if strategy in TRYON_PROVIDER_STRATEGIES:
        return strategy
    logger.warning(
        "Unknown user photo try-on strategy=%s; falling back to %s",
        sanitize_log_message(strategy),
        TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT,
    )
    return TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT


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


def _size_metadata(size: tuple[int, int] | None) -> list[int] | None:
    return [size[0], size[1]] if size is not None else None


def _preservation_guardrail_metadata(result: PreservationCheckResult) -> dict[str, object]:
    """Return sanitized preservation metadata safe for logs/debug JSON."""

    metadata: dict[str, object] = {
        "original_size": _size_metadata(result.original_size),
        "provider_output_size": _size_metadata(result.provider_output_size),
        "mask_size": _size_metadata(result.mask_size),
        "original_aspect": _aspect_ratio(result.original_size),
        "provider_output_aspect": _aspect_ratio(result.provider_output_size),
        "aspect_ratio_delta": result.aspect_ratio_delta,
        "size_normalized": result.size_normalized,
        "normalized_size": _size_metadata(result.normalized_size),
        "fail_reason": result.reason,
    }
    if result.drift is not None:
        metadata.update(
            {
                "protected_region_score": result.drift.protected_region_score,
                "protected_region_changed_ratio": result.drift.changed_pixel_percent,
                "protected_region_sampled_pixels": result.drift.protected_pixel_count,
                "boundary_band_excluded": result.drift.boundary_band_excluded,
                "boundary_band_pixels": result.drift.boundary_band_pixel_count,
                "color_normalization_applied": result.drift.color_normalization_applied,
            }
        )
    return metadata


def _ensure_user_photo_preservation_safe(
    *,
    source_image_path: Path,
    candidate_image_bytes: bytes,
    mask_image_path: Path,
) -> PreservationCheckResult | None:
    """Fail closed when a masked provider output changes protected regions."""

    settings = get_settings()
    if not settings.user_photo_preservation_check_enabled:
        return None

    result = evaluate_generated_image_preservation(
        source_image_path=source_image_path,
        candidate_image_bytes=candidate_image_bytes,
        mask_image_path=mask_image_path,
        thresholds=_preservation_thresholds_from_settings(),
    )
    if result.passes:
        return result

    drift = result.drift
    logger.warning(
        (
            "User photo preservation guardrail failed reason=%s mean_delta=%s changed_pixel_percent=%s "
            "max_delta=%s original_size=%s provider_output_size=%s mask_size=%s "
            "aspect_ratio_delta=%s size_normalized=%s boundary_band_excluded=%s "
            "boundary_band_pixels=%s color_normalization_applied=%s"
        ),
        result.reason,
        f"{drift.mean_delta:.4f}" if drift else "n/a",
        f"{drift.changed_pixel_percent:.4f}" if drift else "n/a",
        drift.max_delta if drift else "n/a",
        result.original_size,
        result.provider_output_size,
        result.mask_size,
        f"{result.aspect_ratio_delta:.6f}" if result.aspect_ratio_delta is not None else "n/a",
        result.size_normalized,
        drift.boundary_band_excluded if drift else "n/a",
        drift.boundary_band_pixel_count if drift else "n/a",
        drift.color_normalization_applied if drift else "n/a",
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
        tmp_path = Path(tmp_dir)
        normalized_reference_path = _normalized_fabric_reference_for_provider(reference_path, tmp_path)
        provider_size = _select_vision_guided_provider_size(photo_path)
        provider_photo_path = _prepare_vision_guided_provider_photo(photo_path, provider_size, tmp_path)
        provider_mask_path = _prepare_provider_mask_canvas(mask_path, provider_size, tmp_path)
        settings = get_settings()
        edit_metadata = _image_edit_fidelity_metadata(
            settings.openai_image_model,
            settings.tryon_input_fidelity,
        )
        for attempt in range(1, max_attempts + 1):
            prompt = _build_user_photo_prompt(fabric, mask_used=True, attempt_index=attempt)
            if provider_size.canvas_adapted:
                prompt = "\n".join(
                    [
                        prompt,
                        (
                            f"The user photo and edit mask are centered on a neutral "
                            f"{provider_size.requested_size} provider compatibility canvas. "
                            "Edit only the transparent mask area inside the original-photo frame. "
                            "Do not edit the neutral padding. Return the full provider canvas with "
                            "the original-photo frame in the same position and scale."
                        ),
                    ]
                )
            generation.prompt = prompt
            report: dict[str, object] = {
                "attempt": attempt,
                "strategy": TRYON_PROVIDER_STRATEGY_CHATGPT_LIKE_MASKED_EDIT,
                "fabric_reference_normalized": True,
                **edit_metadata,
                "requested_provider_size": provider_size.requested_size,
                "requested_provider_aspect": provider_size.requested_aspect,
                "original_size": _size_metadata(provider_size.original_size),
                "original_aspect": provider_size.original_aspect,
                "exact_provider_aspect_supported": provider_size.exact_aspect_supported,
                "provider_canvas_adapted": provider_size.canvas_adapted,
                "provider_canvas_size": _size_metadata(provider_size.provider_canvas_size),
                "provider_source_box": list(provider_size.source_box) if provider_size.source_box is not None else None,
                "provider_called": False,
                "preservation_checked": False,
                "status": "started",
            }
            try:
                image_bytes = _generate_fabric_on_user_photo(
                    str(provider_photo_path),
                    str(normalized_reference_path),
                    prompt,
                    mask_image_path=str(provider_mask_path),
                    image_size=provider_size.requested_size,
                    input_fidelity=edit_metadata["input_fidelity_applied"],
                )
                report["provider_called"] = True
                image_bytes = _extract_vision_guided_original_frame(image_bytes, provider_size)
                preservation_result = _ensure_user_photo_preservation_safe(
                    source_image_path=photo_path,
                    candidate_image_bytes=image_bytes,
                    mask_image_path=mask_path,
                )
                if preservation_result is not None:
                    report["guardrail_metadata"] = _preservation_guardrail_metadata(preservation_result)
                    if preservation_result.normalized_candidate_image_bytes is not None:
                        image_bytes = preservation_result.normalized_candidate_image_bytes
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


def _generate_vision_guided_user_photo_with_attempts(
    *,
    generation: Generation,
    photo_path: Path,
    reference_path: Path,
    fabric: Fabric,
    mask_path: Path,
    mask_mode: str | None,
) -> bytes:
    """Run model-led full-frame edits without sending the guardrail mask to the provider."""

    strategy = TRYON_PROVIDER_STRATEGY_VISION_GUIDED_EDIT
    max_attempts = _tryon_max_provider_attempts()
    attempt_reports: list[dict[str, object]] = []
    last_error: Exception | None = None

    with TemporaryDirectory(prefix="tryon-reference-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        normalized_reference_path = _normalized_fabric_reference_for_provider(reference_path, tmp_path)
        provider_size = _select_vision_guided_provider_size(photo_path)
        provider_photo_path = _prepare_vision_guided_provider_photo(photo_path, provider_size, tmp_path)
        for attempt in range(1, max_attempts + 1):
            prompt = _build_vision_guided_user_photo_prompt(
                fabric,
                mask_mode=mask_mode,
                attempt_index=attempt,
                provider_size=provider_size,
            )
            generation.prompt = prompt
            report: dict[str, object] = {
                "attempt": attempt,
                "strategy": strategy,
                "prompt_version": VISION_GUIDED_PROMPT_VERSION,
                "has_original_image": True,
                "has_fabric_reference": True,
                "fabric_reference_normalized": True,
                "requested_provider_size": provider_size.requested_size,
                "requested_provider_aspect": provider_size.requested_aspect,
                "original_size": _size_metadata(provider_size.original_size),
                "original_aspect": provider_size.original_aspect,
                "exact_provider_aspect_supported": provider_size.exact_aspect_supported,
                "provider_canvas_adapted": provider_size.canvas_adapted,
                "provider_canvas_size": _size_metadata(provider_size.provider_canvas_size),
                "provider_source_box": list(provider_size.source_box) if provider_size.source_box is not None else None,
                "mask_used": False,
                "mask_mode": "none",
                "guardrail_mask_mode": mask_mode,
                "provider_called": False,
                "preservation_checked": False,
                "status": "started",
            }
            try:
                image_bytes = _generate_fabric_on_user_photo(
                    str(provider_photo_path),
                    str(normalized_reference_path),
                    prompt,
                    mask_image_path=None,
                    image_size=provider_size.requested_size,
                )
                report["provider_called"] = True
                image_bytes = _extract_vision_guided_original_frame(image_bytes, provider_size)
                preservation_result = _ensure_user_photo_preservation_safe(
                    source_image_path=photo_path,
                    candidate_image_bytes=image_bytes,
                    mask_image_path=mask_path,
                )
                if preservation_result is not None:
                    report["guardrail_metadata"] = _preservation_guardrail_metadata(preservation_result)
                    if preservation_result.normalized_candidate_image_bytes is not None:
                        image_bytes = preservation_result.normalized_candidate_image_bytes
                report["preservation_checked"] = True
                report["guardrail_status"] = "passed"
                report["status"] = "passed"
                attempt_reports.append(report)
                _write_tryon_debug_report(generation, strategy=strategy, attempts=attempt_reports)
                return image_bytes
            except UserPhotoPreservationError as exc:
                report["preservation_checked"] = True
                report["guardrail_status"] = "failed"
                report["guardrail_reason"] = exc.result.reason
                report["guardrail_metadata"] = _preservation_guardrail_metadata(exc.result)
                report["status"] = "failed"
                report["error"] = safe_exception_summary(exc)
                attempt_reports.append(report)
                last_error = exc
                logger.warning(
                    "Vision-guided user photo try-on attempt failed generation_id=%s attempt=%s max_attempts=%s error=%s",
                    generation.id,
                    attempt,
                    max_attempts,
                    safe_exception_summary(exc),
                )
                if attempt >= max_attempts:
                    break
            except Exception as exc:
                report["status"] = "failed"
                report["error"] = safe_exception_summary(exc)
                attempt_reports.append(report)
                last_error = exc
                logger.warning(
                    "Vision-guided user photo try-on provider failed generation_id=%s attempt=%s max_attempts=%s error=%s",
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
    raise RuntimeError("Vision-guided user photo try-on failed before provider attempt.")


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
            strategy = _tryon_provider_strategy()
            if strategy == TRYON_PROVIDER_STRATEGY_VISION_GUIDED_EDIT:
                image_bytes = _generate_vision_guided_user_photo_with_attempts(
                    generation=generation,
                    photo_path=photo_path,
                    reference_path=reference_path,
                    fabric=fabric,
                    mask_path=mask_result.mask_path,
                    mask_mode=mask_result.mode,
                )
            else:
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
