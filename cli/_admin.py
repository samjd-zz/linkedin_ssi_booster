"""One-shot admin commands: reports, SSI scores, reconcile, Bluesky stats, categories."""

import os
from typing import Callable

from colorama import Fore, Style

from services.buffer_service import BufferService


def run_admin_command(args, build_buffer_service: Callable[[], BufferService]) -> bool:
    """Run any requested admin command; return True when the CLI should exit."""
    if args.avatar_learn_report:
        from services.avatar_intelligence import build_learning_report, format_learning_report
        report = build_learning_report()
        print(format_learning_report(report))
        return True

    from services.ssi_tracker import SSITracker
    tracker = SSITracker()

    if args.report:
        tracker.print_report()
        return True

    if args.reconcile:
        from services.selection_learning import reconcile_published
        buffer = build_buffer_service()
        channel_ids: dict[str, str | None] = {"linkedin": buffer.get_linkedin_channel_id()}
        x_id = os.getenv("BUFFER_X_CHANNEL_ID")
        bsky_id = os.getenv("BUFFER_BLUESKY_CHANNEL_ID")
        threads_id = os.getenv("BUFFER_THREADS_CHANNEL_ID")
        facebook_id = os.getenv("BUFFER_FACEBOOK_CHANNEL_ID")
        if x_id:
            channel_ids["x"] = x_id
        if bsky_id:
            channel_ids["bluesky"] = bsky_id
        if threads_id:
            channel_ids["threads"] = threads_id
        if facebook_id:
            channel_ids["facebook"] = facebook_id
        stats = reconcile_published(buffer, {k: v for k, v in channel_ids.items() if v is not None})
        print(str(Fore.GREEN) + "\n✅  Reconcile complete" + str(Style.RESET_ALL))
        for k, v in stats.items():
            print(f"   {k}: {v}")

    if args.save_ssi:
        brand, find, engage, build = args.save_ssi
        tracker.save_scores(establish=brand, find=find, engage=engage, build=build)
        total = brand + find + engage + build
        print(str(Fore.GREEN) + f"✅  Saved SSI scores: brand={brand} find={find} engage={engage} build={build} total={total:.2f}" + str(Style.RESET_ALL))
        return True

    if args.bsky_stats:
        from services.ssi_tracker import fetch_bluesky_stats
        stats = fetch_bluesky_stats()
        if stats:
            print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n📊 Bluesky stats for @{stats['handle']}" + str(Style.RESET_ALL))
            print(f"  👥 Followers    : {str(Fore.WHITE)}{stats['followers']}{str(Style.RESET_ALL)}")
            print(f"  ➡️  Following    : {stats['following']}")
            print(f"  📝 Total posts  : {stats['posts']}")
            print(str(Fore.CYAN) + f"\n  Last {stats['analysed']} posts (engagement)" + str(Style.RESET_ALL))
            print(f"  ❤️  Likes        : {stats['total_likes']}")
            print(f"  💬 Replies      : {stats['total_replies']}")
            print(f"  🔁 Reposts      : {stats['total_reposts']}")
            print(f"  🗨️  Quotes       : {stats['total_quotes']}")
            print(f"  📈 Avg / post   : {stats['avg_engagement']}")
            if stats.get("top_post"):
                tp = stats["top_post"]
                print(str(Fore.YELLOW) + f"\n  🏆 Top post ({tp['likes']}L {tp['replies']}R {tp['reposts']}RT)" + str(Style.RESET_ALL))
                print(f"  '{tp['text']}'")
                if tp["url"]:
                    print(f"  {tp['url']}")
        return True

    if args.list_categories:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return True
        categories = svc.list_categories()
        if not categories:
            print(str(Fore.YELLOW) + "\n⚠️  No categories found" + str(Style.RESET_ALL))
            return True
        print(str(Fore.CYAN) + str(Style.BRIGHT) + f"\n🏷️  Model2Vec Categories ({len(categories)} total)" + str(Style.RESET_ALL))
        print()
        for name, meta in sorted(categories.items()):
            is_custom = meta.get("custom", "False") == "True"
            ssi = meta.get("ssi_component", "general")
            desc = meta.get("description", "")
            custom_marker = str(Fore.MAGENTA) + " [custom]" + str(Style.RESET_ALL) if is_custom else ""
            print(str(Fore.WHITE) + str(Style.BRIGHT) + f"  {name}" + str(Style.RESET_ALL) + custom_marker)
            print(f"    {desc[:100]}{'...' if len(desc) > 100 else ''}")
            print(str(Fore.YELLOW) + f"    → {ssi}" + str(Style.RESET_ALL))
            print()
        return True

    if args.add_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return True
        name, description, ssi_component = args.add_category
        valid_ssi = {"establish_brand", "find_right_people", "engage_with_insights", "build_relationships"}
        if ssi_component not in valid_ssi:
            print(str(Fore.RED) + f"\n❌  Invalid SSI component: {ssi_component}" + str(Style.RESET_ALL))
            print(f"    Valid options: {', '.join(sorted(valid_ssi))}")
            return True
        success = svc.add_category(name, description, ssi_component)
        if success:
            print(str(Fore.GREEN) + f"\n✅  Added custom category: '{name}'" + str(Style.RESET_ALL))
            print(f"    Description: {description[:80]}{'...' if len(description) > 80 else ''}")
            print(str(Fore.YELLOW) + f"    SSI Component: {ssi_component}" + str(Style.RESET_ALL))
        else:
            print(str(Fore.RED) + f"\n❌  Failed to add category '{name}' (may already exist)" + str(Style.RESET_ALL))
        return True

    if args.remove_category:
        from services.model2vec_service import get_model2vec_service
        svc = get_model2vec_service()
        if not svc.is_available():
            print(str(Fore.YELLOW) + "\n⚠️  Model2Vec is not available (install with: pip install model2vec numpy)" + str(Style.RESET_ALL))
            return True
        names = args.remove_category
        results = svc.remove_categories(names)
        successes = [n for n, r in zip(names, results) if r]
        failures = [n for n, r in zip(names, results) if not r]
        if successes:
            print(str(Fore.GREEN) + f"\n✅  Removed {len(successes)} category(ies):" + str(Style.RESET_ALL))
            for name in successes:
                print(f"    • {name}")
        if failures:
            print(str(Fore.RED) + f"\n❌  Failed to remove {len(failures)} category(ies):" + str(Style.RESET_ALL))
            for name in failures:
                print(f"    • {name} (not found or is a default category)")
        return True
    return False
