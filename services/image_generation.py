import gc
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging
import shutil
from threading import Lock

import torch
from diffusers import (
    AutoencoderKL,
    FluxPipeline,
    FluxTransformer2DModel,
    FlowMatchEulerDiscreteScheduler,
    GGUFQuantizationConfig,
)
from transformers import CLIPTextModel, CLIPTokenizer, T5EncoderModel, AutoTokenizer


logger = logging.getLogger(__name__)

REQUIRED_MODEL_FILES = (
    "flux1-schnell-Q4_K_S.gguf",
    "ae.safetensors",
    "clip_l.safetensors",
    "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
)


@dataclass
class _FluxRuntime:
    """Holds a fully assembled FLUX pipeline for reuse across requests."""

    pipe: FluxPipeline


_RUNTIME_LOCK = Lock()
_RUNTIME_CACHE: _FluxRuntime | None = None
_RUNTIME_CACHE_ROOT: Path | None = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _log_cuda_memory(prefix: str) -> None:
    if not torch.cuda.is_available():
        return
    if not _env_bool("FLUX_LOG_MEMORY", False):
        return
    device_index = torch.cuda.current_device()
    allocated = torch.cuda.memory_allocated(device_index) / (1024**2)
    reserved = torch.cuda.memory_reserved(device_index) / (1024**2)
    peak = torch.cuda.max_memory_allocated(device_index) / (1024**2)
    logger.info(
        "%s CUDA memory: allocated=%.1fMB reserved=%.1fMB peak=%.1fMB",
        prefix,
        allocated,
        reserved,
        peak,
    )


def _cleanup_cuda_cache() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
    gc.collect()


def _build_runtime(model_root: Path) -> _FluxRuntime:
    transformer_path = model_root / "flux1-schnell-Q4_K_S.gguf"
    vae_path = model_root / "ae.safetensors"
    clip_path = model_root / "clip_l.safetensors"
    t5_path = model_root / "t5-v1_1-xxl-encoder-Q4_K_M.gguf"

    transformer_config_dir = model_root / "transformer_config"
    _ensure_transformer_config_layout(transformer_config_dir)

    logger.info("Loading FLUX transformer from single file...")
    transformer = FluxTransformer2DModel.from_single_file(
        str(transformer_path),
        config=str(transformer_config_dir),
        local_files_only=True,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16,
    )

    vae_config_dir = model_root / "vae_config"
    _ensure_vae_config_layout(vae_config_dir)
    vae = AutoencoderKL.from_single_file(
        str(vae_path),
        config=str(vae_config_dir),
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    )

    text_encoder_dir = model_root / "clip_text_encoder"
    _ensure_clip_weights_layout(
        text_encoder_dir=text_encoder_dir, clip_weights_path=clip_path
    )
    text_encoder = CLIPTextModel.from_pretrained(
        str(text_encoder_dir),
        local_files_only=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    )
    tokenizer = CLIPTokenizer.from_pretrained(
        "openai/clip-vit-large-patch14",
        local_files_only=False,
    )

    logger.info("Loading T5 GGUF Text Encoder...")
    text_encoder_2 = T5EncoderModel.from_pretrained(
        str(model_root),
        gguf_file=t5_path.name,
        torch_dtype=torch.bfloat16,
    )

    tokenizer_2 = AutoTokenizer.from_pretrained(
        str(model_root),
        gguf_file=t5_path.name,
    )

    scheduler = FlowMatchEulerDiscreteScheduler(
        num_train_timesteps=1000,
        shift=3.0,
    )

    logger.info("Assembling FLUX pipeline...")
    pipe = FluxPipeline(
        scheduler=scheduler,
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        text_encoder_2=text_encoder_2,
        tokenizer_2=tokenizer_2,
        transformer=transformer,
    )
    pipe.register_to_config(_class_name="FluxPipeline", _diffusers_version="0.30.0")

    # Prioritize memory stability over throughput on 12GB cards.
    pipe.enable_model_cpu_offload()
    pipe.enable_attention_slicing("max")
    pipe.enable_vae_slicing()
    pipe.enable_vae_tiling()

    return _FluxRuntime(pipe=pipe)


def _get_or_create_runtime(model_root: Path) -> _FluxRuntime:
    global _RUNTIME_CACHE, _RUNTIME_CACHE_ROOT

    if _RUNTIME_CACHE is not None and _RUNTIME_CACHE_ROOT == model_root:
        return _RUNTIME_CACHE

    if _RUNTIME_CACHE is not None:
        _release_cached_runtime_locked()

    _RUNTIME_CACHE = _build_runtime(model_root)
    _RUNTIME_CACHE_ROOT = model_root
    return _RUNTIME_CACHE


def _release_cached_runtime_locked() -> None:
    global _RUNTIME_CACHE, _RUNTIME_CACHE_ROOT
    if _RUNTIME_CACHE is None:
        return
    del _RUNTIME_CACHE
    _RUNTIME_CACHE = None
    _RUNTIME_CACHE_ROOT = None
    _cleanup_cuda_cache()


def unload_flux_runtime() -> None:
    """Explicitly release cached FLUX runtime memory."""
    with _RUNTIME_LOCK:
        _release_cached_runtime_locked()

def generate_flux_image(
    prompt: str,
    output_path: str = "data/output.png",
    model_dir: str = "/app/models/flux",
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
    keep_loaded: bool | None = None,
):
    """
    Generates an image using FLUX.1-schnell GGUF on an RTX 3060.
    """
    model_root = _resolve_model_root(model_dir)
    _validate_local_model_files(model_root)

    if width < 256 or height < 256:
        raise ValueError("FLUX width/height must be at least 256")
    if num_inference_steps < 1:
        raise ValueError("FLUX num_inference_steps must be at least 1")

    if keep_loaded is None:
        keep_loaded = _env_bool("FLUX_KEEP_PIPELINE_LOADED", True)

    runtime: _FluxRuntime | None = None
    try:
        _log_cuda_memory("FLUX pre-infer")

        if keep_loaded:
            with _RUNTIME_LOCK:
                runtime = _get_or_create_runtime(model_root)
                pipe = runtime.pipe

                max_sequence_length = int(os.getenv("FLUX_MAX_SEQUENCE_LENGTH", "192"))

                logger.info(
                    "Generating FLUX image for prompt prefix: %s (size=%sx%s, steps=%s, cached=true)",
                    prompt[:30],
                    width,
                    height,
                    num_inference_steps,
                )

                with torch.inference_mode():
                    result: Any = pipe(
                        prompt=prompt,
                        width=width,
                        height=height,
                        num_inference_steps=num_inference_steps,
                        guidance_scale=0.0,
                        max_sequence_length=max_sequence_length,
                    )
                    image = result.images[0]

                output = Path(output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(output))
                del image
                del result
                _cleanup_cuda_cache()
                _log_cuda_memory("FLUX post-infer cached")
                logger.info("FLUX image saved to %s", output)
                return str(output)

        runtime = _build_runtime(model_root)
        pipe = runtime.pipe

        max_sequence_length = int(os.getenv("FLUX_MAX_SEQUENCE_LENGTH", "192"))

        logger.info(
            "Generating FLUX image for prompt prefix: %s (size=%sx%s, steps=%s, cached=false)",
            prompt[:30],
            width,
            height,
            num_inference_steps,
        )

        with torch.inference_mode():
            result: Any = pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=0.0,
                max_sequence_length=max_sequence_length,
            )
            image = result.images[0]

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output))
        del image
        del result
        logger.info("FLUX image saved to %s", output)
        _log_cuda_memory("FLUX post-infer uncached")
        return str(output)
    finally:
        if not keep_loaded and runtime is not None:
            del runtime
            _cleanup_cuda_cache()
            logger.info("FLUX cleanup complete (uncached mode)")


def _resolve_model_root(model_path_or_dir: str) -> Path:
    model_path = Path(model_path_or_dir).expanduser()
    if model_path.suffix.lower() == ".gguf":
        return model_path.parent
    return model_path


def _validate_local_model_files(model_root: Path) -> None:
    missing_files = [name for name in REQUIRED_MODEL_FILES if not (model_root / name).is_file()]
    if missing_files:
        raise ValueError(
            "Missing FLUX model files in "
            f"{model_root}: {', '.join(missing_files)}. "
            "Run the FLUX init step to download required local files."
        )


def _ensure_clip_weights_layout(text_encoder_dir: Path, clip_weights_path: Path) -> None:
    target_weights = text_encoder_dir / "model.safetensors"
    if target_weights.is_file():
        return

    text_encoder_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = text_encoder_dir / "config.json"
    if not config_file.is_file():
        import urllib.request
        url = "https://huggingface.co/openai/clip-vit-large-patch14/resolve/main/config.json"
        urllib.request.urlretrieve(url, str(config_file))

    try:
        target_weights.symlink_to(clip_weights_path)
    except OSError:
        shutil.copy2(clip_weights_path, target_weights)


def _ensure_transformer_config_layout(config_dir: Path) -> None:
    config_file = config_dir / "config.json"
    if config_file.is_file():
        return
    config_dir.mkdir(parents=True, exist_ok=True)
    
    transformer_config = {
        "_class_name": "FluxTransformer2DModel",
        "_diffusers_version": "0.30.0",
        "attention_head_dim": 128,
        "guidance_embeds": False,  # MUST BE FALSE FOR SCHNELL
        "in_channels": 64,
        "joint_attention_dim": 4096,
        "num_attention_heads": 24,
        "num_layers": 19,
        "num_single_layers": 38,
        "patch_size": 1,
        "pooled_projection_dim": 768,
        "sample_size": 128
    }

    with open(config_file, "w", encoding="utf-8") as f:
        import json
        json.dump(transformer_config, f, indent=2)


def _ensure_vae_config_layout(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    if config_file.is_file():
        return

    vae_config = {
        "_class_name": "AutoencoderKL",
        "_diffusers_version": "0.30.0",
        "act_fn": "silu",
        "block_out_channels": [128, 256, 512, 512],
        "down_block_types": [
            "DownEncoderBlock2D",
            "DownEncoderBlock2D",
            "DownEncoderBlock2D",
            "DownEncoderBlock2D",
        ],
        "force_upcast": True,
        "in_channels": 3,
        "latent_channels": 16,
        "layers_per_block": 2,
        "mid_block_add_attention": True,
        "norm_num_groups": 32,
        "out_channels": 3,
        "sample_size": 1024,
        "scaling_factor": 0.3611,
        "shift_factor": 0.1159,
        "up_block_types": [
            "UpDecoderBlock2D",
            "UpDecoderBlock2D",
            "UpDecoderBlock2D",
            "UpDecoderBlock2D",
        ],
        "use_post_quant_conv": False,
        "use_quant_conv": False,
    }

    with open(config_file, "w", encoding="utf-8") as f:
        import json
        json.dump(vae_config, f, indent=2)