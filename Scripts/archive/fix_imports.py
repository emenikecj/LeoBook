"""Fix all import paths after widget folder restructure."""
import os

lib = r"c:\Users\Admin\Desktop\ProProjection\LeoBook\leobookapp\lib"

replacements = {
    # desktop_home_content.dart internal relative imports (was in responsive/)
    "import 'category_bar.dart'": "import '../shared/category_bar.dart'",
    "import 'accuracy_report_card.dart'": "import '../shared/accuracy_report_card.dart'",
    "import '../featured_carousel.dart'": "import '../shared/featured_carousel.dart'",
    "import '../footnote_section.dart'": "import '../shared/footnote_section.dart'",
    "import 'global_stats_footer.dart'": "import '../shared/global_stats_footer.dart'",
    "import 'leo_tab.dart'": "import '../shared/leo_tab.dart'",
    "import 'leo_date_picker.dart'": "import '../shared/leo_date_picker.dart'",
    "import 'navigation_sidebar.dart'": "import '../desktop/navigation_sidebar.dart'",

    # Package-style imports referencing old paths
    "package:leobookapp/presentation/widgets/match_card.dart": "package:leobookapp/presentation/widgets/shared/match_card.dart",
    "package:leobookapp/presentation/widgets/news_feed.dart": "package:leobookapp/presentation/widgets/shared/news_feed.dart",
    "package:leobookapp/presentation/widgets/featured_carousel.dart": "package:leobookapp/presentation/widgets/shared/featured_carousel.dart",
    "package:leobookapp/presentation/widgets/recommendation_card.dart": "package:leobookapp/presentation/widgets/shared/recommendation_card.dart",
    "package:leobookapp/presentation/widgets/footnote_section.dart": "package:leobookapp/presentation/widgets/shared/footnote_section.dart",
    "package:leobookapp/presentation/widgets/responsive/desktop_header.dart": "package:leobookapp/presentation/widgets/desktop/desktop_header.dart",
    "package:leobookapp/presentation/widgets/responsive/desktop_home_content.dart": "package:leobookapp/presentation/widgets/desktop/desktop_home_content.dart",
    "package:leobookapp/presentation/widgets/responsive/navigation_sidebar.dart": "package:leobookapp/presentation/widgets/desktop/navigation_sidebar.dart",
    "package:leobookapp/presentation/widgets/responsive/category_bar.dart": "package:leobookapp/presentation/widgets/shared/category_bar.dart",
    "package:leobookapp/presentation/widgets/responsive/accuracy_report_card.dart": "package:leobookapp/presentation/widgets/shared/accuracy_report_card.dart",
    "package:leobookapp/presentation/widgets/responsive/leo_tab.dart": "package:leobookapp/presentation/widgets/shared/leo_tab.dart",
    "package:leobookapp/presentation/widgets/responsive/leo_date_picker.dart": "package:leobookapp/presentation/widgets/shared/leo_date_picker.dart",
    "package:leobookapp/presentation/widgets/responsive/global_stats_footer.dart": "package:leobookapp/presentation/widgets/shared/global_stats_footer.dart",

    # Relative imports from screens/ -> widgets/ (these were already fixed in first batch but catch stragglers)
    "'../widgets/responsive/desktop_header.dart'": "'../widgets/desktop/desktop_header.dart'",
    "'../widgets/responsive/desktop_home_content.dart'": "'../widgets/desktop/desktop_home_content.dart'",
    "'../widgets/responsive/navigation_sidebar.dart'": "'../widgets/desktop/navigation_sidebar.dart'",
    "'../widgets/responsive/accuracy_report_card.dart'": "'../widgets/shared/accuracy_report_card.dart'",
    "'../widgets/responsive/category_bar.dart'": "'../widgets/shared/category_bar.dart'",
    "'../widgets/responsive/global_stats_footer.dart'": "'../widgets/shared/global_stats_footer.dart'",
    "'../widgets/responsive/leo_date_picker.dart'": "'../widgets/shared/leo_date_picker.dart'",
    "'../widgets/responsive/leo_tab.dart'": "'../widgets/shared/leo_tab.dart'",
    "'../widgets/match_card.dart'": "'../widgets/shared/match_card.dart'",
    "'../widgets/news_feed.dart'": "'../widgets/shared/news_feed.dart'",
    "'../widgets/recommendation_card.dart'": "'../widgets/shared/recommendation_card.dart'",
    "'../widgets/featured_carousel.dart'": "'../widgets/shared/featured_carousel.dart'",
    "'../widgets/footnote_section.dart'": "'../widgets/shared/footnote_section.dart'",
    "'../widgets/league_tabs/overview_tab.dart'": "'../widgets/shared/league_tabs/overview_tab.dart'",
    "'../widgets/league_tabs/fixtures_tab.dart'": "'../widgets/shared/league_tabs/fixtures_tab.dart'",
    "'../widgets/league_tabs/predictions_tab.dart'": "'../widgets/shared/league_tabs/predictions_tab.dart'",
    "'../widgets/league_tabs/stats_tab.dart'": "'../widgets/shared/league_tabs/stats_tab.dart'",

    # Widgets in shared/ that reference screens via relative paths
    # They moved from widgets/ to widgets/shared/, so need extra ../
    "'../screens/match_details_screen.dart'": "'../../screens/match_details_screen.dart'",
    "'../screens/team_screen.dart'": "'../../screens/team_screen.dart'",
    "'../screens/league_screen.dart'": "'../../screens/league_screen.dart'",
    "'../screens/search_screen.dart'": "'../../screens/search_screen.dart'",
    "'../screens/home_screen.dart'": "'../../screens/home_screen.dart'",
    "'../screens/top_predictions_screen.dart'": "'../../screens/top_predictions_screen.dart'",
}

count = 0
for root, dirs, files in os.walk(lib):
    for f in files:
        if not f.endswith(".dart"):
            continue
        fpath = os.path.join(root, f)
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()
        new_content = content
        for old, new in replacements.items():
            new_content = new_content.replace(old, new)
        if new_content != content:
            with open(fpath, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_content)
            count += 1
            rel = os.path.relpath(fpath, lib)
            print(f"  [fix] {rel}")

print(f"\nFixed {count} files.")
