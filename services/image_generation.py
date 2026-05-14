from typing import Any
import torch
import os
from diffusers import FluxPipeline, FluxTransformer2DModel, GGUFQuantizationConfig
from PIL import Image

def generate_flux_image(
    prompt: str, 
    output_path: str = "data/output.png",
    model_dir: str = "/app/models"
):
    """
    Generates an image using FLUX.1-schnell GGUF on an RTX 3060.
    """
    
    # 1. Define paths for your 4 "Organs"
    transformer_path = os.path.join(model_dir, "flux1-schnell-Q4_K_S.gguf")
    vae_path = os.path.join(model_dir, "ae.safetensors")
    clip_path = os.path.join(model_dir, "clip_l.safetensors")
    t5_path = os.path.join(model_dir, "t5xxl_q4_k_m.gguf")

    print(f"--- Loading FLUX Brain from {transformer_path} ---")

    # 2. Load the GGUF Transformer (The Brain)
    # This keeps weights in 4-bit and only dequantizes during the forward pass
    transformer = FluxTransformer2DModel.from_single_file(
        transformer_path,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16
    )

    # 3. Initialize the Pipeline
    # We use the 'schnell' config but swap in your local GGUF transformer
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-schnell", 
        transformer=transformer,
        torch_dtype=torch.bfloat16
    )

    # 4. RTX 3060 Optimization: Memory Offloading
    # This moves the Text Encoders to CPU RAM and only puts the active part 
    # of the model on your GPU. Essential for 12GB cards!
    pipe.enable_model_cpu_offload()

    print(f"--- Generating Image for: {prompt[:30]}... ---")

    # 5. Run Inference
    # Schnell needs 4 steps. Guidance 0.0 is standard for the distilled version.
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

    # 6. Save and Cleanup
    image.save(output_path)
    print(f"--- Image saved to {output_path} ---")
    
    # Intensive cleanup to free the ~8-10GB used by Flux for the 3060
    del pipe
    del transformer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect() # Extra clearing for segmented memory
    
    return output_path