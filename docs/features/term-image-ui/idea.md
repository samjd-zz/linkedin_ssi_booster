# Feature Idea: Term-Image UI Integration

## Overview

This document proposes integrating the `term-image` library to enable rich, high-fidelity image display directly within the terminal UI of the LinkedIn SSI Booster. This enhancement will allow users to immediately visualize generated images, avatars, or other visual artifacts without needing to open external image viewers.

## Problem Statement (Project Context)

The LinkedIn SSI Booster currently generates high-fidelity images using the FLUX.1-schnell pipeline. However, the console output remains purely text-based. When images are generated, users do not get immediate visual feedback in their terminal, requiring them to manually locate and open image files to review them. This disrupts the workflow and reduces the immediacy of the feedback loop, especially during development, debugging, and content generation previews.

## Proposed Solution

Integrate `term-image` (https://term-image.readthedocs.io/en/v0.1.1/viewer/tui.html#ui-components) into the project's console output system. This will allow the system to render generated images (e.g., from `services/image_generation.py`) directly within the terminal, leveraging `term-image`'s capabilities for displaying images across various terminal emulators.

The integration should focus on:
-   Detecting a supported terminal for `term-image` (e.g., Kitty, iTerm2, Konsole, or unsupported terminals using `chafa`/`sixel` fallbacks).
-   Providing a CLI flag (e.g., `--show-terminal-image`) to enable/disable this feature.
-   Displaying generated images as part of the normal console output flow, especially during `--dry-run` or when a post includes an image.
-   Considering `term-image`'s UI components, such as `DirectImage` or `TextImage`, for optimal display based on image type and terminal capabilities.

## Expected Benefits (Project User Impact)

-   **Enhanced User Experience**: Users gain immediate visual feedback of generated images directly in their terminal, streamlining the content creation and review process.
-   **Improved Debugging and Development**: Developers can quickly verify generated images without context switching to an external viewer, accelerating iteration.
-   **Richer Console Reports**: Future console reports could include visual elements, making them more informative and engaging.
-   **Increased Transparency**: Users can visually confirm the output of the FLUX.1-schnell pipeline without extra steps.
-   **No External Dependencies for Viewing**: Images are viewed within the existing terminal, removing the need for separate image viewer applications.

## Technical Considerations (Project Integration)

### Technology Stack Integration Requirements
-   **Language**: Python 3.12+
-   **New Dependency**: `term-image` (to be added to `requirements.txt`).
-   **Image Handling**: Integration with `PIL/Pillow` (already likely in use for image generation) for `term-image` compatibility.

### Architecture Alignment and Patterns
-   The integration should be modular, ideally encapsulated within a new or existing service (e.g., `services/terminal_ui.py` or an extension of `services/image_generation.py`).
-   The display logic should be invoked conditionally based on CLI arguments and terminal capabilities.
-   Adhere to absolute import conventions and `logging.getLogger(__name__)`.

### External Service and Dependency Requirements
-   The primary external dependency is the `term-image` library itself.
-   No new external APIs or cloud services are required as `term-image` operates locally.

## Project System Integration

-   **`main.py`**:
    -   Add a new argument, e.g., `--show-terminal-image`, to enable the feature.
    -   Conditional calls to the image display logic based on this flag.
-   **`services/image_generation.py`**:
    -   Potentially extend this service to include a function for displaying the generated image path using `term-image`.
    -   This function would take the image file path and handle the `term-image` rendering.
-   **`services/shared.py`**:
    -   Consider a shared flag for terminal image display status if needed across multiple modules.
-   **`requirements.txt`**: Add `term-image` as a dependency.

## Initial Scope

The initial scope will focus on:
1.  Adding `term-image` to `requirements.txt`.
2.  Implementing a function that takes an image file path and displays it in the terminal using `term-image`.
3.  Integrating this function into `main.py` such that when `--show-terminal-image` is used after image generation, the image is displayed.
4.  Ensuring basic compatibility with common terminal emulators (e.g., `xterm-256color`, `kitty`, `iterm`).

## Success Criteria

-   A user running `python main.py --curate --show-terminal-image --dry-run` sees any generated images displayed directly in their terminal.
-   The feature does not introduce new errors or significantly impact performance.
-   The `term-image` dependency is correctly listed in `requirements.txt`.
-   The code adheres to project conventions (type hints, logging, absolute imports).
