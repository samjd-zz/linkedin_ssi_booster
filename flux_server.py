"""
Minimal Flask HTTP server for the FLUX.1-schnell inference container.

Runs inside the `full_build` Docker container (the only one with torch +
diffusers + llama-cpp-python installed).  The `core_base` (app) container
calls POST /generate via FLUX_SERVICE_URL=http://flux-app:5000.

The output_path written must be inside a volume shared between both
containers — currently /app/yt-vid-data.
"""

import logging
import os

from flask import Flask, jsonify, request

from services.image_generation import generate_flux_image  # only importable here

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

MODEL_PATH_OR_DIR = os.getenv("FLUX_MODEL_PATH", "/app/models/flux")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def generate():
    """
    Body: {
        "prompt": str,
        "output_path": str,
        "width": int (optional),
        "height": int (optional),
        "num_inference_steps": int (optional)
    }
    Response: { "output_path": str } or { "error": str }
    """
    body = request.get_json(force=True, silent=True) or {}
    prompt = body.get("prompt", "").strip()
    output_path = body.get("output_path", "").strip()
    width = int(body.get("width", os.getenv("FLUX_RENDER_WIDTH", "768")))
    height = int(body.get("height", os.getenv("FLUX_RENDER_HEIGHT", "768")))
    num_inference_steps = int(body.get("num_inference_steps", os.getenv("FLUX_RENDER_STEPS", "4")))

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if not output_path:
        return jsonify({"error": "output_path is required"}), 400
    if width < 256 or height < 256:
        return jsonify({"error": "width and height must be >= 256"}), 400
    if num_inference_steps < 1:
        return jsonify({"error": "num_inference_steps must be >= 1"}), 400

    # Restrict writes to the shared yt-vid-data directory for security.
    allowed_prefix = "/app/yt-vid-data"
    if not os.path.abspath(output_path).startswith(allowed_prefix):
        return jsonify({"error": f"output_path must be inside {allowed_prefix}"}), 400

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        generate_flux_image(
            prompt=prompt,
            output_path=output_path,
            model_dir=MODEL_PATH_OR_DIR,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            keep_loaded=True,
        )
        logger.info("FLUX render complete: %s", output_path)
        return jsonify({"output_path": output_path})
    except Exception as exc:
        logger.error("FLUX render failed: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.getenv("FLUX_SERVER_PORT", "5000"))
    logger.info("Starting FLUX inference server on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
