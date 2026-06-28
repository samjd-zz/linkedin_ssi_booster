import gc
from pathlib import Path
from typing import Any
import logging
import shutil

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

def generate_flux_image(
    prompt: str,
    output_path: str = "data/output.png",
    model_dir: str = "/app/models/flux"
):
    """
    Generates an image using FLUX.1-schnell GGUF on an RTX 3060.
    """
    model_root = _resolve_model_root(model_dir)
    _validate_local_model_files(model_root)

    transformer_path = model_root / "flux1-schnell-Q4_K_S.gguf"
    vae_path = model_root / "ae.safetensors"
    clip_path = model_root / "clip_l.safetensors"
    t5_path = model_root / "t5-v1_1-xxl-encoder-Q4_K_M.gguf"

    # 1. Ensure the exact Schnell structural configuration exists locally
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

    # The FLUX VAE is an AutoencoderKL with a FLUX-specific architecture
    # (16 latent channels, no quant/post-quant conv, shift/scaling factors).
    # Without a local config, from_single_file cannot infer this and falls
    # back to the stable-diffusion-v1-5 default repo to fetch config.json,
    # which fails under local_files_only=True. Supply the config locally.
    vae_config_dir = model_root / "vae_config"
    _ensure_vae_config_layout(vae_config_dir)
    vae = AutoencoderKL.from_single_file(
        str(vae_path),
        config=str(vae_config_dir),
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    )

    text_encoder_dir = model_root / "clip_text_encoder"
    _ensure_clip_weights_layout(text_encoder_dir=text_encoder_dir, clip_weights_path=clip_path)
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

    # Load the T5-XXL encoder and its tokenizer directly from the GGUF file.
    # transformers natively de-quantizes GGUF weights and reads the model
    # config + tokenizer from the file's metadata. Using from_single_file
    # without a GGUFQuantizationConfig leaves the weights on the meta device
    # ("Cannot copy out of meta tensor") and breaks cpu offload / inference.
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
        shift=3.0
    )

    # 2. Assemble the pipeline matrix natively
    logger.info("Assembling pipeline matrix...")
    pipe = FluxPipeline(
        scheduler=scheduler,
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        text_encoder_2=text_encoder_2,
        tokenizer_2=tokenizer_2,
        transformer=transformer
    )
    
    # FORCE the pipeline to recognize itself as FLUX
    # This prevents the library from defaulting to SD v1.5 search logic
    pipe.register_to_config(
        _class_name="FluxPipeline",
        _diffusers_version="0.30.0"
    )

    # 3. Bind execution space parameters to GPU
    pipe.enable_model_cpu_offload()

    logger.info("Generating FLUX image for prompt prefix: %s", prompt[:30])

    with torch.inference_mode():
        result: Any = pipe(
            prompt=prompt,
            width=1024,
            height=1024,
            num_inference_steps=4, 
            guidance_scale=0.0,
            max_sequence_length=256
        )
        image = result.images[0]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output))
    logger.info("FLUX image saved to %s", output)
    
    # Cleanup routines — explicit delete + GC ensures RAM/VRAM is released
    # before Ollama reclaims the GPU for the next inference job.
    del pipe
    del transformer
    del vae
    del text_encoder
    del tokenizer
    del text_encoder_2
    del tokenizer_2
    gc.collect()  # flush Python-level ref cycles before CUDA cleanup
    if torch.cuda.is_available():
        torch.cuda.synchronize()  # wait for all CUDA kernels to finish
        torch.cuda.empty_cache()  # return VRAM to the pool
        torch.cuda.ipc_collect()  # release shared-memory handles
    gc.collect()  # second pass — clears any pinned-memory CPU tensors
    logger.info("FLUX cleanup complete — VRAM and CPU buffers released")

    return str(output)


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
    # REMOVE the 'if config_file.is_file(): return' line to force overwrite
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