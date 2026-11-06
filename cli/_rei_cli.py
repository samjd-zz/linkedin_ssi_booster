"""--rei-generate / --rei-generate-strudel CLI dispatcher."""

import asyncio
import logging

from colorama import Fore, Style

from services.rei_toei._models import LyricCompositionError

logger = logging.getLogger(__name__)


def run_rei_cli(args, ai) -> None:
    """Run the requested Rei Toei generation flow (Suno or Strudel)."""
    from services.rei_toei_service import ReiToeiConfig
    from cli._rei_strudel import handle_rei_generate_strudel
    from cli._rei_suno import handle_rei_generate

    rei_config = ReiToeiConfig()

    if not rei_config.enabled:
        print(
            str(Fore.YELLOW)
            + "⚠️  Rei Toei is disabled (REI_TOEI_ENABLED=false) — skipping generation."
            + str(Style.RESET_ALL)
        )
        return

    try:
        if args.rei_generate:
            asyncio.run(handle_rei_generate(args, ai, rei_config))
        elif args.rei_generate_strudel:
            asyncio.run(handle_rei_generate_strudel(args, ai, rei_config))
    except KeyboardInterrupt:
        print("\nRei Toei generation cancelled.")
    except LyricCompositionError as exc:
        logger.error("Rei Toei song generation failed: %s", exc)
        print(str(Fore.RED) + f"\n\u274c  Rei Toei error: {exc}" + str(Style.RESET_ALL))
        raise SystemExit(1) from None
    except Exception as _rei_err:
        logger.error("Rei Toei CLI error: %s", _rei_err, exc_info=True)
        cause = _rei_err.__cause__
        detail = f"{_rei_err} (caused by: {cause})" if cause else str(_rei_err)
        print(str(Fore.RED) + f"\n\u274c  Rei Toei error: {detail}" + str(Style.RESET_ALL))
